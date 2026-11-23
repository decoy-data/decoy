"""CSV-WRITE-FAST A3 (control): what each Arrow type reads back as, new writer against pandas.

The old pandas text is rebuilt with the engine converter and `DataFrame.to_csv`, so the test
asserts the differences the plan lists (float, bool and zoned timestamp text in an all-text read)
and fails on any unlisted one. A typed read with a declared Arrow schema gives the source values.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv
import pytest
from tests.csv_sources import csv_source

from decoy.cli._sources import read_csv_frame
from decoy.cli.io import write_table

_TS = datetime(2024, 1, 2, 3, 4, 5, 6)
_NAN = float("nan")

# (type label, array, "same" in an all-text read or the expected differing new text)
_CASES: list[tuple[str, pa.Array, list[str] | None]] = [
    ("string", pa.array(["a", "c,d", "é"]), None),
    ("int8", pa.array([1, None, -3], pa.int8()), None),
    ("int64", pa.array([1, None, 2**62], pa.int64()), None),
    ("uint64", pa.array([0, None, 2**64 - 1], pa.uint64()), None),
    ("decimal", pa.array([Decimal("1.50"), None, Decimal("-0.01")], pa.decimal128(10, 2)), None),
    ("date32", pa.array([date(2024, 1, 2), None, date(1970, 1, 1)], pa.date32()), None),
    ("dict", pa.array(["x", "y", None]).dictionary_encode(), None),
    ("float64", pa.array([1.0, 1.5, 1e-7]), ["1", "1.5", "1e-7"]),
    ("float32", pa.array([1.0, 1.5, 0.25], pa.float32()), ["1", "1.5", "0.25"]),
    ("bool", pa.array([True, False, None]), ["true", "false", ""]),
    (
        "ts_utc",
        pa.array([_TS, None, _TS], pa.timestamp("us", tz="UTC")),
        ["2024-01-02 03:04:05.000006Z", "", "2024-01-02 03:04:05.000006Z"],
    ),
    (
        "ts_ny",
        pa.array([_TS, None, _TS], pa.timestamp("us", tz="America/New_York")),
        ["2024-01-02 03:04:05.000006Z", "", "2024-01-02 03:04:05.000006Z"],
    ),
]


def _old_text(table: pa.Table, path: Path) -> None:
    from decoy_engine import generated_table_to_pandas

    generated_table_to_pandas(table).to_csv(path, index=False)


def _all_text(path: Path) -> pd.DataFrame:
    return read_csv_frame("t", csv_source(path), path.parent, dtype=str)


@pytest.mark.parametrize(("label", "array", "differs"), _CASES, ids=[c[0] for c in _CASES])
def test_all_text_read_back(
    tmp_path: Path, label: str, array: pa.Array, differs: list[str] | None
) -> None:
    table = pa.table({"k": pa.array(range(len(array))), "c": array})
    new, old = tmp_path / "new.csv", tmp_path / "old.csv"
    write_table(table, "csv", new)
    _old_text(table, old)
    got, was = _all_text(new)["c"].tolist(), _all_text(old)["c"].tolist()
    if differs is None:
        assert got == was, label
    else:
        assert got != was, label
        assert [("" if pd.isna(v) else v) for v in got] == differs


@pytest.mark.parametrize(("label", "array", "differs"), _CASES, ids=[c[0] for c in _CASES])
def test_typed_read_back_gives_the_source_values(
    tmp_path: Path, label: str, array: pa.Array, differs: list[str] | None
) -> None:
    table = pa.table({"k": pa.array(range(len(array))), "c": array})
    out = tmp_path / "new.csv"
    write_table(table, "csv", out)
    arrow_type: Any = array.type
    if pa.types.is_dictionary(arrow_type):
        arrow_type = pa.string()
    options = pacsv.ConvertOptions(column_types={"c": arrow_type}, strings_can_be_null=True)
    back = pacsv.read_csv(out, convert_options=options).column("c")
    want = array.cast(arrow_type) if arrow_type != array.type else array
    assert back.to_pylist() == want.to_pylist(), label


def test_empty_string_and_null_both_read_as_null_under_the_default_vocabulary(
    tmp_path: Path,
) -> None:
    out = tmp_path / "e.csv"
    write_table(pa.table({"k": [1, 2, 3], "c": pa.array(["a", "", None])}), "csv", out)
    assert out.read_bytes() == b'"k","c"\n1,"a"\n2,""\n3,\n'
    assert _all_text(out)["c"].isna().tolist() == [False, True, True]


def test_float_negative_zero_and_nan_read_back_typed(tmp_path: Path) -> None:
    out = tmp_path / "f.csv"
    write_table(pa.table({"k": [1, 2, 3], "c": pa.array([-0.0, _NAN, 1e20])}), "csv", out)
    back = pacsv.read_csv(
        out, convert_options=pacsv.ConvertOptions(column_types={"c": pa.float64()})
    ).column("c")
    values = back.to_pylist()
    assert str(values[0]) == "-0.0"
    assert values[1] is None  # `nan` is in Arrow's default null vocabulary, as `NaN` was
    assert values[2] == 1e20


_WHOLE = datetime(2024, 1, 2, 3, 4, 5)


def _naive_texts(tmp_path: Path, values: list[datetime], unit: str) -> tuple[list[str], list[str]]:
    table = pa.table({"k": list(range(len(values))), "c": pa.array(values, pa.timestamp(unit))})
    new, old = tmp_path / "new.csv", tmp_path / "old.csv"
    write_table(table, "csv", new)
    _old_text(table, old)
    return _all_text(new)["c"].tolist(), _all_text(old)["c"].tolist()


def test_naive_us_whole_seconds_gain_a_six_digit_fraction(tmp_path: Path) -> None:
    """A1.7: pandas wrote no fraction for a whole-second column; Arrow writes `.000000`."""
    got, was = _naive_texts(tmp_path, [_WHOLE, _WHOLE], "us")
    assert was == ["2024-01-02 03:04:05"] * 2
    assert got == ["2024-01-02 03:04:05.000000"] * 2


def test_naive_us_with_a_nonzero_fraction_stays_equal(tmp_path: Path) -> None:
    got, was = _naive_texts(tmp_path, [_TS, _WHOLE], "us")
    assert got == was == ["2024-01-02 03:04:05.000006", "2024-01-02 03:04:05.000000"]


def test_naive_ns_gains_the_nine_digit_fraction(tmp_path: Path) -> None:
    got, was = _naive_texts(tmp_path, [_TS, _WHOLE], "ns")
    assert got == ["2024-01-02 03:04:05.000006000", "2024-01-02 03:04:05.000000000"]
    assert was[0] == "2024-01-02 03:04:05.000006"
    assert got != was


@pytest.mark.parametrize("unit", ["us", "ns"])
def test_naive_timestamp_typed_read_is_equal(tmp_path: Path, unit: str) -> None:
    table = pa.table({"k": [1, 2], "c": pa.array([_TS, _WHOLE], pa.timestamp(unit))})
    out = tmp_path / "new.csv"
    write_table(table, "csv", out)
    options = pacsv.ConvertOptions(column_types={"c": pa.timestamp(unit)})
    assert pacsv.read_csv(out, convert_options=options).column("c").equals(table.column("c"))
