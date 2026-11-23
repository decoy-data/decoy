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

import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal
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
    def test_parquet_to_parquet_value_parity_with_plain_run(
        self, tmp_path: Path
    ) -> None:
        cfg = _pipeline(tmp_path, src_fmt="parquet", tgt_fmt="parquet")
        out = tmp_path / "out.parquet"
        assert runner.invoke(app, ["run", str(cfg)]).exit_code == 0
        plain = _read_values(out)
        out.unlink()

        result = runner.invoke(
            app, ["run", str(cfg), "--chunked", "--chunk-size", "33"]
        )
        assert result.exit_code == 0, result.output
        chunked = _read_values(out)
        assert chunked == plain
        assert len(chunked["ssn"]) == 200

    def test_chunk_size_invariance(self, tmp_path: Path) -> None:
        cfg = _pipeline(tmp_path, src_fmt="parquet", tgt_fmt="parquet")
        out = tmp_path / "out.parquet"
        assert (
            runner.invoke(
                app, ["run", str(cfg), "--chunked", "--chunk-size", "7"]
            ).exit_code
            == 0
        )
        seven = _read_values(out)
        out.unlink()
        assert (
            runner.invoke(
                app, ["run", str(cfg), "--chunked", "--chunk-size", "33"]
            ).exit_code
            == 0
        )
        assert _read_values(out) == seven

    def test_same_chunk_size_is_byte_stable(self, tmp_path: Path) -> None:
        cfg = _pipeline(tmp_path, src_fmt="parquet", tgt_fmt="parquet")
        out = tmp_path / "out.parquet"
        assert (
            runner.invoke(
                app, ["run", str(cfg), "--chunked", "--chunk-size", "33"]
            ).exit_code
            == 0
        )
        first = out.read_bytes()
        assert (
            runner.invoke(
                app, ["run", str(cfg), "--chunked", "--chunk-size", "33"]
            ).exit_code
            == 0
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
        result = runner.invoke(
            app, ["run", str(cfg), "--chunked", "--chunk-size", "33"]
        )
        assert result.exit_code == 0, result.output
        assert _read_values(out) == plain

    def test_parquet_source_csv_target(self, tmp_path: Path) -> None:
        cfg = _pipeline(tmp_path, src_fmt="parquet", tgt_fmt="csv")
        out = tmp_path / "out.csv"
        assert runner.invoke(app, ["run", str(cfg)]).exit_code == 0
        plain = _read_values(out)
        out.unlink()
        result = runner.invoke(
            app, ["run", str(cfg), "--chunked", "--chunk-size", "33"]
        )
        assert result.exit_code == 0, result.output
        assert _read_values(out) == plain

    def test_empty_parquet_source_writes_valid_zero_row_file(
        self, tmp_path: Path
    ) -> None:
        cfg = _pipeline(tmp_path, src_fmt="parquet", tgt_fmt="parquet", rows=0)
        out = tmp_path / "out.parquet"
        result = runner.invoke(app, ["run", str(cfg), "--chunked"])
        assert result.exit_code == 0, result.output
        table = pq.read_table(str(out))
        assert table.num_rows == 0
        assert set(table.column_names) == {"ssn", "email", "visits"}


# ---------------------------------------------------------------------------------------
# PARQUET-CHUNKED-NULLABLE-INT S2: `--chunked` keeps one source type per column. Fixtures F
# (nullable int, uint64, date), M (the type matrix) and R (values pandas refuses) are the
# plan's; goldens live in tests/e2e/fixtures.
# ---------------------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"
_BIG = 2**53 + 1


def _field(name: str, typ: pa.DataType, *, nullable: bool = True, fid: int | None = None):
    meta = {"PARQUET:field_id": str(fid)} if fid is not None else None
    return pa.field(name, typ, nullable=nullable, metadata=meta)


def _fixture_f() -> pa.Table:
    return pa.table(
        {
            "id": pa.array(range(9), pa.int64()),
            "n": pa.array([10, 20, 30, _BIG, None, 60, None, None, None], pa.int64()),
            "u": pa.array([1, 2**63 + 5, 2**64 - 1, 7, None, 9, None, None, None], pa.uint64()),
            "d": pa.array([date(2020, 1, 1 + i) for i in range(4)] + [None] * 5, pa.date32()),
            "email": pa.array([f"u{i}@example.com" for i in range(6)] + [None] * 3, pa.string()),
        }
    )


def _fixture_m() -> pa.Table:
    nul = [None, None, None]
    fields = [
        _field("i8", pa.int8(), fid=1),
        _field("u16", pa.uint16(), fid=2),
        _field("u64", pa.uint64(), fid=3),
        _field("d128", pa.decimal128(12, 2), fid=4),
        _field("d256", pa.decimal256(40, 2), fid=5),
        _field("dic", pa.dictionary(pa.int32(), pa.string()), fid=6),
        _field("ts", pa.timestamp("us", tz="UTC"), fid=7),
        _field("req", pa.int64(), nullable=False, fid=8),
        _field("f", pa.float64(), fid=9),
        _field("email", pa.string(), fid=10),
    ]
    stamp = datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc)
    cols = [
        pa.array([1, -2, 3, *nul], pa.int8()),
        pa.array([1, 65535, 3, *nul], pa.uint16()),
        pa.array([1, 2**63 + 5, 2**64 - 1, *nul], pa.uint64()),
        pa.array(
            [Decimal("1.25"), Decimal("3.50"), Decimal("9999999999.99"), *nul], pa.decimal128(12, 2)
        ),
        pa.array([Decimal("1.25"), Decimal("3.50"), Decimal("7.00"), *nul], pa.decimal256(40, 2)),
        pa.array(["a", "b", "a", *nul], pa.dictionary(pa.int32(), pa.string())),
        pa.array([stamp, stamp, stamp, *nul], pa.timestamp("us", tz="UTC")),
        pa.array(range(6), pa.int64()),
        pa.array([1.5, float("nan"), 2.5, *nul], pa.float64()),
        pa.array([f"m{i}@example.com" for i in range(3)] + nul, pa.string()),
    ]
    return pa.Table.from_arrays(cols, schema=pa.schema(fields))


def _typed_config(
    tmp_path: Path,
    table: pa.Table,
    *,
    hashed: tuple[str, ...] = ("email",),
    tgt_fmt: str = "parquet",
    when: dict[str, str] | None = None,
    name: str = "t",
) -> Path:
    src = tmp_path / f"{name}_src.parquet"
    pq.write_table(table, src)
    columns = []
    for col in table.column_names:
        spec: dict = (
            {"name": col, "strategy": "hash", "namespace": f"{col}_ns"}
            if col in hashed
            else {"name": col, "strategy": "passthrough"}
        )
        if when and col in when:
            spec["when"] = when[col]
        columns.append(spec)
    cfg = {
        "version": 2,
        "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
        "sources": {"t": file_source(src, "parquet")},
        "tables": [{"name": "t", "columns": columns}],
        "targets": {
            "t": {"type": "file", "format": tgt_fmt, "path": str(tmp_path / f"{name}.{tgt_fmt}")}
        },
    }
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def _run_chunked(cfg: Path, size: int = 3, *extra: str):
    return runner.invoke(app, ["run", str(cfg), "--chunked", "--chunk-size", str(size), *extra])


def _out(tmp_path: Path, fmt: str, name: str = "t") -> Path:
    return tmp_path / f"{name}.{fmt}"


def _digests() -> dict[str, str]:
    out = {}
    for line in (FIXTURES / "chunked_parquet_digests.txt").read_text().splitlines():
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plain_email(tmp_path: Path, table: pa.Table) -> list:
    """The hashed column of a plain run (tokens, not source values)."""
    plain_dir = tmp_path / "plain"
    plain_dir.mkdir()
    cfg = _typed_config(plain_dir, table.select(["email"]))
    assert runner.invoke(app, ["run", str(cfg)]).exit_code == 0
    return pq.read_table(_out(plain_dir, "parquet")).column("email").to_pylist()


class TestChunkedKeepsSourceTypes:
    def test_at_c1_nullable_int_uint64_date_keep_type_and_value(self, tmp_path: Path) -> None:
        src = _fixture_f()
        cfg = _typed_config(tmp_path, src)
        result = _run_chunked(cfg)
        assert result.exit_code == 0, result.output
        out = pq.read_table(_out(tmp_path, "parquet"))
        assert out.schema.field("n").type == pa.int64()
        assert out.schema.field("u").type == pa.uint64()
        assert out.schema.field("d").type == pa.date32()
        assert out.schema.field("email").type == pa.string()
        for col in ("id", "n", "u", "d"):
            assert out.column(col).to_pylist() == src.column(col).to_pylist()
        assert out.column("email").to_pylist() == _plain_email(tmp_path, src)
        digests = _digests()
        assert digests["pyarrow"] == pa.__version__, "pyarrow moved: update the digest golden"
        assert _sha(_out(tmp_path, "parquet")) == digests["F"]

    def test_at_c2_csv_target_writes_exact_integers(self, tmp_path: Path) -> None:
        cfg = _typed_config(tmp_path, _fixture_f(), tgt_fmt="csv")
        result = _run_chunked(cfg)
        assert result.exit_code == 0, result.output
        rows = pd.read_csv(_out(tmp_path, "csv"), dtype=str, keep_default_na=False)
        assert rows.loc[3, "n"] == "9007199254740993"
        assert rows.loc[1, "u"] == "9223372036854775813"
        assert rows.loc[2, "u"] == "18446744073709551615"

    def test_at_c3_chunk_size_does_not_change_values_or_types(self, tmp_path: Path) -> None:
        cfg = _typed_config(tmp_path, _fixture_f())
        seen = []
        for size in (1, 3, 7, 100):
            assert _run_chunked(cfg, size).exit_code == 0
            out = pq.read_table(_out(tmp_path, "parquet"))
            seen.append((out.schema.remove_metadata(), out.to_pydict()))
        assert all(s == seen[0] for s in seen)
        csv_dir = tmp_path / "csv"
        csv_dir.mkdir()
        cfg_csv = _typed_config(csv_dir, _fixture_f(), tgt_fmt="csv")
        blobs = []
        for size in (1, 3, 7, 100):
            assert _run_chunked(cfg_csv, size).exit_code == 0
            blobs.append(_out(csv_dir, "csv").read_bytes())
        assert len(set(blobs)) == 1

    def test_at_c4_chunk_zero_all_null_in_a_typed_column(self, tmp_path: Path) -> None:
        src = _fixture_f().take(list(range(8, -1, -1)))
        cfg = _typed_config(tmp_path, src)
        result = _run_chunked(cfg)
        assert result.exit_code == 0, result.output
        out = pq.read_table(_out(tmp_path, "parquet"))
        assert [str(f.type) for f in out.schema] == [
            "int64",
            "int64",
            "uint64",
            "date32[day]",
            "string",
        ]
        for col in ("n", "u", "d"):
            assert out.column(col).to_pylist() == src.column(col).to_pylist()

    def test_at_c8_empty_parquet_keeps_a_required_column(self, tmp_path: Path) -> None:
        schema = pa.schema(
            [_field("req", pa.int64(), nullable=False), _field("email", pa.string())]
        )
        cfg = _typed_config(tmp_path, schema.empty_table())
        result = _run_chunked(cfg)
        assert result.exit_code == 0, result.output
        out = pq.read_table(_out(tmp_path, "parquet"))
        assert out.num_rows == 0
        assert out.schema.field("req").nullable is False
        assert out.schema.field("email").type == pa.string()

    def test_at_c8_empty_csv_source_publishes_its_header(self, tmp_path: Path) -> None:
        """Control (green on base). A header-only CSV source publishes a header-only file; a
        stream that yields no table at all publishes nothing (`test_atomic_output.py`)."""
        src = tmp_path / "e.csv"
        src.write_text("email\n", encoding="utf-8")
        cfg = {
            "version": 2,
            "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
            "sources": {"t": file_source(src, "csv")},
            "tables": [
                {"name": "t", "columns": [{"name": "email", "strategy": "hash", "namespace": "e"}]}
            ],
            "targets": {"t": {"type": "file", "format": "csv", "path": str(tmp_path / "o.csv")}},
        }
        path = tmp_path / "e.yaml"
        path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        assert runner.invoke(app, ["run", str(path), "--chunked"]).exit_code == 0
        assert (tmp_path / "o.csv").read_bytes() == b'"email"\n'

    def test_at_c8_undeclared_source_column_is_refused_before_any_read(
        self, tmp_path: Path
    ) -> None:
        src = _fixture_f()
        cfg = _typed_config(tmp_path, src)
        data = yaml.safe_load(cfg.read_text())
        data["tables"][0]["columns"] = [c for c in data["tables"][0]["columns"] if c["name"] != "n"]
        cfg.write_text(yaml.safe_dump(data), encoding="utf-8")
        result = _run_chunked(cfg)
        assert result.exit_code != 0
        assert "undeclared" in result.output
        assert not _out(tmp_path, "parquet").exists()

    def test_at_c9_type_matrix_parquet_target(self, tmp_path: Path) -> None:
        src = _fixture_m()
        cfg = _typed_config(tmp_path, src)
        result = _run_chunked(cfg)
        assert result.exit_code == 0, result.output
        out_path = _out(tmp_path, "parquet")
        out = pq.read_table(out_path)
        assert (FIXTURES / "chunked_type_matrix.schema.txt").read_text() == (
            out.schema.to_string(show_schema_metadata=True)
        )
        assert _sha(out_path) == _digests()["M"]
        for col in src.column_names:
            if col != "email":
                assert out.column(col).to_pylist() == src.column(col).to_pylist() or col == "f"
        assert out.schema.metadata is None or b"pandas" not in out.schema.metadata
        assert all(not f.metadata for f in out.schema)
        assert out.schema.field("req").nullable is False

    def test_at_c9_golden_matches_output_schema_of_the_source_schema(self) -> None:
        """The golden is the output schema of the source, never regenerated from a run."""
        from decoy_engine import output_schema

        expected = output_schema(_fixture_m().schema)
        assert (FIXTURES / "chunked_type_matrix.schema.txt").read_text() == expected.to_string(
            show_schema_metadata=True
        )

    def test_at_c10_type_matrix_csv_target(self, tmp_path: Path) -> None:
        from decoy.cli.io import write_table

        src = _fixture_m()
        cfg = _typed_config(tmp_path, src, tgt_fmt="csv")
        result = _run_chunked(cfg)
        assert result.exit_code == 0, result.output
        gold_dir = tmp_path / "gold"
        gold_dir.mkdir()
        gold = gold_dir / "gold.csv"
        write_table(src.drop_columns(["email"]), "csv", gold)
        got = pd.read_csv(_out(tmp_path, "csv"), dtype=str, keep_default_na=False)
        want = pd.read_csv(gold, dtype=str, keep_default_na=False)
        for col in want.columns:
            assert got[col].tolist() == want[col].tolist(), col
        assert got.loc[0, "d256"] == "1.25"
        assert got.loc[1, "d256"] == "3.50"
        assert got.loc[2, "u64"] == "18446744073709551615"
        plain = _plain_email(tmp_path, src.select(["email"]))
        assert got["email"].tolist() == [("" if v is None else v) for v in plain]

    def test_at_c17_all_null_masked_chunks_stay_string(self, tmp_path: Path) -> None:
        nul = [None, None]
        src = pa.table(
            {
                "h": pa.array(["a", "b", *nul], pa.string()),
                "t": pa.array(["abcdef", "ghijkl", *nul], pa.string()),
                "r": pa.array(["x", "y", *nul], pa.string()),
                "c": pa.array(["p", "q", *nul], pa.string()),
            }
        )
        cfg = _typed_config(tmp_path, src, hashed=())
        data = yaml.safe_load(cfg.read_text())
        specs = {
            "h": {"strategy": "hash", "namespace": "h_ns"},
            "t": {"strategy": "truncate", "provider_config": {"length": 3}},
            "r": {"strategy": "redact"},
            "c": {
                "strategy": "categorical",
                "deterministic": True,
                "namespace": "c_ns",
                "provider_config": {"categories": ["p", "q", "z"]},
            },
        }
        data["tables"][0]["columns"] = [{"name": k, **v} for k, v in specs.items()]
        cfg.write_text(yaml.safe_dump(data), encoding="utf-8")
        result = _run_chunked(cfg, 2)
        assert result.exit_code == 0, result.output
        out = pq.read_table(_out(tmp_path, "parquet"))
        assert (FIXTURES / "chunked_all_null_masked.schema.txt").read_text() == (
            out.schema.to_string(show_schema_metadata=True)
        )


_REFUSED_SOURCES = {
    "time64_ns": pa.table(
        {
            "t": pa.array([1, 2, 3, 3_600_000_000_000 + 987654321], pa.time64("ns")),
            "email": ["a@x.com", "b@x.com", "c@x.com", "d@x.com"],
        }
    ),
    "date32_far": pa.table(
        {
            "t": pa.array([0, 1, 2, -1_000_000], pa.date32()),
            "email": ["a@x.com", "b@x.com", "c@x.com", "d@x.com"],
        }
    ),
}


def _direct(tmp_path: Path, cfg: Path, **kwargs: object) -> dict:
    """Run the chunked coordinator without the CLI preflight, which profiles a source with
    pandas and refuses these files before the engine is reached (see the S2 report)."""
    from decoy.cli.io import RunLayout
    from decoy.cli.run._execute import _run_chunked_mask

    config_dict = yaml.safe_load(cfg.read_text())
    return _run_chunked_mask(config_dict, cfg.parent, 2, RunLayout.fixed(tmp_path), **kwargs)


class TestValuesPandasRefuses:
    @pytest.mark.parametrize("case", sorted(_REFUSED_SOURCES))
    def test_at_c12_the_cli_preflight_refuses_these_sources_first(
        self, tmp_path: Path, case: str
    ) -> None:
        """Characterization: `decoy run` profiles the source with pandas before it streams, so
        a value pandas refuses ends the run at preflight on every leg, `--no-native` included."""
        cfg = _typed_config(tmp_path, _REFUSED_SOURCES[case])
        for extra in ((), ("--no-native",)):
            result = _run_chunked(cfg, 2, *extra)
            assert result.exit_code == 1, result.output
            assert "source not parsed" in result.output
        assert not _out(tmp_path, "parquet").exists()

    @pytest.mark.parametrize("case", sorted(_REFUSED_SOURCES))
    def test_at_c12_default_runs_exact_and_no_native_fails(self, tmp_path: Path, case: str) -> None:
        src = _REFUSED_SOURCES[case]
        cfg = _typed_config(tmp_path, src)
        _direct(tmp_path, cfg)
        out = pq.read_table(_out(tmp_path, "parquet"))
        assert out.column("t").equals(src.column("t"))
        _out(tmp_path, "parquet").unlink()
        with pytest.raises(Exception) as caught:  # F6: raw, uncoded pandas or pyarrow error
            _direct(tmp_path, cfg, pandas_only=True)
        print(
            f"AT-C12 refused-value {case}: {type(caught.value).__module__}."
            f"{type(caught.value).__name__}"
        )
        assert getattr(caught.value, "code", None) is None

    @pytest.mark.parametrize("case", sorted(_REFUSED_SOURCES))
    def test_at_c14_a_read_refused_value_is_coded_and_value_free(
        self, tmp_path: Path, case: str
    ) -> None:
        from decoy_engine import ExecutionError

        cfg = _typed_config(tmp_path, _REFUSED_SOURCES[case], when={"email": "t != 'q'"})
        with pytest.raises(ExecutionError) as caught:
            _direct(tmp_path, cfg)
        assert caught.value.code == "chunked_passthrough_value_unrepresentable"
        text = str(caught.value)
        for marker in ("987654321", "out of range", "nanoseconds", "-1000000"):
            assert marker not in text
