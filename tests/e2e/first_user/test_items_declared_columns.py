"""`decoy validate` refuses a declared column the source lacks, as `decoy run` does (row 24b).

GATE-05: the gate's preflight layer only checked that source files exist, so `validate`
exited 0 on a config `run` refuses before any row. The layer now asks the one engine check
(`prepared_sources`) that `run` asks. GATE-06: `fpe` with no namespace is refused at validate.
Remote sources are never opened at validate; each gets a not-checked warning.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from decoy_engine import parse_pipeline_config
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_OK, EXIT_USAGE, EXIT_WARNINGS
from tests.csv_sources import csv_source

runner = CliRunner()

UNDECLARED = "source_file.declared_column_missing"


def _write(tmp_path: Path, sources: dict[str, Any], columns: list[dict[str, Any]]) -> Path:
    cfg = {
        "version": 2,
        "global_settings": {"seed": 3},
        "sources": sources,
        "tables": [{"name": "people", "columns": columns}],
        "targets": {"people": {"type": "file", "format": "csv", "path": str(tmp_path / "o.csv")}},
    }
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def _codes(result: Any) -> list[tuple[str, str]]:
    assert result.stdout, f"no JSON: {result.output!r} {result.exception!r}"
    return [(m["layer"], m["code"]) for m in json.loads(result.stdout)["messages"]]


def _validate(config: Path, *extra: str) -> Any:
    return runner.invoke(app, ["validate", str(config), "--json", *extra])


def test_g5_a_declared_column_missing_from_the_source_exits_1(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    src.write_text("name\nAda\n", encoding="utf-8")
    config = _write(
        tmp_path,
        {"people": csv_source(src)},
        [{"name": "name", "strategy": "redact"}, {"name": "email", "strategy": "redact"}],
    )
    result = _validate(config)
    assert result.exit_code == EXIT_USAGE, result.output
    assert ("preflight", UNDECLARED) in _codes(result)
    run = runner.invoke(app, ["run", str(config), "--json"])
    assert run.exit_code == EXIT_USAGE
    assert UNDECLARED in run.output


def test_g5_the_column_check_reads_the_header_only(tmp_path: Path) -> None:
    from decoy.cli.preflight import _check_declared_columns, _PreflightAccumulator

    src = tmp_path / "in.csv"
    # A data row that cannot decode: a body read would fail with a different code.
    src.write_bytes(b"name\n\xff\xfe\xfd\n")
    config = _write(
        tmp_path, {"people": csv_source(src)}, [{"name": "name", "strategy": "redact"}]
    )
    validated = parse_pipeline_config(yaml.safe_load(config.read_text())).model_dump()
    acc = _PreflightAccumulator()
    _check_declared_columns(validated, tmp_path, acc)
    assert [c.status for c in acc.checks] == ["pass"]


def test_g5b_a_headerless_csv_with_too_few_column_names_exits_1(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    src.write_text("Ada\nBen\n", encoding="utf-8")
    config = _write(
        tmp_path,
        {"people": csv_source(src, has_header=False, column_names=["name"])},
        [{"name": "name", "strategy": "redact"}, {"name": "email", "strategy": "redact"}],
    )
    result = _validate(config)
    assert result.exit_code == EXIT_USAGE, result.output
    assert ("preflight", UNDECLARED) in _codes(result)


def test_g5b_a_missing_source_file_stays_one_finding(tmp_path: Path) -> None:
    config = _write(
        tmp_path,
        {"people": csv_source(tmp_path / "absent.csv")},
        [{"name": "name", "strategy": "redact"}],
    )
    result = _validate(config)
    assert result.exit_code == EXIT_USAGE, result.output
    preflight = [c for layer, c in _codes(result) if layer == "preflight"]
    assert preflight == ["source.people.exists"]


def test_g5_validate_preflight_alone_refuses_the_same_config(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    src.write_text("name\nAda\n", encoding="utf-8")
    config = _write(
        tmp_path,
        {"people": csv_source(src)},
        [{"name": "name", "strategy": "redact"}, {"name": "email", "strategy": "redact"}],
    )
    result = runner.invoke(app, ["validate", "preflight", str(config), "--json"])
    assert result.exit_code == EXIT_USAGE, result.output
    codes = [c["code"] for c in json.loads(result.stdout)["checks"]]
    assert UNDECLARED in codes


def _s3_config(tmp_path: Path) -> Path:
    s3 = {"type": "s3", "format": "csv", "bucket": "b", "key": "k.csv" }
    return _write(
        tmp_path,
        {"people": s3},
        [{"name": "name", "strategy": "redact"}, {"name": "email", "strategy": "redact"}],
    )


def test_g5c_a_remote_source_is_not_opened_and_warns(tmp_path: Path, monkeypatch: Any) -> None:
    def _no_network(*_a: Any, **_k: Any) -> None:
        raise AssertionError("validate must not open a remote source")

    monkeypatch.setattr("decoy_engine.profile._cloud_readers.build_s3_profile_source", _no_network)
    config = _s3_config(tmp_path)

    result = _validate(config)
    assert result.exit_code == EXIT_OK, result.output
    warnings = [m for m in json.loads(result.stdout)["messages"] if m["severity"] == "warning"]
    assert any("declared columns not checked" in m["message"] for m in warnings), result.output

    strict = _validate(config, "--fail-on-warning")
    assert strict.exit_code == EXIT_WARNINGS, strict.output


def test_g6_fpe_without_a_namespace_exits_1_at_validate(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    src.write_text("ssn\n123456789\n", encoding="utf-8")
    config = _write(
        tmp_path,
        {"people": csv_source(src)},
        [{"name": "ssn", "strategy": "fpe", "provider_config": {"charset": "digits"}}],
    )
    result = _validate(config)
    assert result.exit_code == EXIT_USAGE, result.output
    assert "fpe_requires_namespace" in [c for _, c in _codes(result)]
