"""G-LIB-FS: only `cli/library/_fs.py` removes, renames or writes a file in the library package.

Following a link out of the library on delete, write or read was found four times (#210 repair,
#214 scratch delete, #215 ref write, #219 prune and clean). The fix is one module that checks
every path component with `lstat`, opens folders no-follow and refuses anything outside the
root; this sentry keeps every other library module from going around it.

Banned outside `_fs.py`, by any spelling the AST shows: `os.unlink`, `os.remove`, `os.rmdir`,
`os.rename`, `os.replace`, `shutil.rmtree`, `shutil.move`, `Path.unlink`, `Path.rmdir`,
`Path.rename`, `Path.write_text`, `Path.write_bytes`, and `open(...)` or `Path.open(...)` with a
mode that writes (`w`, `a`, `x` or `+`). No allowlist: a hit is a defect.

Named limits: a name bound at run time (`getattr(os, "unlink")`) and an alias by assignment
(`u = os.unlink`) are not seen; `.replace(...)` on a `Path` is not told apart from `str.replace`,
so `os.replace` is the spelling caught.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "src" / "decoy" / "cli" / "library"
OWNER = "_fs.py"

_MODULE_CALLS = {
    "os": {"unlink", "remove", "rmdir", "rename", "replace"},
    "shutil": {"rmtree", "move"},
}
_METHODS = {"unlink", "rmdir", "rename", "write_text", "write_bytes"}
_WRITE_MODES = set("wax+")


def _imported_names(tree: ast.AST) -> dict[str, str]:
    """Local name -> `module.attr` for `from os import unlink [as u]` style imports."""
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in _MODULE_CALLS:
            for alias in node.names:
                if alias.name in _MODULE_CALLS[node.module]:
                    names[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return names


def _module_aliases(tree: ast.AST) -> dict[str, str]:
    """Local name -> module for `import os [as o]` and `import shutil [as s]`."""
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _MODULE_CALLS:
                    found[alias.asname or alias.name] = alias.name
    return found


def _writes_mode(call: ast.Call, position: int) -> bool:
    mode: ast.expr | None = None
    if len(call.args) > position:
        mode = call.args[position]
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = kw.value
    if mode is None:
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return bool(_WRITE_MODES & set(mode.value))
    return True  # a mode the scan cannot read is treated as a write


def offenders(source: str) -> list[tuple[int, str]]:
    """Every banned call in `source`: (line, spelling)."""
    tree = ast.parse(source)
    imported = _imported_names(tree)
    modules = _module_aliases(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in imported:
                found.append((node.lineno, imported[func.id]))
            elif func.id == "open" and _writes_mode(node, 1):
                found.append((node.lineno, "open(write)"))
        elif isinstance(func, ast.Attribute):
            owner = func.value
            if isinstance(owner, ast.Name) and owner.id in modules:
                module = modules[owner.id]
                if func.attr in _MODULE_CALLS[module]:
                    found.append((node.lineno, f"{module}.{func.attr}"))
                continue
            if func.attr in _METHODS:
                found.append((node.lineno, f"Path.{func.attr}"))
            elif func.attr == "open" and _writes_mode(node, 0):
                found.append((node.lineno, "Path.open(write)"))
    return sorted(found)


def _package_sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(PACKAGE.glob("*.py"))}


def test_only_the_fs_module_removes_renames_or_writes() -> None:
    sources = _package_sources()
    assert OWNER in sources and "_store.py" in sources  # non-vacuous: the package was scanned
    hits = {
        name: found
        for name, text in sources.items()
        if name != OWNER and (found := offenders(text))
    }
    assert hits == {}, "a library module touches the filesystem around _fs.py"


def test_the_fs_module_is_where_the_removals_live() -> None:
    """Control: the scan sees the owner's own calls, so an empty result elsewhere means none."""
    spellings = {s for _line, s in offenders(_package_sources()[OWNER])}
    assert {"os.unlink", "os.rmdir"} <= spellings


SEEDED = """
import os
import os as o
import shutil
from os import replace as swap
from pathlib import Path

def bad(p: Path, q: Path) -> None:
    os.unlink(p)
    o.remove(p)
    shutil.rmtree(p)
    swap(p, q)
    p.unlink()
    p.rmdir()
    p.rename(q)
    p.write_text("x")
    p.write_bytes(b"x")
    open(p, "w")
    open(p, mode="ab")
    p.open("r+")
    os.replace(p, q)

def fine(p: Path) -> None:
    open(p)
    open(p, "rb")
    p.open()
    p.read_bytes()
    "a".replace("a", "b")
    os.open(p, os.O_RDONLY)
"""


def test_the_scan_fires_on_every_seeded_spelling() -> None:
    found = [spelling for _line, spelling in offenders(SEEDED)]
    assert found == [
        "os.unlink",
        "os.remove",
        "shutil.rmtree",
        "os.replace",
        "Path.unlink",
        "Path.rmdir",
        "Path.rename",
        "Path.write_text",
        "Path.write_bytes",
        "open(write)",
        "open(write)",
        "Path.open(write)",
        "os.replace",
    ]


def test_a_seeded_module_in_the_package_would_fail_the_rule() -> None:
    """The package rule itself fires: a seeded `_seeded.py` with one bare unlink is a hit."""
    sources = {**_package_sources(), "_seeded.py": "import os\nos.unlink('x')\n"}
    hits = {n: f for n, t in sources.items() if n != OWNER and (f := offenders(t))}
    assert hits.get("_seeded.py") == [(2, "os.unlink")]
