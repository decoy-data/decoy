"""`decoy run --chunked` parquet streaming (deferred follow-up 6, 2026-06-12).

Reader and writer are picked by file suffix independently, mirroring the
plain path's free format mixing. Contracts pinned here:

- parquet target: VALUE parity with a plain run for any chunk size
  (each chunk writes one row group, so file bytes are stable only for a
  fixed chunk size); CSV target keeps the original byte-parity contract.
- parquet sources stream via ParquetFile.iter_batches and carry real
  dtypes, the first chunked inputs that are not all-string.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.csv_sources import file_source
from tests.keyed_secret import TEST_MASK_SECRET_REF

# Keyed strategies need an admitted mask secret (engine 0.17.0); see tests/keyed_secret.py.
pytestmark = pytest.mark.usefixtures("mask_secret")

runner = CliRunner()

_COLUMNS = [
    {
        "name": "ssn",
        "strategy": "fpe",
        "namespace": "ssn_ns",
        "provider_config": {"charset": "digits"},
    },
    {"name": "email", "strategy": "hash", "namespace": "email_ns"},
    {"name": "visits", "strategy": "hash", "namespace": "visits_ns"},
]


def _frame(rows: int = 200) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ssn": [f"{i:09d}" for i in range(rows)],
            "email": [f"user{i}@example.com" for i in range(rows)],
            "visits": list(range(rows)),  # int64: typed parquet column
        }
    )


def _pipeline(tmp_path: Path, *, src_fmt: str, tgt_fmt: str, rows: int = 200) -> Path:
    src = tmp_path / f"in.{src_fmt}"
    df = _frame(rows)
    if src_fmt == "parquet":
        df.to_parquet(src, index=False)
    else:
        df.to_csv(src, index=False)
    cfg = {
        "version": 2,
        "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
        "sources": {"accounts": file_source(src, src_fmt)},
        "tables": [{"name": "accounts", "columns": _COLUMNS}],
        "targets": {
            "accounts": {
                "type": "file",
                "format": tgt_fmt,
                "path": str(tmp_path / f"out.{tgt_fmt}"),
            }
        },
    }
    p = tmp_path / "pipeline.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return p


def _read_values(path: Path) -> dict:
    if path.suffix == ".parquet":
        return pq.read_table(str(path)).to_pydict()
    return pa.Table.from_pandas(pd.read_csv(path, dtype=str)).to_pydict()


class TestChunkedParquet:
    def test_parquet_to_parquet_value_parity_with_plain_run(self, tmp_path: Path) -> None:
        cfg = _pipeline(tmp_path, src_fmt="parquet", tgt_fmt="parquet")
        out = tmp_path / "out.parquet"
        assert runner.invoke(app, ["run", str(cfg)]).exit_code == 0
        plain = _read_values(out)
        out.unlink()

        result = runner.invoke(app, ["run", str(cfg), "--chunked", "--chunk-size", "33"])
        assert result.exit_code == 0, result.output
        chunked = _read_values(out)
        assert chunked == plain
        assert len(chunked["ssn"]) == 200

    def test_chunk_size_invariance(self, tmp_path: Path) -> None:
        cfg = _pipeline(tmp_path, src_fmt="parquet", tgt_fmt="parquet")
        out = tmp_path / "out.parquet"
        assert (
            runner.invoke(app, ["run", str(cfg), "--chunked", "--chunk-size", "7"]).exit_code == 0
        )
        seven = _read_values(out)
        out.unlink()
        assert (
            runner.invoke(app, ["run", str(cfg), "--chunked", "--chunk-size", "33"]).exit_code == 0
        )
        assert _read_values(out) == seven

    def test_same_chunk_size_is_byte_stable(self, tmp_path: Path) -> None:
        cfg = _pipeline(tmp_path, src_fmt="parquet", tgt_fmt="parquet")
        out = tmp_path / "out.parquet"
        assert (
            runner.invoke(app, ["run", str(cfg), "--chunked", "--chunk-size", "33"]).exit_code == 0
        )
        first = out.read_bytes()
        assert (
            runner.invoke(app, ["run", str(cfg), "--chunked", "--chunk-size", "33"]).exit_code == 0
        )
        assert out.read_bytes() == first

    def test_nulls_preserved_through_parquet_stream(self, tmp_path: Path) -> None:
        src = tmp_path / "in.parquet"
        df = _frame(20)
        df.loc[3, "email"] = None
        df.to_parquet(src, index=False)
        cfg = _pipeline(tmp_path, src_fmt="parquet", tgt_fmt="parquet")
        df.to_parquet(src, index=False)  # overwrite the helper's source
        out = tmp_path / "out.parquet"
        result = runner.invoke(app, ["run", str(cfg), "--chunked", "--chunk-size", "6"])
        assert result.exit_code == 0, result.output
        values = _read_values(out)
        assert values["email"][3] is None
        assert len(values["email"]) == 20

    def test_csv_source_parquet_target(self, tmp_path: Path) -> None:
        cfg = _pipeline(tmp_path, src_fmt="csv", tgt_fmt="parquet")
        out = tmp_path / "out.parquet"
        assert runner.invoke(app, ["run", str(cfg)]).exit_code == 0
        plain = _read_values(out)
        out.unlink()
        result = runner.invoke(app, ["run", str(cfg), "--chunked", "--chunk-size", "33"])
        assert result.exit_code == 0, result.output
        assert _read_values(out) == plain

    def test_parquet_source_csv_target(self, tmp_path: Path) -> None:
        cfg = _pipeline(tmp_path, src_fmt="parquet", tgt_fmt="csv")
        out = tmp_path / "out.csv"
        assert runner.invoke(app, ["run", str(cfg)]).exit_code == 0
        plain = _read_values(out)
        out.unlink()
        result = runner.invoke(app, ["run", str(cfg), "--chunked", "--chunk-size", "33"])
        assert result.exit_code == 0, result.output
        assert _read_values(out) == plain

    def test_empty_parquet_source_writes_valid_zero_row_file(self, tmp_path: Path) -> None:
        cfg = _pipeline(tmp_path, src_fmt="parquet", tgt_fmt="parquet", rows=0)
        out = tmp_path / "out.parquet"
        result = runner.invoke(app, ["run", str(cfg), "--chunked"])
        assert result.exit_code == 0, result.output
        table = pq.read_table(str(out))
        assert table.num_rows == 0
        assert set(table.column_names) == {"ssn", "email", "visits"}


# CHUNKED-STRUCT S2: nested passthrough columns (struct, list, map) next to a masked sibling.
_NESTED_SCHEMA = pa.schema(
    [
        ("email", pa.string()),
        ("addr", pa.struct([("city", pa.string()), ("zip", pa.int32())])),
        ("tags", pa.list_(pa.string())),
        ("attrs", pa.map_(pa.string(), pa.string())),
    ]
)
_NESTED_ROWS = {
    "email": ["a0@example.com", "a1@example.com", "a2@example.com"],
    "addr": [{"city": "c0", "zip": 0}, {"city": "c1", "zip": 1}, None],
    "tags": [["t0", "x"], ["t1", "x"], None],
    "attrs": [[("k", "v0")], [("k", "v1")], None],
}


def _nested_table(*, with_email: bool) -> pa.Table:
    """Fixture F (with `email`) or F-N (every column nested). The last row is null in
    every nested column, so chunk size 2 ends on a null-only single-row chunk."""
    fields = [f for f in _NESTED_SCHEMA if with_email or f.name != "email"]
    schema = pa.schema(fields)
    return pa.table({f.name: _NESTED_ROWS[f.name] for f in fields}, schema=schema)


def _nested_pipeline(tmp_path: Path, table: pa.Table, *, tgt_fmt: str = "parquet") -> Path:
    src = tmp_path / "nested_in.parquet"
    pq.write_table(table, src)
    columns = [
        {"name": n, "strategy": "redact" if n == "email" else "passthrough"}
        for n in table.schema.names
    ]
    cfg = {
        "version": 2,
        "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
        "sources": {"people": file_source(src, "parquet")},
        "tables": [{"name": "people", "columns": columns}],
        "targets": {
            "people": {
                "type": "file",
                "format": tgt_fmt,
                "path": str(tmp_path / f"nested_out.{tgt_fmt}"),
            }
        },
    }
    p = tmp_path / "nested_pipeline.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return p


class TestNestedPassthroughColumns:
    @pytest.mark.parametrize("with_email", [True, False], ids=["F", "F-N"])
    def test_chunked_equals_plain_and_keeps_types(self, tmp_path: Path, with_email: bool) -> None:
        table = _nested_table(with_email=with_email)
        cfg = _nested_pipeline(tmp_path, table)
        out = tmp_path / "nested_out.parquet"

        plain = runner.invoke(app, ["run", str(cfg)])
        assert plain.exit_code == 0, plain.output
        plain_table = pq.read_table(str(out))
        out.unlink()

        chunked = runner.invoke(app, ["run", str(cfg), "--chunked", "--chunk-size", "2"])
        assert chunked.exit_code == 0, chunked.output
        chunked_table = pq.read_table(str(out))

        assert chunked_table.num_rows == 3
        assert chunked_table.equals(plain_table)
        assert chunked_table.schema.types == table.schema.types
        for name in ("addr", "tags", "attrs"):
            assert chunked_table.column(name).to_pylist() == table.column(name).to_pylist()
        if with_email:
            leaked = set(_NESTED_ROWS["email"]) & set(chunked_table.column("email").to_pylist())
            assert not leaked

    @pytest.mark.parametrize("with_email", [True, False], ids=["F", "F-N"])
    def test_plain_run_keeps_source_schema(self, tmp_path: Path, with_email: bool) -> None:
        table = _nested_table(with_email=with_email)
        cfg = _nested_pipeline(tmp_path, table)
        result = runner.invoke(app, ["run", str(cfg)])
        assert result.exit_code == 0, result.output
        out = pq.read_table(str(tmp_path / "nested_out.parquet"))
        assert out.schema.types == table.schema.types
        assert out.num_rows == 3

    def test_csv_target_chunked_bytes_equal_plain(self, tmp_path: Path) -> None:
        cfg = _nested_pipeline(tmp_path, _nested_table(with_email=True), tgt_fmt="csv")
        out = tmp_path / "nested_out.csv"
        assert runner.invoke(app, ["run", str(cfg)]).exit_code == 0
        plain_bytes = out.read_bytes()
        out.unlink()
        result = runner.invoke(app, ["run", str(cfg), "--chunked", "--chunk-size", "2"])
        assert result.exit_code == 0, result.output
        assert out.read_bytes() == plain_bytes
