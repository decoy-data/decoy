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


def write_sites(source: str) -> list[str]:
    """Every open-for-write spelling in `source`, as `line: what`."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
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
            if isinstance(fn, ast.Name) and fn.id == "open" and _mode_is_write(node, 1):
                found.append(f"{line}: open() for write")
            elif isinstance(fn, ast.Attribute):
                owner = fn.value.id if isinstance(fn.value, ast.Name) else ""
                if owner == "os" and fn.attr in OS_WRITERS:
                    found.append(f"{line}: os.{fn.attr}")
                elif fn.attr == "open" and owner in {"io", "codecs"} and _mode_is_write(node, 1):
                    found.append(f"{line}: {owner}.open() for write")
                elif (
                    fn.attr == "open" and owner not in {"io", "codecs"} and _mode_is_write(node, 0)
                ):
                    found.append(f"{line}: .open() for write")
                elif owner in WHOLE_MODULES:
                    found.append(f"{line}: {owner}.{fn.attr}")
                elif fn.attr in PATH_WRITERS | FRAME_WRITERS:
                    found.append(f"{line}: .{fn.attr}()")
                elif fn.attr == "urlretrieve":
                    found.append(f"{line}: urlretrieve")
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
        "os.path.join(a, b)",
        "name.replace('a', 'b')",
        "urllib.request.urlopen(u)",
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
