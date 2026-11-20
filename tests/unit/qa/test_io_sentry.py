"""Sentry: `scripts/qa/io.py` is the only file writer in the QA tooling.

Every other QA module hands bytes to `publish_private_once` or a `StagedFile`. The scan is a
syntax-tree walk, so a call spelled `open(p, "w")`, `Path.write_text`, `os.open`, a `tempfile`
helper or a `shutil` copy in any other module is red. It also keeps the QA tools off private
product modules. Planted cases prove the scan catches each spelling.

Two library writes are out of its sight on purpose: `pq.write_table` into a `BytesIO`, and the
DuckDB database that `formats.duckdb_file` builds inside `io.private_scratch_dir()`. Neither
produces a final file; the bytes still go through `publish_private_once`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
QA = ROOT / "scripts" / "qa"
WRITE_MODE = re.compile(r"[wax+]")
OS_WRITERS = {"open", "fdopen", "replace", "rename", "truncate", "write", "link", "symlink"}
PATH_WRITERS = {"write_text", "write_bytes", "touch"}
WHOLE_MODULES = {"tempfile", "shutil"}
FRAME_WRITERS = {"to_csv", "to_parquet", "to_json", "to_pickle", "write_csv", "write_parquet"}
SQL_WRITE = re.compile(r"\bCOPY\b.*\bTO\b|\bEXPORT\s+DATABASE\b", re.I | re.S)
PRIVATE_IMPORT = re.compile(r"^decoy(\.\w+)*\._\w+")


def _mode_is_write(call: ast.Call, position: int) -> bool:
    mode = next((k.value for k in call.keywords if k.arg == "mode"), None)
    if mode is None and len(call.args) > position:
        mode = call.args[position]
    if mode is None:
        return False  # the default mode is read
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return WRITE_MODE.search(mode.value) is not None
    return True  # a mode the scan cannot read is treated as a write


def _aliases(tree: ast.AST) -> dict[str, str]:
    """Local name to the dotted thing it stands for: `import os as o` gives o -> os,
    `from os import replace as r` gives r -> os.replace."""
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                found[a.asname or a.name.split(".")[0]] = (
                    a.name if a.asname else a.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                found[a.asname or a.name] = f"{node.module}.{a.name}"
    return found


def _memory_names(tree: ast.AST) -> set[str]:
    """Names assigned an in-memory buffer, so `write_table(t, buf)` is not a file write."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn = node.value.func
            if (isinstance(fn, ast.Attribute) and fn.attr == "BytesIO") or (
                isinstance(fn, ast.Name) and fn.id == "BytesIO"
            ):
                names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def _is_memory_dest(node: ast.expr, memory: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in memory
    return (
        isinstance(node, ast.Call)
        and getattr(node.func, "attr", getattr(node.func, "id", "")) == "BytesIO"
    )


def _connect_writes(call: ast.Call, source_line: str) -> bool:
    """`x.connect(path)` creates a file unless it is `:memory:`, read-only, or marked scratch."""
    if "qa-io: scratch" in source_line:
        return False  # built inside io.private_scratch_dir(); the bytes then go through io.py
    if not call.args and not call.keywords:
        return False
    first = call.args[0] if call.args else None
    if isinstance(first, ast.Constant) and first.value == ":memory:":
        return False
    read_only = next((k.value for k in call.keywords if k.arg == "read_only"), None)
    return not (isinstance(read_only, ast.Constant) and read_only.value is True)


def write_sites(source: str) -> list[str]:
    """Every open-for-write spelling in `source`, as `line: what`."""
    tree = ast.parse(source)
    lines = source.splitlines()
    alias, memory = _aliases(tree), _memory_names(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            names = {a.name for a in node.names}
            if top in WHOLE_MODULES or (top == "os" and names & OS_WRITERS):
                found.append(f"{line}: from {node.module} import a writer")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if SQL_WRITE.search(node.value):
                found.append(f"{line}: SQL that writes a file")
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                target = alias.get(fn.id, fn.id)
                if target == "open" and _mode_is_write(node, 1):
                    found.append(f"{line}: open() for write")
                elif target.startswith("io.open") and _mode_is_write(node, 1):
                    found.append(f"{line}: io.open() for write")
            elif isinstance(fn, ast.Attribute):
                owner = (
                    alias.get(fn.value.id, fn.value.id) if isinstance(fn.value, ast.Name) else ""
                )
                if owner == "os" and fn.attr in OS_WRITERS:
                    found.append(f"{line}: os.{fn.attr}")
                elif fn.attr == "open" and owner in {"io", "codecs"} and _mode_is_write(node, 1):
                    found.append(f"{line}: {owner}.open() for write")
                elif (
                    fn.attr == "open"
                    and owner not in {"io", "codecs"}
                    and not owner.lower().endswith("opener")  # urllib: open(url), not a file
                    and _mode_is_write(node, 0)
                ):
                    found.append(f"{line}: .open() for write")
                elif owner in WHOLE_MODULES:
                    found.append(f"{line}: {owner}.{fn.attr}")
                elif fn.attr in PATH_WRITERS | FRAME_WRITERS:
                    found.append(f"{line}: .{fn.attr}()")
                elif fn.attr == "urlretrieve":
                    found.append(f"{line}: urlretrieve")
                elif fn.attr == "write_table":
                    dest = node.args[1] if len(node.args) > 1 else None
                    where = next((k.value for k in node.keywords if k.arg == "where"), dest)
                    if where is None or not _is_memory_dest(where, memory):
                        found.append(f"{line}: write_table to a path")
                elif fn.attr == "connect" and _connect_writes(node, lines[line - 1]):
                    found.append(f"{line}: .connect(path)")
    return found


def private_imports(source: str) -> list[str]:
    bad = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            bad += [a.name for a in node.names if PRIVATE_IMPORT.match(a.name)]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if PRIVATE_IMPORT.match(node.module) or (
                node.module.startswith("decoy") and any(a.name.startswith("_") for a in node.names)
            ):
                bad.append(node.module)
    return bad


def _qa_modules() -> list[Path]:
    return sorted(p for p in QA.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_module_but_io_writes_a_file() -> None:
    offenders = {
        p.relative_to(ROOT).as_posix(): sites
        for p in _qa_modules()
        if p != QA / "io.py"
        if (sites := write_sites(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}, "route these writes through scripts/qa/io.py"


def test_io_py_is_where_the_writes_are() -> None:
    # A scan that finds nothing anywhere proves nothing; io.py must light it up.
    assert len(write_sites((QA / "io.py").read_text(encoding="utf-8"))) >= 3


def test_no_qa_module_imports_a_private_product_module() -> None:
    offenders = {
        p.relative_to(ROOT).as_posix(): bad
        for p in _qa_modules()
        if (bad := private_imports(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}


@pytest.mark.parametrize(
    "snippet",
    [
        "open(p, 'w')",
        "open(p, mode='ab')",
        "open(p, 'r+')",
        "open(p, m)",
        "io.open(p, 'wb')",
        "path.open('w')",
        "path.open(mode='x')",
        "path.write_text('x')",
        "path.write_bytes(b'x')",
        "path.touch()",
        "os.open(p, os.O_WRONLY)",
        "os.replace(a, b)",
        "os.rename(a, b)",
        "tempfile.mkstemp()",
        "tempfile.NamedTemporaryFile()",
        "shutil.copyfile(a, b)",
        "shutil.move(a, b)",
        "df.to_csv(p)",
        "df.to_parquet(p)",
        "urllib.request.urlretrieve(u, p)",
        "from shutil import copy",
        "from tempfile import mkstemp",
        "from os import replace",
        "con.execute(\"COPY t TO 'x.csv'\")",
        "con.execute('EXPORT DATABASE out')",
        "import os as o\no.replace(a, b)",
        "import shutil as sh\nsh.copyfile(a, b)",
        "import tempfile as t\nt.mkstemp()",
        "from os import replace as r\nr(a, b)",
        "import io as i\ni.open(p, 'w')",
        "from io import open as o\no(p, 'wb')",
        "pq.write_table(t, 'x.parquet')",
        "pq.write_table(t, where=path)",
        "pq.write_table(t, buf)",
        "duckdb.connect(path)",
        "duckdb.connect(str(db))",
    ],
)
def test_the_scan_catches_each_spelling(snippet: str) -> None:
    assert write_sites(snippet), snippet


@pytest.mark.parametrize(
    "snippet",
    [
        "open(p)",
        "open(p, 'r')",
        "open(p, 'rb')",
        "path.open('rb')",
        "path.read_text()",
        "_OPENER.open(url, timeout=60)",
        "os.path.join(a, b)",
        "name.replace('a', 'b')",
        "urllib.request.urlopen(u)",
        "import io\nbuf = io.BytesIO()\npq.write_table(t, buf, compression='NONE')",
        "buf = BytesIO()\npq.write_table(t, buf)",
        "pq.write_table(t, io.BytesIO())",
        "duckdb.connect(':memory:')",
        "duckdb.connect(str(db), read_only=True)",
        "duckdb.connect(str(db))  # qa-io: scratch",
        "import os as o\no.path.join(a, b)",
    ],
)
def test_the_scan_leaves_reads_alone(snippet: str) -> None:
    assert write_sites(snippet) == [], snippet


@pytest.mark.parametrize(
    "snippet",
    [
        "from decoy._atomic import write_atomic",
        "import decoy._private_file",
        "from decoy.cli.io._paths import x",
        "from decoy import _atomic",
    ],
)
def test_the_private_import_scan_catches_each_spelling(snippet: str) -> None:
    assert private_imports(snippet), snippet


def test_the_private_import_scan_leaves_public_imports_alone() -> None:
    assert private_imports("from decoy.cli.exit_codes import EXIT_OK\nimport decoy\n") == []
