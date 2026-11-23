"""GEN-FIT-SHAPE C1: both CSV writers print Arrow integers with nulls as integers.

`pyarrow.Table.to_pandas()` widens an integer column that holds a null to float64, so the cell
text becomes `23.0`. Both CSV writers now hand the Arrow table to `pyarrow.csv` (CSV-WRITE-FAST),
which prints each integer type, signed or unsigned, as its integer. The `_csv_frame` dtype checks
became read-back checks: a typed read of the written file gives the same nullable integer values.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pytest

from decoy.cli.io._layout import RunLayout
from decoy.cli.io._targets import write_chunked_output, write_table

_BIG = 2**64 - 1


def _table() -> pa.Table:
    return pa.table(
        {
            "i8": pa.array([1, None, -3], pa.int8()),
            "i64": pa.array([23, None, -7], pa.int64()),
            "u8": pa.array([1, None, 255], pa.uint8()),
            "u64": pa.array([_BIG, None, 2**63 + 1], pa.uint64()),
            "flag": pa.array([True, None, False], pa.bool_()),
            "price": pa.array([1.5, None, 2.0], pa.float64()),
            "name": pa.array(["a", None, "c"], pa.string()),
        }
    )


def _cells(path: Path, column: str) -> list[str]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [row[column] for row in csv.DictReader(fh)]


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("i8", "Int8"),
        ("i64", "Int64"),
        ("u8", "UInt8"),
        ("u64", "UInt64"),
    ],
)
def test_written_csv_reads_back_as_each_integer_type(
    tmp_path: Path, column: str, expected: str
) -> None:
    out = tmp_path / "t.csv"
    write_table(_table(), "csv", out)
    got = pd.read_csv(out, dtype={column: expected})[column]
    assert str(got.dtype) == expected
    assert got.tolist() == _table().column(column).to_pandas(types_mapper=pd.ArrowDtype).tolist()


def test_written_csv_keeps_non_integer_values(tmp_path: Path) -> None:
    out = tmp_path / "t.csv"
    write_table(_table(), "csv", out)
    got = pd.read_csv(out, dtype={"flag": "boolean"})
    assert got["flag"].tolist() == [True, pd.NA, False]
    assert got["price"].tolist()[0::2] == [1.5, 2.0]
    assert got["name"].tolist()[0::2] == ["a", "c"]


def test_whole_table_write_prints_nullable_integers_without_a_decimal(tmp_path: Path) -> None:
    out = tmp_path / "t.csv"
    write_table(_table(), "csv", out)
    assert _cells(out, "i64") == ["23", "", "-7"]
    assert _cells(out, "i8") == ["1", "", "-3"]
    assert _cells(out, "u8") == ["1", "", "255"]
    assert _cells(out, "price") == ["1.5", "", "2"]


def test_whole_table_write_keeps_uint64_above_int64_exact(tmp_path: Path) -> None:
    out = tmp_path / "t.csv"
    write_table(_table(), "csv", out)
    assert _cells(out, "u64") == [str(_BIG), "", str(2**63 + 1)]


def test_chunked_write_prints_nullable_integers_without_a_decimal(tmp_path: Path) -> None:
    out = tmp_path / "t.csv"
    table = _table()
    write_chunked_output(
        iter([table.slice(0, 2), table.slice(2)]),
        "csv",
        str(out),
        RunLayout.fixed(tmp_path),
        empty_schema=None,
    )
    assert _cells(out, "i64") == ["23", "", "-7"]
    assert _cells(out, "u64") == [str(_BIG), "", str(2**63 + 1)]
