"""G-CONFIG-READER: every pipeline config field the engine accepts has a recorded reader.

A pipeline config accepts a field that no run reads, and the run reports success: that is how
`pre_scan` was accepted and ignored. This sentry walks the pinned engine's live
`PipelineConfig` (every top-level field and the fields of every top-level field whose annotation
is a pydantic model, through `Optional` and unions) and demands exactly one manifest entry per
path in `tests/sentry/baselines/config-field-readers.json`. The list of paths comes from the
live model, never from the manifest.

It does not walk `tables`, `columns`, `sources`, `targets` or per-column strategy fields. Those
are list or dict items read by the compiler and covered by the engine's own plan tests; walking
them would turn the manifest into a copy of the schema.

Entry kinds: `engine` (a public engine symbol whose source names the key), `cli` (a function on
the CLI run path, with exact call chains), `other_command` (read only by another command) and
`unread` (accepted and read by no run; a shrink-only ratchet through the registered baseline).

Named limits: a read through `getattr` with a computed name, `model_dump()` walked generically,
and a symbol that mentions the key without reading it. The sentry proves a reader is wired to the
key's name; the engine plan tests prove what it does with it. Ported idea: dbt's unused
configuration warning, applied at build time.
"""

from __future__ import annotations

import copy
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from decoy_engine.config import PipelineConfig
from pydantic import BaseModel, create_model
from tests.sentry._ratchet import load_allowlist
from tests.sentry.config import _readers as r

ROOT = Path(__file__).resolve().parents[3]


UNREAD: dict[str, Any] = load_allowlist("config-field-readers")


def _real() -> dict[str, Any]:
    return r.load_manifest(UNREAD)


def _text(found: list[str]) -> str:
    return "\n".join(found)


def test_t1_every_walked_path_has_exactly_one_entry() -> None:
    assert r.findings(PipelineConfig, _real(), ROOT) == []


def test_t1_a_missing_entry_is_a_finding() -> None:
    manifest = copy.deepcopy(_real())
    del manifest["readers"]["global_settings.seed"]
    assert "global_settings.seed" in _text(r.findings(PipelineConfig, manifest, ROOT))


def test_t1_a_path_with_two_entries_or_a_stale_entry_is_a_finding() -> None:
    manifest = copy.deepcopy(_real())
    manifest["unread"]["global_settings.seed"] = {"reason": "twice listed on purpose", "row": "X"}
    manifest["readers"]["no_such.field"] = {"other_command": "x", "row": "X"}
    text = _text(r.findings(PipelineConfig, manifest, ROOT))
    assert "global_settings.seed" in text and "no_such.field" in text


def test_t2_every_engine_entry_names_its_key() -> None:
    for path, entry in _real()["readers"].items():
        if "engine" in entry:
            assert r.engine_findings(path, entry) == [], path


def test_t2_an_engine_entry_that_does_not_name_its_key_fails() -> None:
    entry = {"engine": "decoy_engine.plan:compile_plan"}
    found = r.engine_findings("global_settings.no_such_setting_here", entry)
    assert found and "does not" in found[0]


def test_t2_a_model_class_does_not_count_as_a_reader() -> None:
    entry = {"engine": "decoy_engine.config:PreScanConfig"}
    assert r.engine_findings("pre_scan.on_findings", entry)


def test_t3_a_complete_chain_passes(tmp_path: Path) -> None:
    root = _chain_tree(tmp_path)
    assert r.cli_findings("pre_scan", _chain_entry(), root) == []


@pytest.mark.parametrize(
    ("file", "drop", "link"),
    [
        ("src/decoy/cli/run/_prepare.py", "run_pre_scan(", "prepare -> run_pre_scan"),
        ("src/decoy/api.py", "_mask_pre_scan(", "mask -> _mask_pre_scan"),
    ],
)
def test_t3_a_dropped_link_fails_even_when_the_next_hop_still_calls_on(
    tmp_path: Path, file: str, drop: str, link: str
) -> None:
    root = _chain_tree(tmp_path)
    target = root / file
    target.write_text(target.read_text().replace(drop, "unrelated("), encoding="utf-8")
    found = _text(r.cli_findings("pre_scan", _chain_entry(), root))
    assert link.split(" -> ")[0] in found and link.split(" -> ")[1] in found


def test_t3_a_call_inside_a_nested_function_is_not_a_direct_call(tmp_path: Path) -> None:
    root = _chain_tree(tmp_path)
    prep = root / "src/decoy/cli/run/_prepare.py"
    prep.write_text(
        "def prepare(cfg):\n    def never_called():\n        run_pre_scan(cfg)\n", encoding="utf-8"
    )
    assert r.cli_findings("pre_scan", _chain_entry(), root)


def test_t3_a_missing_file_or_function_fails(tmp_path: Path) -> None:
    root = _chain_tree(tmp_path)
    entry = _chain_entry()
    entry["cli"] = "src/decoy/cli/run/_prepare.py::no_such_function"
    assert r.cli_findings("pre_scan", entry, root)
    entry["cli"] = "src/decoy/cli/run/missing.py::prepare"
    assert r.cli_findings("pre_scan", entry, root)


def test_t4_a_removed_unread_row_cannot_come_back(tmp_path: Path) -> None:
    """The registered baseline is the one list of unread rows: the shrink-only ratchet refuses a
    row the merge base no longer holds, with no second copy of the list in this file."""
    from tests.sentry import _ratchet

    reg = "scripts/dev/sentry_registry.toml"
    path = "tests/sentry/baselines/config-field-readers.json"
    rows = {"pre_scan": {"reason": "accepted and read by no run"}, "delivery": {"reason": "x" * 20}}

    def write(entries: dict[str, Any]) -> None:
        doc = {"sentry_id": "config-field-readers", "created_in": "S0", "entries": entries}
        (tmp_path / path).write_text(json.dumps(doc), encoding="utf-8")

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", *args],
            check=True,
            capture_output=True,
        )

    (tmp_path / path).parent.mkdir(parents=True)
    (tmp_path / reg).parent.mkdir(parents=True)
    (tmp_path / reg).write_text(
        f'[[sentry]]\nid = "config-field-readers"\nbaseline = "{path}"\n', encoding="utf-8"
    )
    git("init", "-q", "-b", "main")
    write(rows)
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    write({"delivery": rows["delivery"]})
    found, _ = _ratchet.check(tmp_path, "HEAD")
    assert found == []  # shrinking is allowed
    git("commit", "-qam", "shrink")
    write(rows)  # the removed row returns
    found, _ = _ratchet.check(tmp_path, "HEAD")
    assert any("gained key(s) not in the merge base: pre_scan" in f for f in found)


def test_t4_each_unread_row_names_a_roadmap_row() -> None:
    for path, entry in _real()["unread"].items():
        assert entry.get("row"), path


class _Extra(BaseModel):
    thing: int = 0


class _Extended(PipelineConfig):
    extra_block: _Extra | None = None


def test_t5_a_new_nested_block_the_walker_was_never_told_about_fails() -> None:
    assert "extra_block.thing" in r.walk(_Extended)
    text = _text(r.findings(_Extended, _real(), ROOT))
    assert "extra_block.thing" in text and "extra_block:" in text


def _grown(block: str) -> type[BaseModel]:
    """PipelineConfig where the nested model of ``block`` gains one new child field."""
    (nested,) = r._models_of(PipelineConfig.model_fields[block].annotation)
    child = create_model("Grown", __base__=nested, brand_new_child=(int, 0))
    return create_model("GrownPipeline", __base__=PipelineConfig, **{block: (child, child())})


def _block_manifest(block: str, children: list[str]) -> dict[str, Any]:
    """The live manifest with ``block`` made an unread block of exactly ``children``, so the
    child checks never depend on which rows the live registry holds today."""
    manifest = copy.deepcopy(_real())
    for path in [p for p in r.walk(PipelineConfig) if p.startswith(block + ".")]:
        manifest["readers"].pop(path, None)
        manifest["unread"].pop(path, None)
    manifest["readers"].pop(block, None)
    manifest["unread"][block] = {"reason": "fixture", "row": "X", "children": children}
    return manifest


def _children_of_block(block: str) -> list[str]:
    return [p.partition(".")[2] for p in r.walk(PipelineConfig) if p.startswith(block + ".")]


@pytest.mark.parametrize("block", ["pre_scan", "delivery"])
def test_t5_a_new_child_of_an_unread_block_needs_classification(block: str) -> None:
    model = _grown(block)
    manifest = _block_manifest(block, _children_of_block(block))
    assert f"{block}.brand_new_child" in r.walk(model)
    text = _text(r.findings(model, manifest, ROOT))
    assert f"{block}.brand_new_child" in text and "classify" in text


def test_t5_a_known_child_of_an_unread_block_is_not_a_finding() -> None:
    kids = _children_of_block("pre_scan")
    assert kids
    assert r.findings(PipelineConfig, _block_manifest("pre_scan", kids), ROOT) == []


def test_t5_a_listed_child_the_block_no_longer_has_is_a_finding() -> None:
    kids = _children_of_block("pre_scan")
    manifest = _block_manifest("pre_scan", [*kids, "gone_child"])
    assert "pre_scan.gone_child" in _text(r.findings(PipelineConfig, manifest, ROOT))


def test_t5_an_unread_block_with_children_lists_them() -> None:
    manifest = _block_manifest("delivery", _children_of_block("delivery"))
    del manifest["unread"]["delivery"]["children"]
    assert "delivery." in _text(r.findings(PipelineConfig, manifest, ROOT))


def test_t5_the_walk_does_not_enter_list_or_dict_items() -> None:
    paths = r.walk(PipelineConfig)
    assert "tables" in paths and not any(p.startswith("tables.") for p in paths)
    assert "pre_scan.detectors" in paths and "global_settings.seed" in paths


@pytest.mark.parametrize(
    ("spec", "rule"),
    [
        ("decoy_engine.plan._compile:compile_plan", "private"),
        ("decoy_engine.plan:_checks", "private"),
        ("decoy_engine.plan._compile:_hash_config", "private"),
        ("decoy_engine.plan:validate", "__all__"),
    ],
)
def test_t6_a_private_or_unlisted_engine_symbol_fails(spec: str, rule: str) -> None:
    found = r.engine_findings("global_settings.on_pool_exhaustion", {"engine": spec})
    assert found and rule in found[0]


def test_t6_a_public_listed_symbol_passes_the_visibility_rule() -> None:
    found = r.engine_findings(
        "global_settings.on_pool_exhaustion", {"engine": "decoy_engine.plan:compile_plan"}
    )
    assert found == []


@pytest.mark.parametrize(
    "path", ["scan_baseline.path", "quarantine.enabled", "delivery.mode", "global_settings.seed"]
)
def test_t7_a_short_or_common_key_with_no_via_fails(path: str) -> None:
    found = r.engine_findings(path, {"engine": "decoy_engine.plan:compile_plan"})
    assert found and "via" in found[0]


def test_t7_a_via_helper_the_symbol_does_not_call_fails() -> None:
    entry = {
        "engine": "decoy_engine.plan:compile_plan",
        "via": "decoy_engine.execution:run_pipeline",
    }
    found = r.engine_findings("quarantine.enabled", entry)
    assert found and "call" in found[0]


def _chain_entry() -> dict[str, Any]:
    prep = "src/decoy/cli/run/_prepare.py::prepare"
    scan = "src/decoy/cli/run/_pre_scan.py::run_pre_scan"
    core = "src/decoy/cli/run/_pre_scan.py::check_pre_scan"
    return {
        "cli": prep,
        "via": "pre_scan_requested",
        "chains": {
            "run": [prep, scan, core],
            "api.mask": ["src/decoy/api.py::mask", "src/decoy/api.py::_mask_pre_scan", core],
        },
    }


def _chain_tree(base: Path) -> Path:
    files = {
        "src/decoy/cli/run/_prepare.py": "def prepare(cfg):\n    if pre_scan_requested(cfg):\n        run_pre_scan(cfg)\n",
        "src/decoy/cli/run/_pre_scan.py": "def run_pre_scan(cfg):\n    check_pre_scan(cfg)\n\ndef check_pre_scan(cfg):\n    return cfg\n",
        "src/decoy/api.py": "def mask(cfg):\n    _mask_pre_scan(cfg)\n\ndef _mask_pre_scan(cfg):\n    check_pre_scan(cfg)\n",
    }
    for rel, text in files.items():
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text(text, encoding="utf-8")
    return base


def _pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, str]) -> None:
    """A throwaway public package ``rdrpkg`` with an ``__all__`` and private helper modules."""
    root = tmp_path / "rdrpkg"
    root.mkdir()
    (root / "__init__.py").write_text(files.pop("__init__"), encoding="utf-8")
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    r._package_trees.cache_clear()
    r._defs_by_name.cache_clear()
    for mod in [m for m in sys.modules if m.split(".")[0] == "rdrpkg"]:
        del sys.modules[mod]
    importlib.invalidate_caches()


_PKG_OK = {
    "__init__": (
        "from ._helper import reads_things, other\n"
        "def real_reader(cfg):\n    return reads_things(cfg)\n"
        "def wrong_reader(cfg):\n    return other(cfg)\n"
        "def dropped_reader(cfg):\n    return cfg\n"
        '__all__ = ["real_reader", "wrong_reader", "dropped_reader", "reads_things", "other"]\n'
    ),
    "_helper.py": (
        'def reads_things(cfg):\n    return cfg["gadget_widths"]\ndef other(cfg):\n    return cfg\n'
    ),
}
_VIA = "rdrpkg:reads_things"


def _entry(symbol: str) -> dict[str, Any]:
    return {"engine": f"rdrpkg:{symbol}", "scope": "package", "via": _VIA}


def test_t8_a_package_reader_that_calls_its_helper_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pkg(tmp_path, monkeypatch, dict(_PKG_OK))
    assert r.engine_findings("block.gadget_widths", _entry("real_reader")) == []


def test_t8_a_wrong_reader_in_the_same_package_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The key is named in the package, but not by the symbol the entry points at."""
    _pkg(tmp_path, monkeypatch, dict(_PKG_OK))
    assert r.engine_findings("block.gadget_widths", _entry("wrong_reader"))
    bare = {"engine": "rdrpkg:wrong_reader", "scope": "package"}
    assert r.engine_findings("block.gadget_widths", bare)


def test_t8_a_reader_that_stops_calling_its_helper_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another function in the package still calls the helper; this reader no longer does."""
    _pkg(tmp_path, monkeypatch, dict(_PKG_OK))
    found = r.engine_findings("block.gadget_widths", _entry("dropped_reader"))
    assert found and "call" in found[0]


def test_t8_a_helper_whose_package_never_names_the_key_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pkg(tmp_path, monkeypatch, dict(_PKG_OK))
    found = r.engine_findings("block.unrelated_setting", _entry("real_reader"))
    assert found and "does not name" in found[0]


def _via_entry(via: str) -> dict[str, Any]:
    return {"engine": "rdrpkg:real_reader", "scope": "package", "via": via}


def test_t8_a_private_helper_resolves_by_its_exact_module_and_symbol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pkg(tmp_path, monkeypatch, dict(_PKG_OK))
    assert r.engine_findings("block.gadget_widths", _via_entry("rdrpkg._helper:reads_things")) == []


@pytest.mark.parametrize(
    "via",
    [
        "rdrpkg.typo:reads_things",  # module does not exist; the bare name does elsewhere
        "rdrpkg._helper:no_such_helper",  # module exists; the symbol does not
        "rdrpkg._other:reads_things",  # module exists; the name is defined in a different module
    ],
)
def test_t8_a_via_in_the_wrong_module_or_symbol_fails_though_the_name_exists_elsewhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, via: str
) -> None:
    files = {**_PKG_OK, "_other.py": "def unrelated(cfg):\n    return cfg\n"}
    _pkg(tmp_path, monkeypatch, files)
    assert r.engine_findings("block.gadget_widths", _via_entry(via))


def test_t8_a_via_that_only_a_method_or_nested_function_defines_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After a repin moves the helper onto a class, a module-level via entry is stale."""
    moved = (
        "class Gadget:\n"
        "    def reads_things(self, cfg):\n        return cfg['gadget_widths']\n"
        "def outer(cfg):\n"
        "    def nested_reads(cfg):\n        return cfg['gadget_widths']\n"
        "    return nested_reads(cfg)\n"
    )
    init = (
        "from ._helper import Gadget, outer\n"
        "def real_reader(cfg):\n    return Gadget().reads_things(cfg), outer(cfg)\n"
        '__all__ = ["real_reader"]\n'
    )
    _pkg(tmp_path, monkeypatch, {"__init__": init, "_helper.py": moved})
    assert r.engine_findings("block.gadget_widths", _via_entry("rdrpkg._helper:reads_things"))
    assert r.engine_findings("block.gadget_widths", _via_entry("rdrpkg._helper:nested_reads"))
