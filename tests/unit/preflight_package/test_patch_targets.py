"""No test patches an attribute on the `decoy.cli.preflight` package itself.

The package keeps names the old module bound, but the moved code reads them from its own
submodules, so a patch on the package sets an attribute nothing reads and the test still
passes. Patch targets must name the submodule that holds the code.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = "decoy.cli.preflight"
PATCH_CALLS = frozenset({"patch", "setattr", "object"})
TESTS = Path(__file__).resolve().parents[2]


def _package_aliases(tree: ast.AST) -> set[str]:
    """Local names bound to the package itself, not to one of its submodules."""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases |= {a.asname for a in node.names if a.name == PACKAGE and a.asname}
        elif isinstance(node, ast.ImportFrom) and node.module == "decoy.cli":
            aliases |= {a.asname or a.name for a in node.names if a.name == "preflight"}
    return aliases


def _is_str(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def package_patch_targets(source: str) -> list[str]:
    """Patch targets in `source` that name an attribute directly on the package."""
    tree = ast.parse(source)
    aliases = _package_aliases(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            first = node.args[0] if node.args else None
            if name in PATCH_CALLS and first is not None and _is_str(first):
                value = first.value  # type: ignore[attr-defined]
                head, _, attr = value.rpartition(".")
                if head == PACKAGE and attr:
                    found.append(value)
            pair = node.args[:2]
        elif isinstance(node, ast.Tuple):
            pair = node.elts[:2]
        else:
            continue
        if len(pair) == 2 and isinstance(pair[0], ast.Name) and pair[0].id in aliases:
            if _is_str(pair[1]):
                found.append(f"{pair[0].id}.{pair[1].value}")  # type: ignore[attr-defined]
    return found


MUST_FLAG = {
    "dotted string": (
        "def t(monkeypatch):\n"
        '    monkeypatch.setattr("decoy.cli.preflight.load_config_mapping", fake)\n'
    ),
    "module object, import as": (
        "import decoy.cli.preflight as preflight\n"
        "def t(monkeypatch):\n"
        '    monkeypatch.setattr(preflight, "load_config_mapping", fake)\n'
    ),
    "module object, from import": (
        "from decoy.cli import preflight\n"
        "from unittest import mock\n"
        "def t():\n"
        '    mock.patch.object(preflight, "capacity_codes")\n'
    ),
    "tuple": ('from decoy.cli import preflight as pf\nSPIES = [(pf, "_check_capacity")]\n'),
}
MUST_PASS = {
    "submodule object": (
        "from decoy.cli.preflight import readiness\n"
        "def t(monkeypatch):\n"
        '    monkeypatch.setattr(readiness, "_check_capacity", fake)\n'
    ),
    "submodule dotted string": (
        "def t(monkeypatch):\n"
        '    monkeypatch.setattr("decoy.cli.preflight._command.load_config_mapping", fake)\n'
    ),
    "submodule imported as preflight": (
        "from decoy.cli.preflight import readiness as preflight\n"
        'SPIES = [(preflight, "_check_capacity")]\n'
    ),
}


@pytest.mark.parametrize("label", sorted(MUST_FLAG))
def test_the_scan_flags_a_patch_on_the_package(label: str) -> None:
    assert package_patch_targets(MUST_FLAG[label]), label


@pytest.mark.parametrize("label", sorted(MUST_PASS))
def test_the_scan_passes_a_patch_on_a_submodule(label: str) -> None:
    assert package_patch_targets(MUST_PASS[label]) == [], label


def test_no_test_patches_the_package_itself() -> None:
    hits = {}
    for path in sorted(TESTS.rglob("*.py")):
        try:
            found = package_patch_targets(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        if found:
            hits[str(path.relative_to(TESTS))] = found
    assert hits == {}
