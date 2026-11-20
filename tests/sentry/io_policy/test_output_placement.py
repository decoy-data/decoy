"""G-ONE-OUTPUT-PLACE: output paths are built by `RunLayout`, not by each command.

Three rules, each over every module under `src/decoy/`:

(a) `resolve_path` (the input-side YAML path resolver, any import spelling) is called only where
    a path is read or compared, listed in ALLOWLIST with the exact site count. `RunLayout` is the
    one writer-side caller. The baseline may shrink and never grow
    (tests/sentry/baselines/output-placement-allow.json, checked by scripts/dev/ratchet_check.py).
(b) Path-building calls (`with_suffix`, `with_name`, `joinpath`, `Path(...)`, a `/` join) that use
    a default side-file name (`.unmasked`, `.detokenized`, `.snapshot.json`, `.masked`) or the
    `out` folder literal sit only in `cli/io/_layout.py` and `cli/project/_scaffold.py`, except
    the sites in NAME_ALLOWLIST that later slices move there (shrink-only baseline
    tests/sentry/baselines/output-name-allow.json).
(c) `write_targets` and `write_chunked_output` take their placement as a `RunLayout`.
(d) `decoy validate`'s target check reaches a target path only through `place_target`.

A syntax walk: a path built through a runtime-bound name, or a literal assembled from pieces, is
not seen.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from tests.sentry._ratchet import load_allowlist
from tests.sentry.io_policy._calls import call_sites, tally

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"
PLACERS = ("cli/io/_layout.py", "cli/project/_scaffold.py")
NAME_LITERALS = (".unmasked", ".detokenized", ".snapshot.json", ".masked")
OUT_LITERAL = "out"
BUILDERS = frozenset({"with_suffix", "with_name", "joinpath", "Path", "PurePath"})
WRITERS = ("write_targets", "write_chunked_output")
TARGETS = "cli/io/_targets.py"
PREFLIGHT = "cli/preflight.py"
TARGET_CHECK = "_check_target_overwrite"


@dataclass(frozen=True)
class AllowedSite:
    file: str  # relative to src/decoy
    function: str
    sites: int
    reason: str


ALLOWLIST: tuple[AllowedSite, ...] = tuple(
    AllowedSite(*key.split("::"), e["sites"], e["reason"])
    for key, e in load_allowlist("output-placement-allow").items()
)

# Default names are built only in the placers; the P10 sweep emptied this list.
NAME_ALLOWLIST: tuple[AllowedSite, ...] = tuple(
    AllowedSite(*key.split("::"), e["sites"], e["reason"])
    for key, e in load_allowlist("output-name-allow").items()
)


def _resolve_sites(source: str) -> list[tuple[int, str]]:
    return call_sites(source, qualified_match=lambda _module, member: member == "resolve_path")


def _has_literal(node: ast.AST, *, exact_out: bool) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if any(lit in child.value for lit in NAME_LITERALS):
                return True
            if exact_out and child.value == OUT_LITERAL:
                return True
    return False


def _builder_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return func.id if isinstance(func, ast.Name) else None


def name_sites(source: str) -> list[tuple[int, str]]:
    """(line, qualified function) for each path-building node using a watched literal."""
    found: list[tuple[int, str]] = []

    def visit(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = child.name if scope == "<module>" else f"{scope}.{child.name}"
                visit(child, qual)
                continue
            if isinstance(child, ast.Call) and _builder_name(child) in BUILDERS:
                if any(_has_literal(a, exact_out=False) for a in (*child.args, *child.keywords)):
                    found.append((child.lineno, scope))
            elif isinstance(child, ast.BinOp) and isinstance(child.op, ast.Div):
                if _has_literal(child.right, exact_out=True):
                    found.append((child.lineno, scope))
            visit(child, scope)

    visit(ast.parse(source), "<module>")
    return found


def _allowed(entries: tuple[AllowedSite, ...]) -> dict[tuple[str, str], int]:
    return {(a.file, a.function): a.sites for a in entries}


def _name_tally(root: Path) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel in PLACERS:
            continue
        for _line, scope in name_sites(path.read_text(encoding="utf-8")):
            counts[(rel, scope)] = counts.get((rel, scope), 0) + 1
    return counts


def _resolve_tally(root: Path) -> dict[tuple[str, str], int]:
    return tally(root, skip="", finder=_resolve_sites)


# --- (a) resolve_path --------------------------------------------------------------------


def test_resolve_path_is_called_only_at_listed_sites() -> None:
    found, allowed = _resolve_tally(SRC), _allowed(ALLOWLIST)
    extra = {k: n for k, n in found.items() if allowed.get(k, 0) < n}
    assert not extra, f"resolve_path called outside the listed sites: {sorted(extra)}"


def test_resolve_path_allowlist_is_live_and_exact() -> None:
    found = _resolve_tally(SRC)
    stale = {k: n for k, n in _allowed(ALLOWLIST).items() if found.get(k, 0) != n}
    assert not stale, f"allowlist entries that no longer match the code: {sorted(stale)}"


def test_allowlist_has_reasons_and_unique_identities() -> None:
    assert len(_allowed(ALLOWLIST)) == len(ALLOWLIST)
    assert len(_allowed(NAME_ALLOWLIST)) == len(NAME_ALLOWLIST)
    assert all(len(a.reason) >= 15 for a in (*ALLOWLIST, *NAME_ALLOWLIST))


@pytest.mark.parametrize(
    "source",
    [
        "from decoy.cli.io import resolve_path\ndef f(p, b):\n    return resolve_path(p, b)\n",
        "from decoy.cli.io import resolve_path as rp\ndef f(p, b):\n    return rp(p, b)\n",
        "from decoy.cli._sources import resolve_path\ndef f(p, b):\n    return resolve_path(p, b)\n",
        "import decoy.cli.io as io\ndef f(p, b):\n    return io.resolve_path(p, b)\n",
    ],
)
def test_walk_sees_each_spelling_of_resolve_path(source: str) -> None:
    assert [scope for _l, scope in _resolve_sites(source)] == ["f"]


# --- (b) default names and the out folder ------------------------------------------------


def test_default_names_and_out_are_built_only_by_the_placers() -> None:
    found, allowed = _name_tally(SRC), _allowed(NAME_ALLOWLIST)
    extra = {k: n for k, n in found.items() if allowed.get(k, 0) < n}
    assert not extra, f"path built from a layout literal outside the placers: {sorted(extra)}"


SIDE_OWNER = "cli/io/_layout.py"
SIDE_FUNCTION = "side_file_name"
SIDE_TABLE = "_SIDE_SUFFIX"
SIDE_SUFFIX_TEXT = re.compile(r"\.(unmasked|detokenized|snapshot)(\.[a-z]+)+")


def side_suffix_uses(source: str) -> list[tuple[int, str]]:
    """(line, scope) of each read of the suffix table and each side-file suffix literal.

    The table's own definition and docstrings are not uses; prose that only mentions a name in
    help text is not a suffix, so only a string that is a whole suffix counts.
    """
    found: list[tuple[int, str]] = []

    def visit(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit(child, child.name if scope == "<module>" else f"{scope}.{child.name}")
                continue
            if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant):
                continue  # a docstring
            targets = (
                [child.target]
                if isinstance(child, ast.AnnAssign)
                else getattr(child, "targets", [])
            )
            if any(isinstance(t, ast.Name) and t.id == SIDE_TABLE for t in targets):
                continue  # the table's definition
            if isinstance(child, ast.Name) and child.id == SIDE_TABLE:
                found.append((child.lineno, scope))
            elif (
                isinstance(child, ast.Constant)
                and isinstance(child.value, str)
                and SIDE_SUFFIX_TEXT.fullmatch(child.value)
            ):
                found.append((child.lineno, scope))
            visit(child, scope)

    visit(ast.parse(source), "<module>")
    return found


def test_only_side_file_name_joins_a_side_file_suffix() -> None:
    """The suffix table is read, and its suffixes spelled, only inside `side_file_name`."""
    stray = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        for line, scope in side_suffix_uses(path.read_text(encoding="utf-8")):
            if (rel, scope) != (SIDE_OWNER, SIDE_FUNCTION):
                stray.append(f"{rel}:{line} in {scope}")
    assert not stray, f"a side-file suffix is used outside side_file_name: {stray}"


@pytest.mark.parametrize(
    "source",
    [
        "_SIDE_SUFFIX = {'a': '.unmasked.csv'}\ndef side_file_default(k, p):\n"
        "    return p.with_suffix(_SIDE_SUFFIX[k])\n",
        "def side_file_default(k, p, parquet):\n"
        "    return p.with_suffix('.detokenized.parquet' if parquet else '.x')\n",
    ],
)
def test_a_second_suffix_join_is_caught(source: str) -> None:
    assert [scope for _l, scope in side_suffix_uses(source)] == ["side_file_default"]


def test_no_default_name_is_built_outside_the_placers() -> None:
    """The sweep is done: the baseline is empty and stays empty."""
    assert NAME_ALLOWLIST == ()
    assert _name_tally(SRC) == {}


def test_name_allowlist_is_live_and_exact() -> None:
    found = _name_tally(SRC)
    stale = {k: n for k, n in _allowed(NAME_ALLOWLIST).items() if found.get(k, 0) != n}
    assert not stale, f"name allowlist entries that no longer match the code: {sorted(stale)}"


@pytest.mark.parametrize(
    "source",
    [
        "def f(p):\n    return p.with_suffix('.unmasked.csv')\n",
        "from pathlib import Path\ndef f(s):\n    return Path(f'{s}.masked.csv')\n",
        "def f(root):\n    return root / 'out' / 'x'\n",
        "def f(p):\n    return p.with_name('a.snapshot.json')\n",
        "def f(p):\n    return p.parent.joinpath('x.detokenized.csv')\n",
    ],
)
def test_walk_sees_each_path_building_spelling(source: str) -> None:
    assert [scope for _l, scope in name_sites(source)] == ["f"]


@pytest.mark.parametrize(
    "source",
    [
        "def f(p):\n    return p.with_suffix('.csv')\n",
        "def f(root):\n    return root / 'output'\n",
        "def f():\n    return 'we mask out the ssn'\n",
    ],
)
def test_walk_ignores_lookalikes(source: str) -> None:
    assert name_sites(source) == []


def test_a_seeded_name_build_in_a_command_is_caught() -> None:
    seeded = "def unmask(p):\n    return p.with_suffix('.unmasked.csv')\n"
    assert name_sites(seeded) == [(2, "unmask")]


# --- (c) the writers take a RunLayout ------------------------------------------------------


def _layout_annotated(source: str, writer: str) -> bool:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == writer:
            args = [*node.args.args, *node.args.kwonlyargs]
            return any(
                isinstance(a.annotation, ast.Name) and a.annotation.id == "RunLayout" for a in args
            )
    return False


@pytest.mark.parametrize("writer", WRITERS)
def test_each_writer_annotates_its_placement_parameter_as_run_layout(writer: str) -> None:
    source = (SRC / TARGETS).read_text(encoding="utf-8")
    assert _layout_annotated(source, writer)


def test_a_writer_back_on_a_base_dir_is_caught() -> None:
    seeded = "def write_targets(config_dict, outputs, base_dir: Path):\n    pass\n"
    assert not _layout_annotated(seeded, "write_targets")


# --- (d) validate's target check builds no path of its own ----------------------------------


def _target_check_builds_path(source: str) -> bool | None:
    """True when the target check skips `place_target`, builds a path or asks `os.path.isabs`.

    None when the function is missing, so a rename fails the test instead of passing it.
    """
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == TARGET_CHECK:
            names = {_builder_name(c) for c in ast.walk(node) if isinstance(c, ast.Call)}
            return "place_target" not in names or bool(names & (BUILDERS | {"isabs"}))
    return None


def test_validate_target_check_places_targets_only_through_place_target() -> None:
    source = (SRC / PREFLIGHT).read_text(encoding="utf-8")
    assert _target_check_builds_path(source) is False


@pytest.mark.parametrize(
    "body",
    [
        "out = Path(raw)",
        "out = PurePath(raw)",
        "out = layout.place_target(raw)\n    other = Path(raw)",
        "out = layout.place_target(raw) if os.path.isabs(raw) else None",
        "out = raw",
    ],
)
def test_a_direct_path_in_the_target_check_is_caught(body: str) -> None:
    seeded = f"def {TARGET_CHECK}(raw, layout):\n    {body}\n"
    assert _target_check_builds_path(seeded) is True
