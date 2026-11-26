"""G-ONE-POINTER: `LATEST` is read and written in `cli/io/_pointer.py` only.

The engine's pointer lock and compare-and-set only help if every writer goes through them. A
second module that builds a `CurrentPointer` or `LocalPointerStore`, or that opens or writes a
file named `LATEST` by itself, would race the one writer and skip its "later run id wins" rule.

Walks every module under `src/decoy/` on the shared scanner `_calls.py` and flags, outside the
allowed module:
- a call that resolves to `CurrentPointer` or `LocalPointerStore` from `decoy_engine`
  (direct, aliased, `from` import or module attribute);
- a call to a file reader or writer (`write_atomic`, `open`, `read_text`, and the like) with an
  argument that names `LATEST`: the literal `"LATEST"` or the constant `_LATEST_FILE`.

A module that only names the path, such as the run-output inventory, is not a reader or writer:
a bare reference to `_LATEST_FILE` outside such a call passes.

Named limits: a path built into a variable first (`p = folder / "LATEST"; open(p)`), `getattr`,
and `exec` are not seen. The sentry targets the spellings a contributor would write by habit.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tests.sentry.io_policy._calls import sites

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"
CHOKE_POINT = "cli/io/_pointer.py"

_POINTER_TYPES = frozenset({"CurrentPointer", "LocalPointerStore"})
_FILE_CALLS = frozenset(
    {
        "write_atomic",
        "write_local_target",
        "open",
        "read_small_file",
        "read_small_bytes",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "unlink",
        "replace",
    }
)
_LATEST_NAMES = frozenset({"_LATEST_FILE"})
_LATEST_TEXT = "LATEST"


def _names_latest(expr: ast.expr) -> bool:
    for node in ast.walk(expr):
        if isinstance(node, ast.Constant) and node.value == _LATEST_TEXT:
            return True
        if isinstance(node, ast.Name) and node.id in _LATEST_NAMES:
            return True
        if isinstance(node, ast.Attribute) and node.attr in _LATEST_NAMES:
            return True
    return False


def _call_target(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    return func.attr if isinstance(func, ast.Attribute) else None


def pointer_sites(source: str) -> list[tuple[int, str]]:
    """Return (line, what) for each call that builds a pointer or touches `LATEST`."""
    found: list[tuple[int, str]] = []
    for site in sites(ast.parse(source)):
        if not isinstance(site.node, ast.Call):
            continue
        resolved = site.name
        if resolved is not None:
            module, _dot, member = resolved.rpartition(".")
            if member in _POINTER_TYPES and (module.split(".")[0] == "decoy_engine"):
                found.append((site.lineno, member))
                continue
        target = _call_target(site.node)
        # The module's own name for the call also counts: `from x import open as o` resolves.
        member = resolved.rpartition(".")[2] if resolved else target
        if member in _FILE_CALLS and any(
            _names_latest(arg) for arg in (*site.node.args, *(k.value for k in site.node.keywords))
        ):
            found.append((site.lineno, f"{member}(LATEST)"))
        elif isinstance(site.node.func, ast.Attribute) and _names_latest(site.node.func.value):
            # `(folder / "LATEST").read_text()`: the receiver is the path.
            if site.node.func.attr in _FILE_CALLS:
                found.append((site.lineno, f"{site.node.func.attr}(LATEST)"))
    return found


def findings(rel: str, source: str) -> list[str]:
    if rel == CHOKE_POINT:
        return []
    return [f"{rel}:{line} {what}" for line, what in pointer_sites(source)]


def _tree_findings() -> list[str]:
    out: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        out += findings(rel, path.read_text(encoding="utf-8"))
    return out


def test_no_module_but_the_pointer_module_builds_or_touches_latest() -> None:
    assert _tree_findings() == []


def test_the_choke_point_is_the_pointer_module() -> None:
    assert CHOKE_POINT == "cli/io/_pointer.py"
    assert (SRC / CHOKE_POINT).is_file()


def test_the_walk_sees_the_pointer_module_itself() -> None:
    source = (SRC / CHOKE_POINT).read_text(encoding="utf-8")
    seen = {what for _line, what in pointer_sites(source)}
    assert {"CurrentPointer", "LocalPointerStore"} <= seen
    assert any(what.endswith("(LATEST)") for what in seen)


def test_a_seeded_site_in_the_layout_module_is_found() -> None:
    source = (SRC / "cli/io/_layout.py").read_text(encoding="utf-8")
    seeded = source + (
        "\n\ndef sneaky(leaf):\n"
        "    from decoy_engine.publication import LocalPointerStore\n"
        "    return LocalPointerStore(leaf)\n"
    )
    assert findings("cli/io/_layout.py", seeded) != findings("cli/io/_layout.py", source)
    assert any("LocalPointerStore" in f for f in findings("cli/io/_layout.py", seeded))


@pytest.mark.parametrize(
    "source",
    [
        "from decoy_engine.publication import LocalPointerStore\n"
        "def f(leaf):\n    return LocalPointerStore(leaf)\n",
        "from decoy_engine.publication import LocalPointerStore as Store\n"
        "def f(leaf):\n    return Store(leaf)\n",
        "import decoy_engine.publication as pub\ndef f(s, leaf):\n    return pub.CurrentPointer(s, leaf)\n",
        "import decoy_engine.publication\n"
        "def f(s, leaf):\n    return decoy_engine.publication.CurrentPointer(s, leaf)\n",
        "from decoy._atomic import write_atomic\n"
        "def f(folder, data, mode):\n    write_atomic(folder, 'LATEST', data, mode)\n",
        "from decoy._atomic import write_atomic as put\n"
        "def f(folder, data, mode):\n    put(folder, _LATEST_FILE, data, mode)\n",
        "def f(folder):\n    return open(folder / 'LATEST', 'rb')\n",
        "def f(folder):\n    return (folder / 'LATEST').read_text()\n",
    ],
)
def test_the_walk_sees_each_spelling(source: str) -> None:
    assert len(findings("cli/other.py", source)) == 1
    assert findings(CHOKE_POINT, source) == []


@pytest.mark.parametrize(
    "source",
    [
        "from decoy.cli.io._pointer import _LATEST_FILE\n"
        "def f(pipeline):\n    return [pipeline / _LATEST_FILE]\n",
        "def f(folder):\n    return folder / 'LATEST'\n",
        "def f(store):\n    return store.read()\n",
        "def f(folder):\n    return open(folder / 'other.txt')\n",
    ],
)
def test_the_walk_ignores_a_bare_name_and_lookalikes(source: str) -> None:
    assert findings("cli/other.py", source) == []
