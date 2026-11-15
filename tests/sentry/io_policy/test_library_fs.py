"""G-LIB-FS: only `cli/library/_fs.py` touches the filesystem in the library package.

Following a link out of the library on delete, write or read was found four times (#210 repair,
#214 scratch delete, #215 ref write, #219 prune and clean), and once more through checks that
read the filesystem directly (#210 round 2: `Path.is_dir()` on `library/`, `is_file()` on an
object, the SQLite index opened by path). The fix is one module that checks every path
component with `lstat` and refuses anything outside the root; this sentry keeps every other
module in the package, at any depth, from going around it.

Banned outside `_fs.py`, by any spelling the AST shows:

- removes, renames and writes: `os.unlink`, `os.remove`, `os.rmdir`, `os.rename`, `os.replace`,
  `shutil.rmtree`, `shutil.move`, `shutil.copy`, `shutil.copy2`, `shutil.copyfile`,
  `shutil.copytree`, `Path.unlink`, `Path.rmdir`, `Path.rename`, `Path.replace` (one positional
  argument; `str.replace` takes two, `datetime.replace` keywords), `Path.write_text`, `Path.write_bytes`, `Path.touch`, `Path.mkdir`,
  and `open(...)` or `Path.open(...)` with a mode that writes;
- inspection, which follows links: `os.stat`, `os.lstat`, `os.scandir`, `os.listdir`,
  `os.walk`, `os.path.exists`, `isdir`, `isfile`, `islink`, `lexists`, `realpath`, `getsize`,
  and `Path.exists`, `is_dir`, `is_file`, `is_symlink`, `stat`, `lstat`, `iterdir`, `glob`,
  `rglob`, `resolve` (with no positional argument; `Library.resolve(text)` is an id lookup);
- the repo's own file helpers: `write_atomic`, `write_local_target`, `open_private`,
  `create_private_directory`, `create_exclusive`, `read_small_file`, `sqlite3.connect`.

No allowlist: SQLite opens its database by path, so `_fs` owns those opens too
(`open_database`, `open_database_readonly`), each judging the path first (`checked_file`).

Named limits: a name bound at run time (`getattr(os, "unlink")`) and an alias by assignment
(`u = os.unlink`) are not seen.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "src" / "decoy" / "cli" / "library"
OWNER = "_fs.py"

_MODULE_CALLS = {
    "os": {
        "unlink", "remove", "rmdir", "rename", "replace", "stat", "lstat", "scandir",
        "listdir", "walk",
    },
    "os.path": {"exists", "isdir", "isfile", "islink", "lexists", "realpath", "getsize"},
    "shutil": {"rmtree", "move", "copy", "copy2", "copyfile", "copytree"},
    "sqlite3": {"connect"},
}  # fmt: skip
_METHODS = {
    "unlink", "rmdir", "rename", "write_text", "write_bytes", "touch", "mkdir", "exists",
    "is_dir", "is_file", "is_symlink", "stat", "lstat", "iterdir", "glob", "rglob", "resolve",
}  # fmt: skip
_HELPERS = {
    "write_atomic", "write_local_target", "open_private", "create_private_directory",
    "create_exclusive", "read_small_file",
}  # fmt: skip
_WRITE_MODES = set("wax+")


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _dotted(node.value)
        return None if inner is None else f"{inner}.{node.attr}"
    return None


def _aliases(tree: ast.AST) -> tuple[dict[str, str], dict[str, str]]:
    """(local module name -> module, local function name -> `module.func` or helper name)."""
    modules: dict[str, str] = {}
    functions: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _MODULE_CALLS:
                    modules[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local = alias.asname or alias.name
                if alias.name in _MODULE_CALLS.get(node.module, ()):
                    functions[local] = f"{node.module}.{alias.name}"
                elif alias.name in _HELPERS:
                    functions[local] = alias.name
                elif node.module == "os" and alias.name == "path":
                    modules[local] = "os.path"
    return modules, functions


def _writes_mode(call: ast.Call, position: int) -> bool:
    mode: ast.expr | None = call.args[position] if len(call.args) > position else None
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
    modules, functions = _aliases(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in functions:
                found.append((node.lineno, functions[func.id]))
            elif func.id == "open" and _writes_mode(node, 1):
                found.append((node.lineno, "open(write)"))
            continue
        if not isinstance(func, ast.Attribute):
            continue
        owner = _dotted(func.value)
        module = modules.get(owner or "", owner if owner in _MODULE_CALLS else None)
        if module is not None and func.attr in _MODULE_CALLS.get(module, ()):
            found.append((node.lineno, f"{module}.{func.attr}"))
        elif module is not None:
            continue
        elif func.attr in _HELPERS:
            found.append((node.lineno, func.attr))
        elif func.attr == "resolve" and node.args:
            continue  # `Path.resolve` takes no positional argument (`Library.resolve(text)` does)
        elif func.attr in _METHODS:
            found.append((node.lineno, f"Path.{func.attr}"))
        elif func.attr == "replace" and len(node.args) == 1 and not node.keywords:
            found.append((node.lineno, "Path.replace"))
        elif func.attr == "open" and _writes_mode(node, 0):
            found.append((node.lineno, "Path.open(write)"))
    return sorted(found)


def _package_sources() -> dict[str, str]:
    return {
        p.relative_to(PACKAGE).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(PACKAGE.rglob("*.py"))
    }


def hits(sources: dict[str, str]) -> dict[str, list[tuple[int, str]]]:
    out: dict[str, list[tuple[int, str]]] = {}
    for name, text in sources.items():
        if name == OWNER:
            continue
        found = offenders(text)
        if found:
            out[name] = found
    return out


def test_only_the_fs_module_touches_the_filesystem() -> None:
    sources = _package_sources()
    assert OWNER in sources and "_store.py" in sources  # non-vacuous: the package was scanned
    assert hits(sources) == {}, "a library module touches the filesystem around _fs.py"


def test_the_fs_module_is_where_the_calls_live() -> None:
    """Control: the scan sees the owner's own calls, so an empty result elsewhere means none."""
    spellings = {s for _line, s in offenders(_package_sources()[OWNER])}
    assert {"os.unlink", "os.rmdir", "os.lstat", "write_atomic", "sqlite3.connect"} <= spellings


SEEDED = """
import os
import os as o
import shutil
import sqlite3
from os import replace as swap
from pathlib import Path
from decoy._atomic import write_atomic

def bad(p: Path, q: Path) -> None:
    os.unlink(p)
    o.remove(p)
    shutil.rmtree(p)
    swap(p, q)
    p.unlink()
    p.write_text("x")
    open(p, "w")
    p.open("r+")
    p.replace(q)
    shutil.copy2(p, q)
    write_atomic(p, "n", b"x")
    p.is_dir()
    os.path.exists(p)
    os.stat(p)
    sqlite3.connect(str(p))

def fine(p: Path, when: object, library: object) -> None:
    when.replace(tzinfo=None)
    library.resolve("abcd1234")
    open(p)
    p.open()
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
        "Path.write_text",
        "open(write)",
        "Path.open(write)",
        "Path.replace",
        "shutil.copy2",
        "write_atomic",
        "Path.is_dir",
        "os.path.exists",
        "os.stat",
        "sqlite3.connect",
    ]


def test_a_seeded_module_at_any_depth_fails_the_rule() -> None:
    """The package rule fires, for a nested module too."""
    sources = {
        **_package_sources(),
        "sub/_seeded.py": "from pathlib import Path\nPath('x').replace(Path('y'))\n",
        "_seeded2.py": "import shutil\nshutil.copy2('a', 'b')\n",
        "_seeded3.py": "from decoy._private_file import open_private\nopen_private('x')\n",
    }
    found = hits(sources)
    assert found.get("sub/_seeded.py") == [(2, "Path.replace")]
    assert found.get("_seeded2.py") == [(2, "shutil.copy2")]
    assert found.get("_seeded3.py") == [(2, "open_private")]
