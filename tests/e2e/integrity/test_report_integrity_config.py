"""AT-C2a6: `decoy report integrity --config` stamps `config_sha256` and runs the config's
post-scan detectors.

The hash is of the YAML bytes the command read (a CRLF file included), and the report's
`detectors` names each model the config asked for. Without `--config` the report keeps today's
regex-only shape with no hash. A model the config asks for that cannot run here exits 1 with
its reason code before either CSV is read.

Mutation: M-C2a6 (ignore the config's detectors) turns the classifier test red.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.e2e.integrity._fixtures import sha256, write_pipeline

runner = CliRunner()


def _integrity(*args: object):
    return runner.invoke(app, ["report", "integrity", *(str(a) for a in args)])


def _masked(tmp_path: Path, cfg: Path) -> Path:
    result = runner.invoke(app, ["run", str(cfg)])
    assert result.exit_code == 0, result.output
    return tmp_path / "masked" / "customers.csv"


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_config_stamps_the_hash_and_runs_its_detectors(tmp_path: Path, newline: str) -> None:
    post = {"integrity": True, "detectors": ["regex", "classifier"]}
    cfg = write_pipeline(tmp_path, post=post, newline=newline)
    masked = _masked(tmp_path, cfg)
    source = tmp_path / "customers.csv"

    result = _integrity(masked, "--source", source, "--config", cfg, "--json")

    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)["report"]
    assert report["config_sha256"] == sha256(cfg.read_bytes())
    sources = [d["source"] for d in report["detectors"]]
    assert sources == ["regex", "classifier"]
    model = report["detectors"][1]["model"]
    assert model["id"] == "lgbm-v1" and model["version"]


def test_without_config_the_report_has_no_hash_and_regex_only(tmp_path: Path) -> None:
    cfg = write_pipeline(tmp_path)
    masked = _masked(tmp_path, cfg)

    result = _integrity(masked, "--source", tmp_path / "customers.csv", "--json")

    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)["report"]
    assert report["config_sha256"] is None
    assert [d["source"] for d in report["detectors"]] == ["regex"]


def test_an_unavailable_config_model_exits_1_before_the_csvs_are_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    post = {"integrity": True, "detectors": ["regex", "classifier"]}
    cfg = write_pipeline(tmp_path, post=post)
    masked = _masked(tmp_path, cfg)
    monkeypatch.setenv("DECOY_ML_DISABLED", "1")
    with mock.patch("decoy.cli.report._integrity.read_report_source") as reads:
        result = _integrity(
            masked, "--source", tmp_path / "customers.csv", "--config", cfg, "--json"
        )

    assert result.exit_code == 1, result.output
    reads.assert_not_called()
    doc = json.loads(result.stdout)
    assert doc["code"] == "provider.classifier_unavailable"
    assert "DECOY_ML_DISABLED" in doc["hint"]
