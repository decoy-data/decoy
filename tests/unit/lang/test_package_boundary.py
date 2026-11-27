"""The compiler is self-contained, so it can move to another package without a rewrite.

Nothing inside `decoy.lang` imports from the rest of `decoy` except the bottom-tier `_source_positions`. Every module imports the engine's
public API, Lark, PyYAML and its own siblings. The loader (`decoy._config_file`) imports the
package, never the other way, and the import-layer contract keeps `lang` below it.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE = Path(__file__).resolve().parents[3] / "src" / "decoy" / "lang"
# The one shared position rule: `_validate` finds the construct for an engine path with the same
# lookup `DecoyPositionIndex` uses, so the two cannot disagree.
ALLOWED: set[tuple[str, str]] = {("_validate.py", "decoy._source_positions")}


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


def test_the_package_imports_nothing_else_from_decoy() -> None:
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
