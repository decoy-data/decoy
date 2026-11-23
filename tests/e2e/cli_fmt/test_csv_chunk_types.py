"""CSV-WRITE-FAST A3: a chunked CSV target writes each chunk on its own types.

CSV carries no types. The engine's adapter makes a nullable int64 chunk float64 when it holds a
null, and reports an all-null chunk as `null`, so one column can change Arrow type between
chunks. The chunked run must exit 0 and write the same bytes as the plain run for the same input.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.csv_sources import file_source
from tests.keyed_secret import TEST_MASK_SECRET_REF

pytestmark = pytest.mark.usefixtures("mask_secret")

runner = CliRunner()

_ROWS = 6
_DAY = datetime.date(2024, 3, 1)

_CASES = {
    # Nulls only in the last chunk (chunk size 2): chunks 1 and 2 are int64, chunk 3 float64.
    "int64-null-in-a-later-chunk": pa.array([1, 2, 3, 4, None, 6], pa.int64()),
    # Chunk 1 is all null, so the engine reports `null` there and int64 or float64 after it.
    "int64-null-in-all-of-chunk-1": pa.array([None, None, 3, 4, 5, 6], pa.int64()),
    "date32-null-in-all-of-chunk-1": pa.array(
        [None, None] + [_DAY + datetime.timedelta(days=i) for i in range(4)], pa.date32()
    ),
}


def _config(tmp_path: Path, column: pa.Array, out: Path) -> Path:
    src = tmp_path / "in.parquet"
    pq.write_table(
        pa.table({"id": [f"id{i}" for i in range(_ROWS)], "v": column}),
        src,
    )
    cfg = {
        "version": 2,
        "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
        "sources": {"t": file_source(src, "parquet")},
        "tables": [
            {
                "name": "t",
                "columns": [
                    {"name": "id", "strategy": "hash", "namespace": "id_ns"},
                    {"name": "v", "strategy": "passthrough"},
                ],
            }
        ],
        "targets": {"t": {"type": "file", "format": "csv", "path": str(out)}},
    }
    path = tmp_path / f"{out.stem}.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


@pytest.mark.parametrize("column", _CASES.values(), ids=_CASES.keys())
def test_chunked_csv_bytes_equal_the_plain_run(tmp_path: Path, column: pa.Array) -> None:
    plain = tmp_path / "plain.csv"
    chunked = tmp_path / "chunked.csv"
    first = runner.invoke(app, ["run", str(_config(tmp_path, column, plain))])
    assert first.exit_code == 0, first.output
    second = runner.invoke(
        app, ["run", str(_config(tmp_path, column, chunked)), "--chunked", "--chunk-size", "2"]
    )
    assert second.exit_code == 0, second.output
    assert chunked.read_bytes() == plain.read_bytes()
    assert chunked.read_bytes().startswith(b'"id","v"\n')
    assert chunked.read_bytes().count(b"\n") == _ROWS + 1
