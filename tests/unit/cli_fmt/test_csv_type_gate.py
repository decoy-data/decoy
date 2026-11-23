"""CSV-WRITE-FAST A5 and A6 (unit side): the one Arrow CSV type and schema policy.

`check_csv_types` is public in `decoy.cli.io`. These tests cover the policy itself and the two
single-table writers that call it (`write_table`, `write_chunked_output`). The run-wide ordering
(no target placed before every target passes) is covered in
`tests/e2e/cli_fmt/test_csv_run_wide_preflight.py`.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pytest

from decoy.cli.io import (
    RunLayout,
    TargetFormatError,
    check_csv_types,
    write_chunked_output,
    write_table,
)

_REFUSED = {
    "float16": pa.float16(),
    "decimal256": pa.decimal256(40, 2),
    "binary": pa.binary(),
    "list": pa.list_(pa.int64()),
    "struct": pa.struct([("a", pa.int64())]),
    "duration": pa.duration("us"),
    "int_dictionary": pa.dictionary(pa.int8(), pa.int64()),
    "map": pa.map_(pa.string(), pa.int64()),
    "large_list": pa.large_list(pa.int64()),
    "fixed_size_binary": pa.binary(4),
    "interval": pa.month_day_nano_interval(),
}
_ACCEPTED = [
    pa.string(),
    pa.large_string(),
    pa.int8(),
    pa.uint64(),
    pa.float32(),
    pa.float64(),
    pa.bool_(),
    pa.date32(),
    pa.date64(),
    pa.timestamp("us"),
    pa.timestamp("ns", tz="UTC"),
    pa.decimal128(10, 2),
    pa.dictionary(pa.int8(), pa.string()),
    pa.null(),
    pa.time32("s"),
    pa.time32("ms"),
    pa.time64("us"),
    pa.time64("ns"),
]


def _no_context(exc: BaseException) -> None:
    assert exc.__cause__ is None
    assert exc.__context__ is None


@pytest.mark.parametrize("name", sorted(_REFUSED))
def test_an_unsupported_type_is_refused_with_a_value_free_coded_error(name: str) -> None:
    schema = pa.schema([("ok", pa.int64()), ("c", _REFUSED[name])])
    with pytest.raises(TargetFormatError) as caught:
        check_csv_types("t", schema)
    assert caught.value.code == "target.csv_unsupported_type"
    message = str(caught.value)
    assert "'t'" in message
    assert "'c'" in message
    assert str(_REFUSED[name]) in message
    _no_context(caught.value)


@pytest.mark.parametrize("arrow_type", _ACCEPTED, ids=str)
def test_every_allowlisted_type_passes(arrow_type: pa.DataType) -> None:
    check_csv_types("t", pa.schema([("c", arrow_type)]))


def test_the_error_never_holds_a_cell_value(tmp_path: Path) -> None:
    secret = "SECRET-CELL-VALUE"
    table = pa.table({"c": pa.array([[1, 2]], pa.list_(pa.int64())), "v": [secret]})
    with pytest.raises(TargetFormatError) as caught:
        write_table(table, "csv", tmp_path / "out.csv")
    assert secret not in str(caught.value)
    assert not list(tmp_path.iterdir())
    _no_context(caught.value)


def test_changed_column_names_or_order_are_coded_drift() -> None:
    first = pa.schema([("a", pa.int64()), ("b", pa.string())])
    renamed = pa.schema([("a", pa.int64()), ("z", pa.string())])
    swapped = pa.schema([("b", pa.string()), ("a", pa.int64())])
    fewer = pa.schema([("a", pa.int64())])
    check_csv_types("t", first, expected_schema=first)
    for later in (renamed, swapped, fewer):
        with pytest.raises(TargetFormatError) as caught:
            check_csv_types("t", later, expected_schema=first)
        assert caught.value.code == "target.csv_schema_drift"
        _no_context(caught.value)


def test_a_changed_type_is_not_drift() -> None:
    first = pa.schema([("a", pa.int64()), ("b", pa.string())])
    check_csv_types("t", pa.schema([("a", pa.float64()), ("b", pa.int64())]), expected_schema=first)
    check_csv_types("t", pa.schema([("a", pa.null()), ("b", pa.date32())]), expected_schema=first)


def test_schema_metadata_is_not_drift() -> None:
    first = pa.schema([("a", pa.int64())], metadata={"x": "1"})
    check_csv_types("t", pa.schema([("a", pa.int64())]), expected_schema=first)


def _chunks(tmp_path: Path, tables: list[pa.Table], name: str = "t") -> Path:
    out = tmp_path / "out.csv"
    write_chunked_output(
        iter(tables),
        "csv",
        str(out),
        RunLayout.fixed(tmp_path),
        empty_schema=None,
        name=name,
    )
    return out


def test_chunked_writer_refuses_drift_before_the_chunk_reaches_the_writer(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    out.write_bytes(b"old\n")
    good = pa.table({"a": [1, 2], "b": ["x", "y"]})
    drifted = pa.table({"a": [3], "z": ["w"]})
    with pytest.raises(TargetFormatError) as caught:
        _chunks(tmp_path, [good, drifted])
    assert caught.value.code == "target.csv_schema_drift"
    _no_context(caught.value)
    assert out.read_bytes() == b"old\n"
    assert [p.name for p in tmp_path.iterdir()] == ["out.csv"]


def test_chunked_writer_refuses_an_unsupported_first_chunk_before_staging(tmp_path: Path) -> None:
    bad = pa.table({"a": pa.array([[1]], pa.list_(pa.int64()))})
    with pytest.raises(TargetFormatError) as caught:
        _chunks(tmp_path, [bad])
    assert caught.value.code == "target.csv_unsupported_type"
    assert list(tmp_path.iterdir()) == []


def test_one_schema_publishes_one_file_with_one_header(tmp_path: Path) -> None:
    out = _chunks(tmp_path, [pa.table({"a": [1, 2]}), pa.table({"a": [3]})])
    assert out.read_bytes() == b'"a"\n"1"\n"2"\n"3"\n'


def test_chunked_writer_writes_a_later_null_chunk(tmp_path: Path) -> None:
    first = pa.table({"a": [1], "b": ["x"]})
    later = pa.table({"a": [2], "b": pa.nulls(1)})
    out = _chunks(tmp_path, [first, later])
    assert out.read_bytes() == b'"a","b"\n1,"x"\n2,\n'


def test_chunked_writer_takes_a_column_that_is_all_null_in_the_first_chunk(
    tmp_path: Path,
) -> None:
    first = pa.table({"a": [1], "b": pa.nulls(1)})
    later = pa.table({"a": [2], "b": ["x"]})
    out = _chunks(tmp_path, [first, later])
    assert out.read_bytes() == b'"a","b"\n1,\n2,"x"\n'


def test_chunked_writer_accepts_a_non_text_type_after_an_all_null_first_chunk(
    tmp_path: Path,
) -> None:
    first = pa.table({"a": [1], "b": pa.nulls(1)})
    later = pa.table({"a": [2], "b": [5]})
    out = _chunks(tmp_path, [first, later])
    assert out.read_bytes() == b'"a","b"\n1,\n2,5\n'


def test_chunked_writer_writes_each_chunk_on_its_own_types(tmp_path: Path) -> None:
    first = pa.table({"a": [1, 2], "b": pa.array([1, 2], pa.int64())})
    later = pa.table({"a": [3, 4], "b": pa.array([3.0, None], pa.float64())})
    out = _chunks(tmp_path, [first, later])
    assert out.read_bytes() == b'"a","b"\n1,1\n2,2\n3,3\n4,\n'
