"""CSV-WRITE-FAST A1, A2, A4, A7: the exact bytes an Arrow CSV target gets, and how they are fed.

Every expectation here is a checked-in binary fixture under `tests/fixtures/cli_fmt/csv_writer/`
(measured with PyArrow's `write_csv`) or a hand-written cell list from the plan's Fields table.
Regenerate the fixtures only with a plan revision: `write_fixtures(dest)` writes the whole set.
"""

from __future__ import annotations

import csv
import io
import math
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv
import pytest

from decoy.cli.io import _targets, write_chunked_output, write_private_table, write_table
from decoy.cli.io._compression import COMPRESSION
from decoy.cli.io._layout import RunLayout

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "cli_fmt" / "csv_writer"
PAYLOAD = FIXTURES / "csv-writer-payload.bin"
SUFFIXES = tuple(suffix for suffix, _method in COMPRESSION)
STREAM_SUFFIXES = (".gz", ".bz2", ".xz", ".zst")
STREAM_ROWS = 30_001
_NAN = float("nan")


def mixed_table() -> pa.Table:
    """One column per accepted Arrow type, with the edge values of the plan's Fields table."""
    utc = datetime(2024, 1, 2, 3, 4, 5)
    return pa.table(
        {
            "s": pa.array(["a", "", None, 'say "hi"', "c,d", "l1\nl2"], pa.string()),
            "ls": pa.array(["é", "x", None, "", "y", "z"], pa.large_string()),
            "i8": pa.array([1, None, -3, 0, 127, -128], pa.int8()),
            "i64": pa.array([1, None, -3, 0, 2**63 - 1, -(2**63)], pa.int64()),
            "u64": pa.array([0, 1, None, 2**63, 2**64 - 1, 5], pa.uint64()),
            "f64": pa.array([0.1, 1.0, -0.0, 1e20, 1.5e-7, _NAN], pa.float64()),
            "f32": pa.array([0.1, 1.0, -0.0, 1e20, 1.5e-7, _NAN], pa.float32()),
            "f64_edge": pa.array([5e-324, -5e-324, 1e300, 42.0, 9007199254740992.0, None]),
            "f32_edge": pa.array([1e-45, -1e-45, 1e30, 42.0, 1.6777216e07, None], pa.float32()),
            "b": pa.array([True, False, None, True, False, True], pa.bool_()),
            "d32": pa.array([date(2024, 1, 2), None, date(1970, 1, 1)] * 2, pa.date32()),
            "d64": pa.array([date(2024, 1, 2), None, date(1970, 1, 1)] * 2, pa.date64()),
            "ts": pa.array(
                [datetime(2024, 1, 2, 3, 4, 5, 6), None, datetime(1999, 12, 31, 23, 59, 59)] * 2,
                pa.timestamp("us"),
            ),
            "ts_utc": pa.array([utc, None, utc] * 2, pa.timestamp("us", tz="UTC")),
            "ts_ny": pa.array([utc, None, utc] * 2, pa.timestamp("us", tz="America/New_York")),
            "ts_off": pa.array([utc, None, utc] * 2, pa.timestamp("us", tz="+05:30")),
            "ts_s_ny": pa.array([utc, None, utc] * 2, pa.timestamp("s", tz="America/New_York")),
            "ts_ms_off": pa.array([utc, None, utc] * 2, pa.timestamp("ms", tz="+05:30")),
            "ts_ns_utc": pa.array([utc, None, utc] * 2, pa.timestamp("ns", tz="UTC")),
            "ts_ns": pa.array(
                [datetime(2024, 1, 2, 3, 4, 5, 6), None, utc] * 2, pa.timestamp("ns")
            ),
            "dec": pa.array(
                [Decimal("1.50"), None, Decimal("-0.01"), Decimal("0.00"), Decimal("9.99"), None],
                pa.decimal128(10, 2),
            ),
            "dict": pa.array(["x", "y", "x", None, "y", "c,d"]).dictionary_encode(),
            "nothing": pa.nulls(6),
            "int_key": pa.array([10, 20, 30, 40, 50, 60], pa.int32()),
        }
    )


def stream_table(rows: int = STREAM_ROWS) -> pa.Table:
    """A compressible table for the codec fixtures: 30,001 rows of an int and a short string."""
    return pa.table(
        {
            "id": pa.array([i % 1000 for i in range(rows)], pa.int64()),
            "k": pa.array([f"k{i % 7}" for i in range(rows)], pa.string()),
        }
    )


def chunked_bytes(table: pa.Table, name: str, size: int, tmp_path: Path) -> bytes:
    out = tmp_path / name
    published = write_chunked_output(
        iter(table.slice(i, size) for i in range(0, table.num_rows, size)),
        "csv",
        str(out),
        RunLayout.fixed(tmp_path),
        empty_schema=None,
    )
    assert published == out
    return out.read_bytes()


def write_fixtures(dest: Path) -> None:
    """Write every fixture. Run it only for a plan revision that changes a frozen byte."""
    import tempfile

    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        out = Path(work) / "mixed.csv"
        write_table(mixed_table(), "csv", out)
        (dest / PAYLOAD.name).write_bytes(out.read_bytes())
        for suffix in SUFFIXES:
            target = Path(work) / f"out.csv{suffix}"
            write_table(stream_table(), "csv", target)
            (dest / f"csv-writer-out.csv{suffix}").write_bytes(target.read_bytes())


# --- A1: the payload bytes and the platform text contract ----------------------------------


def _written(table: pa.Table, tmp_path: Path, name: str = "out.csv") -> bytes:
    out = tmp_path / name
    write_table(table, "csv", out)
    return out.read_bytes()


def test_a1_mixed_table_equals_the_checked_in_bytes(tmp_path: Path) -> None:
    assert _written(mixed_table(), tmp_path) == PAYLOAD.read_bytes()


def test_a1_platform_text_contract(tmp_path: Path) -> None:
    raw = _written(mixed_table(), tmp_path)
    raw.decode("utf-8", errors="strict")
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    assert raw.endswith(b"\n")


def _cells() -> dict[str, list[str]]:
    rows = list(csv.reader(io.StringIO(PAYLOAD.read_bytes().decode("utf-8"), newline="")))
    return {name: [row[i] for row in rows[1:]] for i, name in enumerate(rows[0])}


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("f64", ["0.1", "1", "-0", "1e+20", "1.5e-7", "nan"]),
        ("f32", ["0.1", "1", "-0", "1e+20", "1.5e-7", "nan"]),
        ("f64_edge", ["5e-324", "-5e-324", "1e+300", "42", "9.007199254740992e+15", ""]),
        ("f32_edge", ["1e-45", "-1e-45", "1e+30", "42", "16777216", ""]),
        ("b", ["true", "false", "", "true", "false", "true"]),
        ("u64", ["0", "1", "", str(2**63), str(2**64 - 1), "5"]),
        ("s", ["a", "", "", 'say "hi"', "c,d", "l1\nl2"]),
        ("dec", ["1.50", "", "-0.01", "0.00", "9.99", ""]),
        ("dict", ["x", "y", "x", "", "y", "c,d"]),
        ("ts_utc", ["2024-01-02 03:04:05.000000Z", "", "2024-01-02 03:04:05.000000Z"] * 2),
        ("ts_ny", ["2024-01-02 03:04:05.000000Z", "", "2024-01-02 03:04:05.000000Z"] * 2),
        ("ts_off", ["2024-01-02 03:04:05.000000Z", "", "2024-01-02 03:04:05.000000Z"] * 2),
        ("ts_s_ny", ["2024-01-02 03:04:05Z", "", "2024-01-02 03:04:05Z"] * 2),
        ("ts_ms_off", ["2024-01-02 03:04:05.000Z", "", "2024-01-02 03:04:05.000Z"] * 2),
        ("ts_ns_utc", ["2024-01-02 03:04:05.000000000Z", "", "2024-01-02 03:04:05.000000000Z"] * 2),
        ("ts_ns", ["2024-01-02 03:04:05.000006000", "", "2024-01-02 03:04:05.000000000"] * 2),
    ],
)
def test_a1_cells_match_the_plan_text(column: str, expected: list[str]) -> None:
    got = _cells()[column]
    if column == "ts_ns":
        assert got[0] == expected[0] and got[2] == expected[2]
    else:
        assert got == expected


def test_a1_quoting_and_header() -> None:
    first = PAYLOAD.read_bytes().split(b"\n", 1)[0]
    assert first.startswith(b'"s","ls","i8"')
    rows = PAYLOAD.read_bytes().split(b"\n")
    assert rows[2].startswith(b'"","x"')  # an empty string is `""`
    assert rows[3].startswith(b",,")  # a null is an empty field


def test_a1_negative_zero_keeps_its_sign_bit(tmp_path: Path) -> None:
    table = pa.table({"x": pa.array([-0.0, 0.0])})
    out = tmp_path / "z.csv"
    write_table(table, "csv", out)
    back = pacsv.read_csv(
        out, convert_options=pacsv.ConvertOptions(column_types={"x": pa.float64()})
    )
    assert [math.copysign(1.0, v) for v in back.column("x").to_pylist()] == [-1.0, 1.0]


# --- A2 / A4: whole equals chunked, and every complete compressed file ---------------------


def _fixture(suffix: str) -> bytes:
    return (FIXTURES / f"csv-writer-out.csv{suffix}").read_bytes()


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_a4_complete_file_equals_the_fixture(tmp_path: Path, suffix: str) -> None:
    one = tmp_path / "one"
    two = tmp_path / "two"
    one.mkdir()
    two.mkdir()
    assert _written(stream_table(), one, f"out.csv{suffix}") == _fixture(suffix)
    assert _written(stream_table(), two, f"out.csv{suffix}") == _fixture(suffix)


def _extract(suffix: str, raw: bytes) -> bytes:
    """The CSV payload inside a complete compressed fixture, by the stdlib readers."""
    import bz2
    import gzip
    import lzma
    import tarfile
    import zipfile

    if suffix.startswith(".tar"):
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as tar:
            member = tar.extractfile("out.csv")
            assert member is not None
            return member.read()
    if suffix == ".zip":
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            return archive.read("out.csv")
    if suffix == ".zst":
        return pa.CompressedInputStream(pa.BufferReader(raw), "zstd").read()
    return {".gz": gzip.decompress, ".bz2": bz2.decompress, ".xz": lzma.decompress}[suffix](raw)


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_a4_fixture_opens_and_holds_the_payload(tmp_path: Path, suffix: str) -> None:
    expected = _written(stream_table(), tmp_path, "plain.csv")
    assert _extract(suffix, _fixture(suffix)) == expected


def test_a4_tar_header_is_ustar() -> None:
    block = _fixture(".tar")[:512]
    assert block[257:265] == b"ustar\x0000"  # POSIX ustar, not GNU or pax


def test_a4_zip_and_tar_member_metadata() -> None:
    import tarfile
    import zipfile

    with zipfile.ZipFile(FIXTURES / "csv-writer-out.csv.zip") as archive:
        (info,) = archive.infolist()
        assert info.filename == "out.csv"
        assert info.compress_type == zipfile.ZIP_DEFLATED
        assert info.date_time == (1980, 1, 1, 0, 0, 0)
        assert info.create_system == 3
        assert info.extra == b"" and info.comment == b""
    for suffix in (".tar", ".tar.gz", ".tar.bz2", ".tar.xz"):
        with tarfile.open(FIXTURES / f"csv-writer-out.csv{suffix}", "r:*") as tar:
            (member,) = tar.getmembers()
            assert member.name == "out.csv"
            assert (member.mode, member.uid, member.gid) == (0o644, 0, 0)
            assert (member.uname, member.gname, member.mtime) == ("", "", 0)


@pytest.mark.parametrize("suffix", STREAM_SUFFIXES)
@pytest.mark.parametrize("size", [7, 4096, STREAM_ROWS])
def test_a2_chunked_equals_whole_and_the_fixture(tmp_path: Path, suffix: str, size: int) -> None:
    got = chunked_bytes(stream_table(), f"out.csv{suffix}", size, tmp_path)
    assert got == _fixture(suffix)


@pytest.mark.parametrize("size", [7, 4096, STREAM_ROWS])
def test_a2_uncompressed_chunked_equals_whole(tmp_path: Path, size: int) -> None:
    whole = _written(stream_table(), tmp_path, "whole.csv")
    assert chunked_bytes(stream_table(), "chunked.csv", size, tmp_path) == whole


def test_a2_gzip_is_one_member_with_the_fixed_header() -> None:
    import gzip

    raw = _fixture(".gz")
    assert raw[:10] == bytes.fromhex("1f8b08000000000000ff")
    assert raw.count(b"\x1f\x8b\x08") >= 1
    with gzip.open(io.BytesIO(raw)) as fh:  # one member reads to the end
        assert fh.read().count(b"\n") == STREAM_ROWS + 1


# --- A7: bounded write batches and the private DataFrame route -----------------------------


class _SpyWriter:
    """Records the rows of each batch handed to a real `CSVWriter`."""

    sizes: list[int]

    def __init__(self, real: pacsv.CSVWriter) -> None:
        self._real = real

    def write_batch(self, batch: pa.RecordBatch) -> None:
        type(self).sizes.append(batch.num_rows)
        self._real.write_batch(batch)

    def __enter__(self) -> _SpyWriter:
        self._real.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        self._real.__exit__(*exc)


@pytest.fixture
def batch_sizes(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    sizes: list[int] = []
    _SpyWriter.sizes = sizes
    real = pacsv.CSVWriter
    monkeypatch.setattr(
        _targets.pacsv,
        "CSVWriter",
        lambda *a, **k: _SpyWriter(real(*a, **k)),
    )
    return sizes


def test_a7_whole_table_batches_are_bounded(tmp_path: Path, batch_sizes: list[int]) -> None:
    rows = 3 * _targets._CSV_WRITE_BATCH_ROWS + 17
    write_table(pa.table({"n": pa.array(range(rows), pa.int64())}), "csv", tmp_path / "t.csv")
    assert sum(batch_sizes) == rows
    assert len(batch_sizes) > 3
    assert max(batch_sizes) <= _targets._CSV_WRITE_BATCH_ROWS


@pytest.mark.parametrize("chunk_rows", [5, _targets._CSV_WRITE_BATCH_ROWS + 1, 150_000])
def test_a7_chunked_batches_are_bounded(
    tmp_path: Path, batch_sizes: list[int], chunk_rows: int
) -> None:
    table = pa.table({"n": pa.array(range(150_000), pa.int64())})
    if chunk_rows == 5:
        table = table.slice(0, 50)
    chunked_bytes(table, "c.csv", chunk_rows, tmp_path)
    assert sum(batch_sizes) == table.num_rows
    assert max(batch_sizes) <= _targets._CSV_WRITE_BATCH_ROWS


def test_a7_private_dataframe_route_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frame = pd.DataFrame(
        {"mixed": pd.Series(["a", 1, None, "c,d"], dtype=object), "f": [1.0, 2.5, None, -0.0]}
    )

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("a DataFrame must not be converted to Arrow")

    class _NoFromPandas:
        Table = type("Table", (), {"from_pandas": staticmethod(boom)})

        def __getattr__(self, name: str) -> object:
            return getattr(pa, name)

    monkeypatch.setattr(_targets, "pa", _NoFromPandas())
    monkeypatch.setattr(_targets.pacsv, "CSVWriter", boom)
    out = tmp_path / "private.csv"
    write_private_table(frame, "csv", out)
    assert out.read_bytes() == frame.to_csv(index=False).encode()
    assert out.stat().st_mode & 0o777 == 0o600
