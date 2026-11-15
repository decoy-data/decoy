"""The `library` commands go through the package facade (review round 1 on #210, DESIGN 9).

CODEMAP: commands import `decoy.cli.library`, never its `_` modules. G-LIB-WRITER W1 holds that
outside the package; this holds it for the command modules inside it (every module that imports
`typer`), in each of `import a._x`, `from a._x import y` and `from a import _x`.
"""

from __future__ import annotations

import ast

from tests.unit.library._helpers import ROOT

import decoy.cli.library as facade

PACKAGE = ROOT / "src" / "decoy" / "cli" / "library"
PREFIX = "decoy.cli.library"


def private_imports(source: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.startswith(f"{PREFIX}._")]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith(f"{PREFIX}._"):
                found.append(node.module)
            elif node.module == PREFIX:
                found += [f"{PREFIX}.{a.name}" for a in node.names if a.name.startswith("_")]
    return sorted(found)


def _command_modules() -> dict[str, str]:
    sources = {p.name: p.read_text(encoding="utf-8") for p in PACKAGE.glob("*.py")}
    return {n: t for n, t in sources.items() if "import typer" in t}


def test_command_modules_import_only_the_facade() -> None:
    modules = _command_modules()
    assert "_commands.py" in modules  # non-vacuous: the command module was found
    hits = {n: f for n, t in modules.items() if (f := private_imports(t))}
    assert hits == {}


def test_the_guard_sees_every_spelling() -> None:
    seeded = (
        "import decoy.cli.library._fsck\n"
        "from decoy.cli.library._errors import LibraryError\n"
        "from decoy.cli.library import _paths, open_library\n"
    )
    assert private_imports(seeded) == [
        "decoy.cli.library._errors",
        "decoy.cli.library._fsck",
        "decoy.cli.library._paths",
    ]


def test_the_facade_names_what_the_commands_use() -> None:
    for name in ("LibraryError", "check_root_budget", "fsck_check", "fsck_repair", "resolve_root"):
        assert name in facade.__all__
        assert getattr(facade, name) is not None
