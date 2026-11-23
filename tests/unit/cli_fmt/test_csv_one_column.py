"""CSV-WRITE-FAST A2.1: a one-column table keeps every row on a round trip.

A CSV row with one empty field is a blank line, and CSV readers skip blank lines, so a null in a
one-column table used to lose its row (40 rows read back as 22). A batch with one column writes
every null as `""`; the tests read the file back with the CLI reader and with pandas.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pytest
from tests.csv_sources import csv_source

from decoy.cli._sources import read_csv_frame
from decoy.cli.io import RunLayout, write_chunked_output, write_table

_ROWS = 40


def _cases() -> dict[str, pa.Array]:
    return {
        "int": pa.array([None if i % 2 else i for i in range(_ROWS)], pa.int64()),
        "string": pa.array([None if i % 3 == 0 else f"v{i}" for i in range(_ROWS)], pa.string()),
        "all_null": pa.nulls(_ROWS),
        "float": pa.array([None if i % 2 else i / 4 for i in range(_ROWS)], pa.float64()),
        "dictionary": pa.array([None if i % 2 else "x" for i in range(_ROWS)]).dictionary_encode(),
    }


def _written(table: pa.Table, tmp_path: Path, how: str) -> Path:
    out = tmp_path / f"{how}.csv"
    if how == "whole":
        write_table(table, "csv", out)
    else:
        write_chunked_output(
            iter(table.slice(i, 7) for i in range(0, table.num_rows, 7)),
            "csv",
            str(out),
            RunLayout.fixed(tmp_path),
            empty_schema=None,
        )
    return out


@pytest.mark.parametrize("how", ["whole", "chunked"])
@pytest.mark.parametrize("case", sorted(_cases()))
def test_every_row_reads_back(tmp_path: Path, case: str, how: str) -> None:
    array = _cases()[case]
    out = _written(pa.table({"c": array}), tmp_path, how)
    nulls = [v is None for v in array.to_pylist()]
    for frame in (
        read_csv_frame("t", csv_source(out), tmp_path, dtype=str),
        read_csv_frame("t", csv_source(out), tmp_path, dtype=None),
        pd.read_csv(out),
        pd.read_csv(out, dtype=str),
    ):
        assert len(frame) == _ROWS, (case, how)
        assert frame["c"].isna().tolist() == nulls, (case, how)


def test_non_null_cells_of_a_one_column_table_keep_their_values(tmp_path: Path) -> None:
    out = _written(pa.table({"c": _cases()["int"]}), tmp_path, "whole")
    frame = pd.read_csv(out)
    assert frame["c"].dropna().astype("int64").tolist() == [i for i in range(_ROWS) if i % 2 == 0]


def test_a_table_with_two_columns_is_unchanged(tmp_path: Path) -> None:
    out = tmp_path / "two.csv"
    write_table(pa.table({"k": [1, 2], "c": pa.array([None, 5], pa.int64())}), "csv", out)
    assert out.read_bytes() == b'"k","c"\n1,\n2,5\n'


def test_one_column_nulls_are_written_as_an_empty_quoted_string(tmp_path: Path) -> None:
    out = tmp_path / "one.csv"
    write_table(pa.table({"c": pa.array([1, None, 3], pa.int64())}), "csv", out)
    assert out.read_bytes() == b'"c"\n"1"\n""\n"3"\n'
