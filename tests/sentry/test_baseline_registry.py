"""Every committed baseline or allowlist a CLI sentry reads is registered and checked once.

The ratchet only protects what ``sentry_registry.toml`` names. Each registry row has a ``kind``:
``json`` rows are read by their sentry through ``load_allowlist`` (the baseline is the only copy);
``from_scan`` and ``from_file`` rows are tied to their reader's live keys, both directions. Every
baseline header is checked here once. A sentry in the ``SENTRIES`` manifest (``tests/unit``
sentries included) that holds an inline allowlist-shaped constant, or reads a committed data file
that is not registered, fails, so a new allowlist cannot sit beside the ratchet.

Ported from decoy-engine ``tests/sentry/test_baseline_registry.py`` (X0a).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _baseline_sources as bs

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

LIST_NAME = re.compile(r"ALLOW|EXEMPT|WAIVER|BASELINE|EXCEPTIONS|OMIT")
COLLECTION_CALLS = frozenset({"frozenset", "set", "tuple", "list"})
DATA_LITERAL = re.compile(r"[\w.\-]+\.(?:json|toml)$")
SENTRIES: tuple[str, ...] = bs.load_module(bs.SENTRY / "test_sentry_manifest.py").SENTRIES


def registry_rows() -> list[dict[str, str]]:
    text = bs.REGISTRY.read_text(encoding="utf-8")
    return list(tomllib.loads(text).get("sentry", []))


def registry() -> dict[str, str]:
    return {r["id"]: r["baseline"] for r in registry_rows()}


def _doc(sentry_id: str) -> dict[str, object]:
    path = bs.ROOT / registry()[sentry_id]
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.mark.parametrize("row", registry_rows(), ids=lambda r: r["id"])
def test_every_baseline_has_its_header_and_file_name(row: dict[str, str]) -> None:
    """The one header check: ``sentry_id`` is the registry id and ``created_in`` is named."""
    assert row["baseline"] == f"tests/sentry/baselines/{row['id']}.json"
    assert row.get("kind") in bs.KINDS, "registry row has no known kind"
    doc = _doc(row["id"])
    assert doc["sentry_id"] == row["id"]
    created_in = doc["created_in"]
    assert isinstance(created_in, str) and created_in.strip()


def test_only_recomputed_sentries_have_a_reader() -> None:
    kinds = {r["id"]: r["kind"] for r in registry_rows()}
    assert {i for i, k in kinds.items() if k != "json"} == set(bs.READERS)


@pytest.mark.parametrize("sentry_id", sorted(bs.READERS))
def test_recomputed_keys_match_the_registered_baseline(sentry_id: str) -> None:
    live, recorded = bs.READERS[sentry_id](), set(_doc(sentry_id)["entries"])  # type: ignore[call-overload]
    assert live - recorded == set(), "live entries missing from the baseline"
    assert recorded - live == set(), "stale baseline entries (shrink the baseline)"


def _is_collection(value: ast.expr | None) -> bool:
    if isinstance(value, ast.Call):
        return isinstance(value.func, ast.Name) and value.func.id in COLLECTION_CALLS
    return isinstance(value, (ast.Dict, ast.Tuple, ast.List, ast.Set))


def _reads_the_baseline(value: ast.expr | None) -> bool:
    """Whether the value is built by ``load_allowlist``, so it holds no second copy."""
    return value is not None and any(
        isinstance(n, ast.Name) and n.id == "load_allowlist" for n in ast.walk(value)
    )


def inline_allowlists(sources: dict[str, str], closed: set[tuple[str, str]]) -> list[str]:
    """Allowlist-shaped module constants that hold their own entries instead of the baseline."""
    found = []
    for name, text in sources.items():
        for node in ast.parse(text).body:
            targets = (
                node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
            )
            value = getattr(node, "value", None)
            for t in targets:
                is_list = isinstance(t, ast.Name) and LIST_NAME.search(t.id)
                if (
                    is_list
                    and _is_collection(value)
                    and not _reads_the_baseline(value)
                    and (name, t.id) not in closed
                ):
                    found.append(f"{name}: constant {t.id}")
    return sorted(set(found))


def unregistered_data_files(
    sources: dict[str, str], data_files: set[str], covered_files: set[str]
) -> list[str]:
    """Committed data files a sentry reads that no registry row or reader names."""
    found = []
    for name, text in sources.items():
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                base = node.value.rsplit("/", 1)[-1]
                if (
                    DATA_LITERAL.fullmatch(base)
                    and base in data_files
                    and base not in covered_files
                ):
                    found.append(f"{name}: data file {base}")
    return sorted(set(found))


def _covered_files() -> set[str]:
    return {Path(p).name for p in registry().values()} | set(bs.DATA_FILES)


def _data_files() -> set[str]:
    return {
        p.name
        for root in ("tests", "docs")
        for p in (bs.ROOT / root).rglob("*")
        if p.suffix in {".json", ".toml"}
    }


def _manifest_sources() -> dict[str, str]:
    # Keyed by basename, as NOT_A_LIST_CONSTS is; the names must not collide.
    names = [Path(s).name for s in SENTRIES]
    assert len(set(names)) == len(names), "two manifest files share a basename"
    out = {Path(s).name: (bs.ROOT / s).read_text(encoding="utf-8") for s in SENTRIES}
    out.pop("test_baseline_registry.py")  # holds the seeded fixtures below
    return out


def test_scan_reaches_the_tests_unit_sentries() -> None:
    unit = {Path(s).name for s in SENTRIES if s.startswith("tests/unit/")}
    assert len(unit) == 3
    assert unit <= set(_manifest_sources())


def test_no_sentry_holds_an_inline_allowlist() -> None:
    assert inline_allowlists(_manifest_sources(), set(bs.NOT_A_LIST_CONSTS)) == []


def test_no_sentry_reads_an_unregistered_baseline() -> None:
    assert unregistered_data_files(_manifest_sources(), _data_files(), _covered_files()) == []


def test_not_a_list_consts_still_exist() -> None:
    sources = _manifest_sources()
    stale = [
        f"{f}: {c}"
        for f, c in bs.NOT_A_LIST_CONSTS
        if not re.search(rf"^{c}\b", sources.get(f, ""), re.MULTILINE)
    ]
    assert stale == []


@pytest.mark.parametrize(
    "seed",
    [
        'NEW_ALLOWLIST = {"a": "b"}',
        'NEW_ALLOWLIST = frozenset({"bypass::site"})',
        'NEW_ALLOWLIST = set(["a"])',
        'NEW_ALLOWLIST = tuple(["a"])',
        'NEW_ALLOWLIST = list(("a",))',
        'NEW_ALLOWLIST = ("a",)',
        'NEW_ALLOWLIST = {"a"}',
        'NEW_ALLOWLIST: frozenset[str] = frozenset({"a"})',
        '_NEW_OMITTED = frozenset({"a"})',
        '_ALLOWED: dict[str, str] = {"a": "b"}',
    ],
)
def test_seeded_inline_allowlists_are_caught(seed: str) -> None:
    name = seed.split(" ", 1)[0].rstrip(":")
    found = inline_allowlists({"test_new.py": seed + "\n"}, set(bs.NOT_A_LIST_CONSTS))
    assert found == [f"test_new.py: constant {name}"]


def test_an_allowlist_built_from_the_baseline_passes() -> None:
    seed = 'ALLOWLIST = tuple(Row(k, e["reason"]) for k, e in load_allowlist("x").items())\n'
    assert inline_allowlists({"test_new.py": seed}, set()) == []


def test_seeded_unregistered_readers_are_caught() -> None:
    seeded_file = {"test_new.py": 'P = ROOT / "tests" / "fixtures" / "fresh-list.json"\n'}
    assert unregistered_data_files(seeded_file, {"fresh-list.json"}, _covered_files()) == [
        "test_new.py: data file fresh-list.json"
    ]


def test_a_registered_data_file_passes_and_an_unregistered_one_is_caught() -> None:
    files = _covered_files()
    assert "file_sinks.toml" in files
    registered = {"test_new.py": 'P = HERE / "file_sinks.toml"\n'}
    assert unregistered_data_files(registered, {"file_sinks.toml"}, files) == []
    unregistered = {"test_new.py": 'P = HERE / "other_sinks.toml"\n'}
    assert unregistered_data_files(unregistered, {"other_sinks.toml"}, files) == [
        "test_new.py: data file other_sinks.toml"
    ]
