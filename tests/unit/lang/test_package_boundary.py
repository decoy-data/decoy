"""The compiler is self-contained, so it can move to another package without a rewrite.

Inside `decoy.lang` only the command-line entry (`__main__`) imports from the rest of `decoy`,
and only the shared config-file reader. Every other module imports the engine's public API,
Lark, PyYAML and its own siblings.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE = Path(__file__).resolve().parents[3] / "src" / "decoy" / "lang"
ALLOWED = {("__main__.py", "decoy._config_file")}


def decoy_imports(source: str) -> set[str]:
    """Every `decoy.*` module a source file imports from outside `decoy.lang`."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        names = []
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        elif isinstance(node, ast.ImportFrom):
            names = ["decoy.lang"]  # a relative import stays inside the package
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        for name in names:
            inside = name == "decoy.lang" or name.startswith("decoy.lang.")
            if (name == "decoy" or name.startswith("decoy.")) and not inside:
                found.add(name)
    return found


def test_only_the_entry_point_imports_the_rest_of_the_cli() -> None:
    found = {
        (path.name, name)
        for path in sorted(_PACKAGE.glob("*.py"))
        for name in decoy_imports(path.read_text(encoding="utf-8"))
    }
    assert found == ALLOWED


def test_the_walk_sees_each_import_spelling() -> None:
    assert decoy_imports("from decoy.ui.output import emit_error") == {"decoy.ui.output"}
    assert decoy_imports("import decoy.cli.io as io") == {"decoy.cli.io"}
    assert decoy_imports("def f():\n    from decoy import api") == {"decoy"}
    assert decoy_imports("from decoy.lang._errors import fail\nimport lark") == set()
