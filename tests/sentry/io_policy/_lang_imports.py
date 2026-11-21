"""Scanner for who may reach the language package and the loader's private names.

Every read of a pipeline file goes through `decoy._config_file`, so the compiler is reached from
exactly three places and each may take exact names (plan 2026-11-19-decoy-language-commands.md,
"Choke points and guards"). A use is a pair `(importer module, imported name)`:

* `import decoy.lang as L`, `from decoy import lang` and `from decoy.lang import *` bind the whole
  module, so they are the names `<module>` and `*` and no importer may have them;
* `from decoy.lang import x`, and `decoy.lang.x(...)` after `import decoy`, are `x`;
* `__import__("decoy.lang...")` and `importlib.import_module("decoy.lang...")` are `<dynamic>`;
* any `decoy.lang._private` module is its own module name, never allowed.

The package's own modules are not scanned. Named limit: a module name assembled at run time.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "decoy"
LANG = "decoy.lang"
OWNER = "decoy._config_file"

# importer module prefix -> (names it may take from `decoy.lang`, the one function that may, or None)
IMPORT_PAIRS: dict[str, tuple[frozenset[str], str | None]] = {
    OWNER: (frozenset({"lower_text", "LangError"}), None),
    "decoy.cli.lang": (
        frozenset(
            {"format_text", "convert_config", "emit_yaml", "ConvertError", "LangError", "render"}
        ),
        None,
    ),
    "decoy.ci.rule_codes": (frozenset({"CODES"}), "validation_codes"),
}


def module_of(rel: str) -> str:
    parts = Path(rel).with_suffix("").parts
    return ".".join(("decoy", *(p for p in parts if p != "__init__")))


class _Walk(ast.NodeVisitor):
    def __init__(self) -> None:
        self.found: set[tuple[str, str, str]] = set()  # (module, name, enclosing function)
        self.scope: list[str] = []
        self.decoy_names: set[str] = set()

    def _add(self, module: str, name: str) -> None:
        if module == LANG or module.startswith(LANG + "."):
            self.found.add((module, name, self.scope[-1] if self.scope else ""))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "decoy" and alias.asname is None:
                self.decoy_names.add("decoy")
            elif alias.name == "decoy":
                self.decoy_names.add(alias.asname or "decoy")
            self._add(alias.name, "<module>")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            if module == "decoy" and alias.name == "lang":
                self._add(LANG, "<module>")
            elif module == LANG or module.startswith(LANG + "."):
                self._add(module, "*" if alias.name == "*" else alias.name)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        first = node.args[0] if node.args else None
        if (
            name in {"__import__", "import_module"}
            and isinstance(first, ast.Constant)
            and isinstance(first.value, str)
        ):
            self._add(first.value, "<dynamic>")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        inner = node.value
        if (
            isinstance(inner, ast.Attribute)
            and inner.attr == "lang"
            and isinstance(inner.value, ast.Name)
            and inner.value.id in self.decoy_names
        ):
            self._add(LANG, node.attr)
        self.generic_visit(node)


def uses_in_source(source: str) -> set[tuple[str, str, str]]:
    """`(module, name, function)` for every reach into `decoy.lang` in one file."""
    walker = _Walk()
    walker.visit(ast.parse(source))
    return walker.found


def private_loader_imports(source: str) -> set[str]:
    """Each `_` name taken from `decoy._config_file` by one file."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module == OWNER:
            names |= {a.name for a in node.names if a.name.startswith("_") or a.name == "*"}
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "_config_file" and node.attr.startswith("_"):
                names.add(node.attr)
    return names


def is_allowed(importer: str, module: str, name: str, function: str) -> bool:
    for prefix, (names, only_in) in IMPORT_PAIRS.items():
        if importer == prefix or importer.startswith(prefix + "."):
            return module == LANG and name in names and (only_in is None or function == only_in)
    return False


def violations(src: Path = SRC) -> list[str]:
    out: list[str] = []
    for path in sorted(src.rglob("*.py")):
        rel = path.relative_to(src).as_posix()
        importer = module_of(rel)
        if importer == LANG or importer.startswith(LANG + ".") or "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        out += [
            f"{rel}: {m}.{n} in {f or 'module scope'}"
            for m, n, f in sorted(uses_in_source(source))
            if not is_allowed(importer, m, n, f)
        ]
        if importer != OWNER:
            out += [
                f"{rel}: private loader name {n}" for n in sorted(private_loader_imports(source))
            ]
    return out
