"""G-ONE-SCAN-CALL: one function calls the engine scan and the profile entry points.

Walks every module under `src/decoy/` for any reference to `scan_sources`, `scan_set_to_dict` or
`profile_columns` that resolves to `decoy_engine` (a call, an attribute access, an import, with
or without an alias). The owner is `cli/scanning/_engine_call.py::scan_descriptors`. Any other
site fails unless its `file::function` is in the `scan-call-allow` baseline, which may shrink and
never grow. Two routes sharing one call is what keeps `decoy scan`, `decoy demo` and
`decoy.scan()` from drifting apart.

Named limits: a call through a runtime-bound name (`getattr(decoy_engine, "scan_sources")`), an
alias by assignment, and `from decoy_engine import *`.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.sentry._ratchet import load_allowlist
from tests.sentry.io_policy._calls import sites

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"
OWNER = "cli/scanning/_engine_call.py"
TRACKED = frozenset({"scan_sources", "scan_set_to_dict", "profile_columns"})
ALLOWED: dict[str, dict] = load_allowlist("scan-call-allow")


def _tracked(dotted: str | None) -> bool:
    return (
        dotted is not None
        and dotted.split(".")[0] == "decoy_engine"
        and dotted.rpartition(".")[2] in TRACKED
    )


def _import_scopes(tree: ast.AST) -> set[str]:
    """Scopes holding `from decoy_engine[.x] import <tracked>`, named like `sites` names them."""
    found: set[str] = set()

    def visit(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = scope
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                inner = child.name if scope == "<module>" else f"{scope}.{child.name}"
            if (
                isinstance(child, ast.ImportFrom)
                and child.module
                and not child.level
                and child.module.split(".")[0] == "decoy_engine"
                and any(a.name in TRACKED for a in child.names)
            ):
                found.add(scope)
            visit(child, inner)

    visit(tree, "<module>")
    return found


def hits(source: str) -> set[str]:
    """The scopes in one module that reach a tracked engine function, in any spelling."""
    tree = ast.parse(source)
    scopes = {s.scope for s in sites(tree) if _tracked(s.name)}
    return scopes | _import_scopes(tree)


def _walk() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        scopes = hits(path.read_text(encoding="utf-8"))
        if scopes:
            found[path.relative_to(SRC).as_posix()] = scopes
    return found


def test_only_the_owner_and_the_allowlist_reach_the_engine_scan() -> None:
    found = _walk()
    stray = sorted(
        f"{rel}::{scope}"
        for rel, scopes in found.items()
        if rel != OWNER
        for scope in scopes
        if f"{rel}::{scope}" not in ALLOWED
    )
    assert stray == []


def test_the_walk_is_not_empty_and_finds_the_owner() -> None:
    assert _walk().get(OWNER) == {"scan_descriptors"}


def test_every_allowlist_entry_is_still_live() -> None:
    live = {f"{rel}::{scope}" for rel, scopes in _walk().items() for scope in scopes}
    assert set(ALLOWED) - live == set()


def test_allowlist_holds_exactly_the_c1_entries() -> None:
    assert set(ALLOWED) == {"cli/init.py::_scaffold_from_file", "api.py::scan"}
    assert all(len(e["reason"]) >= 15 for e in ALLOWED.values())


# -- self-tests: each spelling is found --------------------------------------------------------

_SPELLINGS = {
    "from import call": "from decoy_engine import scan_sources\ndef f():\n    scan_sources({})\n",
    "import only": "def f():\n    from decoy_engine import scan_set_to_dict\n",
    "alias": "from decoy_engine import profile_columns as pc\ndef f():\n    pc(1)\n",
    "module alias": "import decoy_engine as de\ndef f():\n    de.scan_sources({})\n",
    "submodule from": (
        "from decoy_engine.profiling import scan_set_to_dict\ndef f():\n    scan_set_to_dict(1)\n"
    ),
    "submodule attribute": (
        "import decoy_engine.profiling.scan_set as s\ndef f():\n    s.scan_sources({})\n"
    ),
    "value reference": "import decoy_engine as de\ndef f():\n    return de.profile_columns\n",
}


def test_each_spelling_is_found() -> None:
    for label, source in _SPELLINGS.items():
        assert hits(source), label


def test_other_engine_names_and_other_packages_are_not_found() -> None:
    assert not hits("from decoy_engine import mask_frame\ndef f():\n    mask_frame()\n")
    assert not hits("import other as o\ndef f():\n    o.scan_sources({})\n")
