"""`decoy run --chunked` read failures: value-free refusals and capacity (PCNI S2, R3).

B1: no source value reaches `--json` or `--verbose` output from any read failure, at any row,
including a csv chunk the reader consumes before the engine starts.
B2: an Arrow or Python out-of-memory is a capacity failure (exit 5), never a bad cell.
"""

from __future__ import annotations

import json as _json
from pathlib import Path

import pyarrow as pa
import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.csv_sources import file_source
from tests.keyed_secret import TEST_MASK_SECRET_REF

pytestmark = pytest.mark.usefixtures("mask_secret")

runner = CliRunner()

_VALID_ROWS = 80_000


def _csv_config(tmp_path: Path, rows: list[bytes]) -> Path:
    src = tmp_path / "in.csv"
    src.write_bytes(b"id,email\n" + b"".join(rows))
    cfg = {
        "version": 2,
        "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
        "sources": {"t": file_source(src, "csv")},
        "tables": [
            {
                "name": "t",
                "columns": [
                    {"name": "id", "strategy": "passthrough"},
                    {"name": "email", "strategy": "hash", "namespace": "e_ns"},
                ],
            }
        ],
        "targets": {"t": {"type": "file", "format": "csv", "path": str(tmp_path / "out.csv")}},
    }
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def _source_config(tmp_path: Path, src: Path, fmt: str) -> Path:
    path = _csv_config(tmp_path, [b"1,a@x.com\n"])
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["sources"] = {"t": file_source(src, fmt)}
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def _run(cfg: Path, *flags: str):
    return runner.invoke(app, ["run", str(cfg), "--chunked", *flags])


class TestAt1BadCsvByteIsValueFree:
    """AT-B1: row 80,001 is past the 10,000-row preflight and inside the first 100,000-row chunk."""

    @pytest.mark.parametrize("flag", ["--json", "--verbose"])
    def test_late_invalid_utf8_byte_never_reaches_the_output(
        self, tmp_path: Path, flag: str
    ) -> None:
        good = [f"{i},user{i}@x.com\n".encode() for i in range(_VALID_ROWS)]
        bad = [b"80000,leakcell\xffsecret@x.com\n"]
        cfg = _csv_config(tmp_path, [*good, *bad])
        result = _run(cfg, flag)
        assert result.exit_code == 3, result.output
        assert "chunked_passthrough_value_unrepresentable" in result.output
        for marker in ("0xff", "\\xff", "�", "leakcell", "secret@x.com", "position"):
            assert marker not in result.output, marker
        assert not (tmp_path / "out.csv").exists()

    def test_json_error_kind_is_the_coded_refusal(self, tmp_path: Path) -> None:
        good = [f"{i},user{i}@x.com\n".encode() for i in range(_VALID_ROWS)]
        cfg = _csv_config(tmp_path, [*good, b"80000,a\xffb@x.com\n"])
        result = _run(cfg, "--json")
        assert result.exit_code == 3
        payload = _json.loads(result.output.strip().splitlines()[-1])
        assert payload.get("error_kind") != "capacity"


class TestAt3DecoderFailureIsValueFree:
    """AT-B3: a decoder error mid-stream is the coded refusal, never the decoder's own text."""

    @pytest.mark.parametrize("flag", ["--json", "--verbose"])
    def test_gzip_tail_that_is_plaintext(self, tmp_path: Path, flag: str) -> None:
        import gzip

        good = b"id,email\n" + b"".join(f"{i},user{i}@x.com\n".encode() for i in range(80_000))
        src = tmp_path / "in.csv.gz"
        src.write_bytes(gzip.compress(good) + b"LEAKCELL,secret@x.com\n")
        cfg = _source_config(tmp_path, src, "csv")
        result = _run(cfg, flag)
        assert result.exit_code == 3, result.output
        assert "chunked_passthrough_value_unrepresentable" in result.output
        for marker in ("LEAKCELL", "b'LE'", "gzipped", "secret@x.com"):
            assert marker not in result.output, marker

    @pytest.mark.parametrize("flag", ["--json", "--verbose"])
    def test_corrupt_second_snappy_row_group(self, tmp_path: Path, flag: str) -> None:
        import pyarrow.parquet as pq

        n = 150_000
        table = pa.table({"id": list(range(n)), "email": [f"user{i}@x.com" for i in range(n)]})
        src = tmp_path / "in.parquet"
        pq.write_table(table, src, compression="snappy", row_group_size=50_000)
        meta = pq.ParquetFile(src).metadata
        assert meta.num_row_groups == 3
        raw = bytearray(src.read_bytes())
        col = meta.row_group(1).column(1)
        start = col.dictionary_page_offset or col.data_page_offset
        end = start + col.total_compressed_size
        raw[start + 20 : end - 20] = b"\xff" * (end - start - 40)
        src.write_bytes(bytes(raw))
        cfg = _source_config(tmp_path, src, "parquet")
        result = _run(cfg, flag)
        assert result.exit_code == 3, result.output
        assert "chunked_passthrough_value_unrepresentable" in result.output
        assert "unexpected_error" not in result.output
        assert "decompression" not in result.output.lower()

    @pytest.mark.parametrize("flag", ["--json", "--verbose"])
    def test_corrupt_xz_tail(self, tmp_path: Path, flag: str) -> None:
        import lzma

        good = b"id,email\n" + b"".join(f"{i},user{i}@x.com\n".encode() for i in range(80_000))
        packed = bytearray(lzma.compress(good))
        # Damage the stream near its end so the decoder fails mid-read, after rows were yielded.
        packed[-40:-20] = b"\xff" * 20
        src = tmp_path / "in.csv.xz"
        src.write_bytes(bytes(packed))
        cfg = _source_config(tmp_path, src, "csv")
        result = _run(cfg, flag)
        assert result.exit_code == 3, result.output
        assert "chunked_passthrough_value_unrepresentable" in result.output
        assert "unexpected_error" not in result.output
        assert "lzma" not in result.output.lower()


def _patched_engine(monkeypatch: pytest.MonkeyPatch, *, at: str, exc: Exception) -> None:
    import decoy_engine

    def fake(*args, **kwargs):
        if at == "creation":
            raise exc

        def gen():
            yield from ()
            raise exc

        return gen()

    monkeypatch.setattr(decoy_engine, "run_mask_chunked", fake)


@pytest.mark.parametrize("at", ["creation", "iteration"])
@pytest.mark.parametrize(
    "make",
    [pa.ArrowMemoryError, pa.ArrowCapacityError, MemoryError],
    ids=["arrow", "arrow-capacity", "python"],
)
class TestAt2OutOfMemoryIsCapacity:
    def test_exit_5_and_capacity_kind(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, at: str, make: type
    ) -> None:
        cfg = _csv_config(tmp_path, [b"1,a@x.com\n", b"2,b@x.com\n"])
        _patched_engine(monkeypatch, at=at, exc=make("out of memory"))
        result = _run(cfg, "--json")
        assert result.exit_code == 5, result.output
        payload = _json.loads(result.output.strip().splitlines()[-1])
        assert payload.get("error_kind") == "capacity"

    def test_exit_code_for_agrees_with_the_run_handler(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, at: str, make: type
    ) -> None:
        from decoy.cli.exit_codes import exit_code_for

        exc = make("out of memory")
        cfg = _csv_config(tmp_path, [b"1,a@x.com\n", b"2,b@x.com\n"])
        _patched_engine(monkeypatch, at=at, exc=exc)
        result = _run(cfg, "--json")
        assert exit_code_for(exc) == result.exit_code == 5
