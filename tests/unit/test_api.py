"""Unit tests for the S6 library one-liner API (`decoy.mask` / `decoy.scan`).

`decoy.api` is a thin wrapper over `decoy_engine.run_pipeline` /
`decoy_engine.profile_columns` -- the SAME entrypoints `decoy run` /
`decoy scan` call. These tests prove:

  1. Basic mask/scan behavior (round-trip, keyed determinism, generate
     tables, multi-table dict data, error handling for malformed
     mask-secret / target / data shapes).
  2. Parity: `decoy.mask(...)` on a config produces byte-identical output
     to `decoy run <same config>.yaml` (test_mask_parity_with_cli_run*),
     and `decoy.scan(...)` on a file produces the identical ColumnProfile
     to `decoy scan <same file>` (test_scan_parity_with_cli*).

See src/decoy/api.py for the design notes (why `data`/`out` need staged
placeholder sources/targets before PipelineConfig validation).
"""

from __future__ import annotations

import json as _json
import os
import secrets
from pathlib import Path

import pandas as pd
import pytest
import yaml
from tests.csv_sources import csv_source
from typer.testing import CliRunner

import decoy
from decoy.__main__ import app
from decoy.api import ConfigValidationError, MaskSecretConfigError
from decoy.cli.exit_codes import EXIT_USAGE

runner = CliRunner()


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["C1", "C2", "C3"],
            "first_name": ["Alice", "Bob", "Carol"],
            "email": ["a@example.com", "b@example.com", "c@example.com"],
            "ssn": ["111-22-3333", "444-55-6666", "777-88-9999"],
        }
    )


@pytest.fixture
def sample_csv(tmp_path: Path, sample_df: pd.DataFrame) -> Path:
    path = tmp_path / "input.csv"
    sample_df.to_csv(path, index=False)
    return path


def _mask_config_dict(source_path: Path, target_path: Path) -> dict:
    """Minimal V2 PipelineConfig mask config, same shape as
    tests/e2e/test_run_command.py's `mask_config` fixture."""
    return {
        "version": 2,
        "global_settings": {"seed": 42},
        "sources": {
            "customers": csv_source(source_path),
        },
        "tables": [
            {
                "name": "customers",
                "columns": [
                    {"name": "customer_id", "strategy": "passthrough"},
                    {"name": "first_name", "strategy": "faker", "provider": "person_first_name"},
                    {"name": "email", "strategy": "faker", "provider": "person_email"},
                    {"name": "ssn", "strategy": "redact"},
                ],
            },
        ],
        "targets": {
            "customers": {"type": "file", "format": "csv", "path": str(target_path)},
        },
    }


@pytest.fixture
def mask_config_path(tmp_path: Path, sample_csv: Path) -> Path:
    config = _mask_config_dict(sample_csv, tmp_path / "masked.csv")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    return path


# --------------------------------------------------------------------------
# decoy.mask -- basic behavior
# --------------------------------------------------------------------------


def test_mask_dataframe_in_memory_roundtrip(sample_df: pd.DataFrame, tmp_path: Path):
    config = {
        "version": 2,
        "global_settings": {"seed": 42},
        "tables": [
            {
                "name": "customers",
                "columns": [
                    {"name": "customer_id", "strategy": "passthrough"},
                    {"name": "first_name", "strategy": "faker", "provider": "person_first_name"},
                    {"name": "email", "strategy": "passthrough"},
                    {"name": "ssn", "strategy": "redact"},
                ],
            },
        ],
    }
    out = decoy.mask(sample_df, config, out=str(tmp_path / "masked.csv"))

    assert isinstance(out, pd.DataFrame)
    assert len(out) == len(sample_df)
    assert out["customer_id"].tolist() == sample_df["customer_id"].tolist()
    assert out["first_name"].tolist() != sample_df["first_name"].tolist()
    assert (out["ssn"] == "REDACTED").all()
    assert (tmp_path / "masked.csv").exists()


def test_mask_config_path_data_none_uses_declared_sources(mask_config_path: Path, tmp_path: Path):
    """data=None mirrors `decoy run pipeline.yaml`: sources load from the
    config's own declared `sources:` block."""
    out = decoy.mask(None, mask_config_path)

    assert isinstance(out, pd.DataFrame)
    assert (tmp_path / "masked.csv").exists()
    assert out["customer_id"].tolist() == ["C1", "C2", "C3"]


def test_mask_does_not_mutate_caller_config_dict(sample_df: pd.DataFrame, tmp_path: Path):
    config = {
        "version": 2,
        "global_settings": {"seed": 42},
        "tables": [
            {"name": "t", "columns": [{"name": "customer_id", "strategy": "passthrough"}]},
        ],
    }
    original = _json.dumps(config, sort_keys=True)
    decoy.mask(sample_df[["customer_id"]], config, out=str(tmp_path / "o.csv"))
    assert _json.dumps(config, sort_keys=True) == original


def test_mask_dict_data_multi_table(tmp_path: Path):
    df_a = pd.DataFrame({"id": ["A1", "A2"]})
    df_b = pd.DataFrame({"id": ["B1", "B2"], "email": ["x@example.com", "y@example.com"]})
    config = {
        "version": 2,
        "global_settings": {"seed": 7},
        "tables": [
            {"name": "table_a", "columns": [{"name": "id", "strategy": "passthrough"}]},
            {
                "name": "table_b",
                "columns": [
                    {"name": "id", "strategy": "passthrough"},
                    {"name": "email", "strategy": "faker", "provider": "person_email"},
                ],
            },
        ],
    }
    out = decoy.mask(
        {"table_a": df_a, "table_b": df_b},
        config,
        out={
            "table_a": str(tmp_path / "a.csv"),
            "table_b": str(tmp_path / "b.csv"),
        },
    )

    assert isinstance(out, dict)
    assert set(out) == {"table_a", "table_b"}
    assert out["table_a"]["id"].tolist() == ["A1", "A2"]
    assert out["table_b"]["email"].tolist() != df_b["email"].tolist()
    assert (tmp_path / "a.csv").exists()
    assert (tmp_path / "b.csv").exists()


def test_mask_generate_table(tmp_path: Path):
    config = {
        "version": 2,
        "global_settings": {"seed": 42},
        "sources": {},
        "tables": [
            {
                "name": "employees",
                "row_count": 5,
                "generate_columns": [
                    {"name": "employee_id", "type": "sequence", "start": 1000, "step": 1},
                    {"name": "first_name", "type": "faker", "faker_type": "first_name"},
                ],
            },
        ],
        "targets": {
            "employees": {"type": "file", "format": "csv", "path": str(tmp_path / "employees.csv")},
        },
    }
    out = decoy.mask(None, config)

    assert isinstance(out, pd.DataFrame)
    assert len(out) == 5
    assert "employee_id" in out.columns
    assert (tmp_path / "employees.csv").exists()


def test_mask_keyed_secret_deterministic_across_calls(tmp_path: Path, monkeypatch):
    secret = secrets.token_hex(32)
    monkeypatch.setenv("DECOY_TEST_MASK_SECRET", secret)
    df = pd.DataFrame({"email": ["a@example.com", "b@example.com"]})
    config = {
        "version": 2,
        "global_settings": {"seed": 1},
        "tables": [
            {
                "name": "t",
                "columns": [{"name": "email", "strategy": "faker", "provider": "person_email"}],
            },
        ],
    }
    out1 = decoy.mask(
        df, config, mask_secret="env:DECOY_TEST_MASK_SECRET", out=str(tmp_path / "o1.csv")
    )
    out2 = decoy.mask(
        df, config, mask_secret="env:DECOY_TEST_MASK_SECRET", out=str(tmp_path / "o2.csv")
    )
    assert out1["email"].tolist() == out2["email"].tolist()


# --------------------------------------------------------------------------
# decoy.mask -- error handling / fail-closed guarantees
# --------------------------------------------------------------------------


def test_mask_requires_config():
    with pytest.raises(TypeError):
        decoy.mask(pd.DataFrame({"a": [1]}))


def test_mask_no_targets_and_no_out_raises(tmp_path: Path):
    config = {
        "version": 2,
        "global_settings": {"seed": 1},
        "tables": [{"name": "t", "columns": [{"name": "a", "strategy": "passthrough"}]}],
    }
    with pytest.raises(ConfigValidationError, match="no targets"):
        decoy.mask(pd.DataFrame({"a": [1]}), config)


def test_mask_ambiguous_dataframe_multi_table_raises():
    config = {
        "version": 2,
        "global_settings": {"seed": 1},
        "tables": [
            {"name": "t1", "columns": [{"name": "a", "strategy": "passthrough"}]},
            {"name": "t2", "columns": [{"name": "a", "strategy": "passthrough"}]},
        ],
    }
    with pytest.raises(ValueError, match="pass a dict keyed by table name"):
        decoy.mask(
            pd.DataFrame({"a": [1]}),
            config,
            out={"t1": "/tmp/decoy-test-o1.csv", "t2": "/tmp/decoy-test-o2.csv"},
        )


def test_mask_invalid_mask_secret_ref_raises(tmp_path: Path):
    config = {
        "version": 2,
        "global_settings": {"seed": 1},
        "tables": [{"name": "t", "columns": [{"name": "a", "strategy": "passthrough"}]}],
    }
    with pytest.raises(MaskSecretConfigError, match="REFERENCE, never the raw secret"):
        decoy.mask(
            pd.DataFrame({"a": [1]}),
            config,
            mask_secret="not-a-valid-ref",
            out=str(tmp_path / "o.csv"),
        )


def test_mask_secret_set_in_both_places_raises(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DECOY_TEST_MASK_SECRET_2", secrets.token_hex(32))
    config = {
        "version": 2,
        "global_settings": {"seed": 1, "mask_secret_ref": "env:DECOY_TEST_MASK_SECRET_2"},
        "tables": [{"name": "t", "columns": [{"name": "a", "strategy": "passthrough"}]}],
    }
    with pytest.raises(MaskSecretConfigError, match="already sets"):
        decoy.mask(
            pd.DataFrame({"a": [1]}),
            config,
            mask_secret="env:DECOY_TEST_MASK_SECRET_2",
            out=str(tmp_path / "o.csv"),
        )


def test_mask_malformed_mask_secret_ref_shape_raises_before_pydantic_echo():
    """A non-string mask_secret_ref must never reach PipelineConfig's
    ValidationError (which would echo the raw value verbatim) -- DE-02
    secret-disclosure ROOT guard, ported from decoy.cli.run."""
    config = {
        "version": 2,
        "global_settings": {"seed": 1, "mask_secret_ref": ["not", "a", "string"]},
        "tables": [{"name": "t", "columns": [{"name": "a", "strategy": "passthrough"}]}],
        "targets": {"t": {"type": "file", "format": "csv", "path": "/tmp/decoy-test-x.csv"}},
    }
    with pytest.raises(MaskSecretConfigError):
        decoy.mask(pd.DataFrame({"a": [1]}), config)


def test_mask_invalid_config_shape_raises_config_validation_error(tmp_path: Path):
    """An unknown top-level key trips PipelineConfig's `extra="forbid"`
    schema gate -- a genuine config-shape error, distinct from an
    unsupported strategy name (which validates fine at the schema level
    and only fails later, at execution, as an engine ExecutionError --
    not this library's concern to reclassify)."""
    config = {
        "version": 2,
        "global_settings": {"seed": 1},
        "tables": [{"name": "t", "columns": [{"name": "a", "strategy": "passthrough"}]}],
        "targets": {"t": {"type": "file", "format": "csv", "path": str(tmp_path / "o.csv")}},
        "bogus_unknown_top_level_key": True,
    }
    with pytest.raises(ConfigValidationError):
        decoy.mask(pd.DataFrame({"a": [1]}), config)


def test_mask_master_key_requires_key_label():
    with pytest.raises(ValueError, match="key_label"):
        decoy.mask(
            pd.DataFrame({"a": [1]}),
            {
                "version": 2,
                "global_settings": {"seed": 1},
                "tables": [{"name": "t", "columns": [{"name": "a", "strategy": "passthrough"}]}],
                "targets": {
                    "t": {"type": "file", "format": "csv", "path": "/tmp/decoy-test-mk.csv"}
                },
            },
            master_key=secrets.token_hex(32),
        )


# --------------------------------------------------------------------------
# decoy.mask -- parity with `decoy run`
# --------------------------------------------------------------------------


def test_mask_parity_with_cli_run(mask_config_path: Path, sample_csv: Path, tmp_path: Path):
    """`decoy.mask(None, config)` on the SAME config `decoy run` uses must
    produce byte-identical masked output (same seed -> same determinism)."""
    cli_target = tmp_path / "masked.csv"

    result = runner.invoke(app, ["run", str(mask_config_path)])
    assert result.exit_code == 0, result.stdout
    cli_output = pd.read_csv(cli_target, dtype=str)
    cli_target.unlink()  # so the library call below writes a fresh file

    lib_output = decoy.mask(None, mask_config_path)

    assert cli_output.astype(str).equals(lib_output.astype(str))
    assert cli_target.exists()
    lib_written = pd.read_csv(cli_target, dtype=str)
    assert cli_output.equals(lib_written)


def test_mask_parity_dataframe_matches_cli_csv_source(
    sample_df: pd.DataFrame, sample_csv: Path, tmp_path: Path
):
    """A DataFrame passed directly to decoy.mask() must produce the same
    masked values as `decoy run` masking the equivalent CSV, for the same
    seed -- proving the DataFrame path is not a different code path."""
    config = _mask_config_dict(sample_csv, tmp_path / "cli_masked.csv")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    result = runner.invoke(app, ["run", str(config_path)])
    assert result.exit_code == 0, result.stdout
    cli_output = pd.read_csv(tmp_path / "cli_masked.csv", dtype=str)

    lib_config = {k: v for k, v in config.items() if k != "sources"}
    lib_output = decoy.mask(sample_df, lib_config, out=str(tmp_path / "lib_masked.csv"))

    assert (
        cli_output.astype(str)
        .reset_index(drop=True)
        .equals(lib_output.astype(str).reset_index(drop=True))
    )


# --------------------------------------------------------------------------
# decoy.scan -- basic behavior
# --------------------------------------------------------------------------


def test_scan_dataframe_returns_profile(sample_df: pd.DataFrame):
    profile = decoy.scan(sample_df, source_label="customers")

    assert profile.source_label == "customers"
    assert profile.row_count == len(sample_df)
    field_names = {f.name for f in profile.fields}
    assert field_names == set(sample_df.columns)
    ssn_field = next(f for f in profile.fields if f.name == "ssn")
    assert ssn_field.pii_score > 0.5


def test_scan_path_csv(sample_csv: Path):
    profile = decoy.scan(sample_csv)
    assert profile.source_label == sample_csv.name
    assert profile.row_count == 3


def test_scan_invalid_strategy_raises():
    with pytest.raises(ValueError, match="strategy must be one of"):
        decoy.scan(pd.DataFrame({"a": [1]}), strategy="bogus")


def test_scan_invalid_data_type_raises():
    with pytest.raises(TypeError):
        decoy.scan(12345)


# --------------------------------------------------------------------------
# decoy.scan -- parity with `decoy scan`
# --------------------------------------------------------------------------


def test_scan_parity_with_cli_scan(sample_csv: Path, tmp_path: Path):
    scan_out = tmp_path / "scan.json"
    result = runner.invoke(app, ["scan", str(sample_csv), "--has-header", "--output", str(scan_out)])
    assert result.exit_code == 0, result.stdout
    # --output holds the value-free scan-set/v1 core; its table is named from the file stem.
    cli_profile = _json.loads(scan_out.read_text())["tables"][0]

    lib_profile = decoy.scan(sample_csv).to_dict()

    assert lib_profile["row_count"] == cli_profile["row_count"]
    assert Path(lib_profile["source_label"]).stem == cli_profile["name"]
    assert lib_profile["reid_risk_score"] == cli_profile["reid_risk_score"]
    lib_fields = {f["name"]: f["pii_score"] for f in lib_profile["fields"]}
    cli_fields = {f["name"]: f["pii_score"] for f in cli_profile["fields"]}
    assert lib_fields == cli_fields


# --------------------------------------------------------------------------
# decoy.mask -- cloud endpoints fail closed
#
# `decoy.mask()` must refuse an s3/gcs source or target before the engine
# runs, exactly as `decoy run` does: the refusal sits in the I/O helpers both
# paths share. Without it an s3 source with [cloud] absent surfaces as a
# ModuleNotFoundError from the engine's profiler, and a gcs target runs the
# whole pipeline and then drops the output. These tests go through the
# public `decoy.mask()` entry, not the helper.
# --------------------------------------------------------------------------


_CLOUD_MODULES = ("boto3", "botocore", "google", "google.cloud", "google.cloud.storage")


@pytest.fixture
def no_cloud_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every [cloud] SDK import fail with ModuleNotFoundError, whatever
    this venv happens to have installed."""
    import sys

    for name in _CLOUD_MODULES:
        monkeypatch.setitem(sys.modules, name, None)


@pytest.fixture
def engine_must_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal has to happen before the engine is invoked."""

    def _boom(*_args, **_kwargs):
        raise AssertionError("run_pipeline was called; the cloud refusal came too late")

    monkeypatch.setattr("decoy_engine.run_pipeline", _boom)


def _single_table_config(source: dict, target: dict) -> dict:
    return {
        "version": 2,
        "global_settings": {"seed": 42},
        "sources": {"customers": source},
        "tables": [
            {
                "name": "customers",
                "columns": [
                    {"name": "customer_id", "strategy": "passthrough"},
                    {"name": "ssn", "strategy": "redact"},
                ],
            },
        ],
        "targets": {"customers": target},
    }


def test_mask_s3_source_without_cloud_extra_fails_closed(
    tmp_path: Path, no_cloud_extra: None, engine_must_not_run: None
):
    config = _single_table_config(
        {"type": "s3", "format": "csv", "bucket": "test-bucket", "key": "customers.csv"},
        {"type": "file", "format": "csv", "path": str(tmp_path / "out.csv")},
    )
    with pytest.raises(decoy.UnsupportedCloudEndpointError) as excinfo:
        decoy.mask(None, config)
    message = str(excinfo.value)
    assert "s3 source 'customers'" in message
    assert "cannot run through" in message
    assert not (tmp_path / "out.csv").exists()


def test_mask_gcs_target_fails_closed_instead_of_dropping_output(
    sample_csv: Path, tmp_path: Path, no_cloud_extra: None, engine_must_not_run: None
):
    config = _single_table_config(
        csv_source(sample_csv),
        {"type": "gcs", "format": "csv", "bucket": "test-bucket", "object": "out.csv"},
    )
    with pytest.raises(decoy.UnsupportedCloudEndpointError) as excinfo:
        decoy.mask(None, config)
    assert "gcs target 'customers'" in str(excinfo.value)


def test_mask_cloud_refusal_matches_cli_run(tmp_path: Path, no_cloud_extra: None):
    """Same config, same refusal text from both entry points."""
    config = _single_table_config(
        {"type": "s3", "format": "csv", "bucket": "test-bucket", "key": "customers.csv"},
        {"type": "file", "format": "csv", "path": str(tmp_path / "out.csv")},
    )
    with pytest.raises(decoy.UnsupportedCloudEndpointError) as excinfo:
        decoy.mask(None, config)

    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    result = runner.invoke(app, ["run", str(config_path)])
    assert result.exit_code == EXIT_USAGE, result.output
    assert " ".join(str(excinfo.value).split()) in " ".join(result.output.split())


# --------------------------------------------------------------------------
# Lazy module attribute access (decoy/__init__.py PEP 562 __getattr__)
# --------------------------------------------------------------------------


def test_decoy_module_exposes_mask_and_scan():
    assert callable(decoy.mask)
    assert callable(decoy.scan)
    assert "mask" in dir(decoy)
    assert "scan" in dir(decoy)


def test_decoy_module_unknown_attribute_raises():
    with pytest.raises(AttributeError):
        _ = decoy.definitely_not_a_real_attribute


# --------------------------------------------------------------------------
# decoy.mask -- two outputs on one destination (DUP-DEST CL1)
# --------------------------------------------------------------------------


@pytest.fixture
def nothing_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """The collision refusal comes before any source read and before the engine runs."""

    def _no_read(*_args, **_kwargs):
        raise AssertionError("a source was read before the collision refusal")

    def _no_run(*_args, **_kwargs):
        raise AssertionError("run_pipeline was called before the collision refusal")

    monkeypatch.setattr("decoy.api._load_sources_from_config", _no_read)
    monkeypatch.setattr("decoy_engine.run_pipeline", _no_run)


def _two_tables(tmp_path: Path, path_a: str, path_b: str) -> dict:
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    for name in ("ta", "tb"):
        pd.DataFrame({"id": [f"{name}1", f"{name}2"]}).to_csv(src / f"{name}.csv", index=False)
    return {
        "version": 2,
        "global_settings": {"seed": 7},
        "sources": {n: csv_source(src / f"{n}.csv") for n in ("ta", "tb")},
        "tables": [
            {"name": n, "columns": [{"name": "id", "strategy": "passthrough"}]}
            for n in ("ta", "tb")
        ],
        "targets": {
            "ta": {"type": "file", "format": "csv", "path": path_a},
            "tb": {"type": "file", "format": "csv", "path": path_b},
        },
    }


def _assert_collision(exc: pytest.ExceptionInfo, *locations: str) -> None:
    from decoy.cli.io import LayoutError

    assert isinstance(exc.value, LayoutError)
    assert exc.value.code == "layout.output_path_collision"
    for location in locations:
        assert location in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__context__ is None


def test_mask_refuses_two_targets_on_one_absolute_path(tmp_path: Path, nothing_runs: None):
    # Equal declarations are the engine's refusal since 0.26.0 (DUP-DEST E1), so mask() raises
    # its config error, not the CLI layout code (CL2, OQ-4).
    shared = tmp_path / "out" / "shared.csv"
    config = _two_tables(tmp_path, str(shared), str(shared))
    with pytest.raises(ConfigValidationError) as exc:
        decoy.mask(config=config)
    message = str(exc.value)
    assert "target_shared_destination" in message
    assert "targets.ta.path" in message and "targets.tb.path" in message
    assert str(shared) not in message
    assert exc.value.__cause__ is None and exc.value.__context__ is None
    assert not (tmp_path / "out").exists()


def test_mask_refuses_out_paths_that_meet_through_a_symlinked_folder(
    tmp_path: Path, nothing_runs: None
):
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    config = _two_tables(tmp_path, str(tmp_path / "a.csv"), str(tmp_path / "b.csv"))
    out = {"ta": str(real / "x.csv"), "tb": str(tmp_path / "link" / "x.csv")}
    with pytest.raises(Exception) as exc:
        decoy.mask(config=config, out=out)
    _assert_collision(exc, "targets.ta.path", "targets.tb.path")
    assert list(real.iterdir()) == []


@pytest.mark.parametrize(
    ("name_a", "name_b"),
    [("Out.csv", "out.csv"), ("café.csv", "café.csv")],
    ids=["case", "nfc-nfd"],
)
def test_mask_refuses_names_one_folding_volume_treats_as_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nothing_runs: None, name_a: str, name_b: str
):
    from decoy.cli.io import _placement

    monkeypatch.setattr(_placement, "_folds_case", lambda _folder: True)
    out = tmp_path / "out"
    out.mkdir()
    config = _two_tables(tmp_path, str(out / name_a), str(out / name_b))
    with pytest.raises(Exception) as exc:
        decoy.mask(config=config)
    _assert_collision(exc, "targets.ta.path", "targets.tb.path")
    assert list(out.iterdir()) == []


def test_mask_refuses_two_existing_hard_links(tmp_path: Path, nothing_runs: None):
    # An existing file's inode is its identity, as in `decoy run` and `decoy validate`.
    first = tmp_path / "first.csv"
    first.write_text("keep\n", encoding="utf-8")
    second = tmp_path / "second.csv"
    second.hardlink_to(first)
    config = _two_tables(tmp_path, str(first), str(second))
    with pytest.raises(Exception) as exc:
        decoy.mask(config=config)
    _assert_collision(exc, "targets.ta.path", "targets.tb.path")
    assert first.read_text(encoding="utf-8") == "keep\n"
    assert os.path.samefile(first, second)


def test_mask_refuses_quarantine_through_a_link_to_a_hard_linked_target(
    tmp_path: Path, nothing_runs: None
):
    # The quarantine writer truncates through a final symlink, so it would rewrite the
    # file a hard-linked target shares.
    shared = tmp_path / "shared.csv"
    shared.write_text("keep\n", encoding="utf-8")
    alias = tmp_path / "alias.csv"
    alias.hardlink_to(shared)
    link = tmp_path / "rows.jsonl"
    link.symlink_to(shared)
    config = _two_tables(tmp_path, str(alias), str(tmp_path / "b.csv"))
    config["quarantine"] = {"enabled": True, "output_path": str(link)}
    with pytest.raises(Exception) as exc:
        decoy.mask(config=config)
    _assert_collision(exc, "targets.ta.path", "quarantine.output_path")
    assert shared.read_text(encoding="utf-8") == "keep\n"


def test_mask_refuses_equal_targets_no_table_writes(tmp_path: Path, nothing_runs: None):
    # Every file target takes part, as in `decoy run` and `decoy validate`.
    config = _two_tables(tmp_path, str(tmp_path / "a.csv"), str(tmp_path / "b.csv"))
    unused = {"type": "file", "format": "csv", "path": str(tmp_path / "unused.csv")}
    config["targets"]["ghost_a"] = unused
    config["targets"]["ghost_b"] = dict(unused)
    with pytest.raises(Exception) as exc:
        decoy.mask(config=config)
    _assert_collision(exc, "targets.ghost_a.path", "targets.ghost_b.path")
    assert not (tmp_path / "unused.csv").exists()


def test_mask_refuses_a_relative_path_above_the_config_against_its_absolute_spelling(
    tmp_path: Path, nothing_runs: None
):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    config = _two_tables(tmp_path, "../shared.csv", str(tmp_path / "shared.csv"))
    path = cfg_dir / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(Exception) as exc:
        decoy.mask(config=path)
    _assert_collision(exc, "targets.ta.path", "targets.tb.path")
    assert not (tmp_path / "shared.csv").exists()


def test_mask_checks_dot_dot_where_the_writer_lands_it(tmp_path: Path, nothing_runs: None):
    # The writer joins a relative path lexically (`config_relative`), so `sub/../a.csv` lands
    # in the config folder even when `sub` is a link elsewhere; the check follows the writer.
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    deep = tmp_path / "real" / "deep"
    deep.mkdir(parents=True)
    (cfg_dir / "sub").symlink_to(deep, target_is_directory=True)
    config = _two_tables(tmp_path, "sub/../a.csv", str(cfg_dir / "a.csv"))
    path = cfg_dir / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(Exception) as exc:
        decoy.mask(config=path)
    _assert_collision(exc, "targets.ta.path", "targets.tb.path")
    assert not (cfg_dir / "a.csv").exists() and not (tmp_path / "real" / "a.csv").exists()


def test_mask_refuses_a_target_on_the_quarantine_file(tmp_path: Path, nothing_runs: None):
    shared = tmp_path / "rows.csv"
    config = _two_tables(tmp_path, str(shared), str(tmp_path / "b.csv"))
    config["quarantine"] = {"enabled": True, "output_path": str(shared)}
    with pytest.raises(Exception) as exc:
        decoy.mask(config=config)
    _assert_collision(exc, "targets.ta.path", "quarantine.output_path")
    assert not shared.exists() and not (tmp_path / "b.csv").exists()


def test_mask_distinct_targets_write_and_the_check_leaves_the_config_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import copy

    import decoy.api as api

    seen: list[tuple[dict, dict]] = []
    real_check = api._refuse_output_collisions

    def _spy(config_dict: dict, layout) -> None:
        before = copy.deepcopy(config_dict)
        real_check(config_dict, layout)
        seen.append((before, copy.deepcopy(config_dict)))

    monkeypatch.setattr(api, "_refuse_output_collisions", _spy)
    # Relative targets, so a check that placed them in the caller's dict would change it.
    config = _two_tables(tmp_path, "a.csv", "b.csv")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    out = decoy.mask(config=path)
    assert set(out) == {"ta", "tb"}
    assert pd.read_csv(tmp_path / "a.csv")["id"].tolist() == ["ta1", "ta2"]
    assert pd.read_csv(tmp_path / "b.csv")["id"].tolist() == ["tb1", "tb2"]
    ((before, after),) = seen
    assert before == after
