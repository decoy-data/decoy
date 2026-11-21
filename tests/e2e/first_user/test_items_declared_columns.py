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

import pytest
import yaml
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
    codes = [c.get("code") for c in json.loads(result.stdout)["checks"]]
    assert UNDECLARED in codes


_REMOTE = {
    "s3": {"type": "s3", "format": "csv", "bucket": "b", "key": "k.csv"},
    "gcs": {"type": "gcs", "format": "csv", "bucket": "b", "object": "k.csv"},
}


def _remote_config(tmp_path: Path, kind: str) -> Path:
    return _write(
        tmp_path,
        {"people": _REMOTE[kind]},
        [{"name": "name", "strategy": "redact"}, {"name": "email", "strategy": "redact"}],
    )


def test_g5c_every_registered_cloud_type_has_a_case() -> None:
    from decoy.cli.extras import CLOUD_ENDPOINT_TYPES

    assert set(_REMOTE) == CLOUD_ENDPOINT_TYPES


@pytest.mark.parametrize("kind", sorted(_REMOTE))
def test_g5c_a_remote_source_is_not_opened_and_warns(
    tmp_path: Path, monkeypatch: Any, kind: str
) -> None:
    def _no_network(*_a: Any, **_k: Any) -> None:
        raise AssertionError("validate must not open a remote source")

    for name in ("build_s3_profile_source", "build_gcs_profile_source"):
        monkeypatch.setattr(f"decoy_engine.profile._cloud_readers.{name}", _no_network)
    config = _remote_config(tmp_path, kind)

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


def test_g5_an_undeclared_source_column_exits_1_with_its_own_code(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    src.write_text("name,ssn\nAda,1\n", encoding="utf-8")
    config = _write(tmp_path, {"people": csv_source(src)}, [{"name": "name", "strategy": "redact"}])
    result = _validate(config)
    assert result.exit_code == EXIT_USAGE, result.output
    assert ("preflight", "source_file.undeclared_column") in _codes(result)


DEGENERATE = "statistical_stats_degenerate"
_DEGENERATE_LABELS = {
    "zero labels": [],
    "all-zero counts": [{"value": "CA", "count": 0}, {"value": "NY", "count": 0}],
}


def _degenerate_project(tmp_path: Path, top_values: list[dict[str, Any]]) -> Path:
    """A generate-only config whose `state` snapshot carries the given label counts."""
    src = tmp_path / "source.csv"
    src.write_text("state\n" + "CA\nNY\nTX\nWA\n" * 25, encoding="utf-8")
    snap = tmp_path / "snap.json"
    fit = runner.invoke(app, ["fit", str(src), "--output", str(snap)])
    assert fit.exit_code == EXIT_OK, fit.output
    doc = json.loads(snap.read_text(encoding="utf-8"))
    doc["columns"]["state"]["stats"].update({"top_values": top_values, "other_count": 0})
    snap.write_text(json.dumps(doc), encoding="utf-8")
    cfg = {
        "version": 2,
        "global_settings": {"seed": 3},
        "tables": [
            {
                "name": "synthetic",
                "row_count": 20,
                "generate_columns": [
                    {
                        "name": "state",
                        "type": "statistical",
                        "snapshot_file": "snap.json",
                        "allow_real_categories": True,
                    }
                ],
            }
        ],
        "targets": {"synthetic": {"type": "file", "format": "csv", "path": "synthetic.csv"}},
    }
    path = tmp_path / "gen.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


@pytest.mark.parametrize("shape", sorted(_DEGENERATE_LABELS))
def test_a_statistical_column_with_no_usable_labels_exits_1_at_validate_and_run(
    tmp_path: Path, shape: str
) -> None:
    """Engine #619: validate gives the code run gives, and run writes nothing."""
    config = _degenerate_project(tmp_path, _DEGENERATE_LABELS[shape])

    checked = _validate(config)
    assert checked.exit_code == EXIT_USAGE, checked.output
    assert DEGENERATE in [c for _, c in _codes(checked)]

    ran = runner.invoke(app, ["run", str(config), "--json"])
    assert ran.exit_code == EXIT_USAGE, ran.output
    assert DEGENERATE in [m["code"] for m in json.loads(ran.stdout)["messages"]]
    assert not list(tmp_path.rglob("synthetic.csv")), "run wrote output for a refused config"
    assert not (tmp_path / "out").exists()
