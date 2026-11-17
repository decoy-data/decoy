"""AT-C2a5, AT-C2a7 and AT-C2a8: the post-scan models on the `decoy run` routes.

- `--chunked` runs no post-scan, so a model post-scan config is refused with the engine's
  `route.post_scan_models_unsupported` before any source is read (AT-C2a5); regex-only
  integrity keeps today's chunked refusal.
- `load_detectors` runs before the first source read, so a model that cannot load refuses with
  exit 1, its reason code and the install hint (AT-C2a7); `-v` sends the engine's
  `decoy_engine.detectors` records to stderr, and without `-v` they stay off it.
- A run with every post-scan detector completes with sockets blocked (AT-C2a8).

Mutations: M-C2a5 (drop the route refusal), M-C2a7 (call `load_detectors` after the sources are
loaded), M-C2a7b (drop the `-v` stderr handler), M-C2a8 (call `spacy.cli.download` on the run
path).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.e2e.integrity._fixtures import default_report, write_pipeline
from tests.e2e.models._venvs import child_env, run_cli

runner = CliRunner()
CLASSIFIER = {"integrity": True, "detectors": ["regex", "classifier"]}


def _route_summary() -> str:
    from decoy_engine import reasons

    return reasons.get("route", "post_scan_models_unsupported").summary


# --- AT-C2a5: --chunked ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "post",
    [
        {"integrity": True, "detectors": ["regex", "ner"]},
        CLASSIFIER,
        {"integrity": True, "detectors": ["regex", "ner"], "ner_findings": "fail"},
    ],
    ids=["ner", "classifier", "ner_fail"],
)
def test_chunked_refuses_a_model_post_scan_before_any_read(tmp_path: Path, post: dict) -> None:
    cfg = write_pipeline(tmp_path, post=post)
    with (
        mock.patch("decoy.cli.run._execute.source_schema_and_chunks") as chunks,
        mock.patch("decoy.cli.run._prepare._load_sources_from_config") as loads,
    ):
        result = runner.invoke(app, ["run", str(cfg), "--chunked", "--json"])

    assert result.exit_code == 1, result.output
    doc = json.loads(result.stdout)
    assert (doc["reason"]["namespace"], doc["reason"]["code"]) == (
        "route",
        "post_scan_models_unsupported",
    )
    assert doc["error"] == _route_summary()
    chunks.assert_not_called()
    loads.assert_not_called()
    assert not (tmp_path / "masked" / "customers.csv").exists()


def test_chunked_regex_only_integrity_keeps_todays_refusal(tmp_path: Path) -> None:
    cfg = write_pipeline(tmp_path, post={"integrity": True})

    result = runner.invoke(app, ["run", str(cfg), "--chunked", "--json"])

    assert result.exit_code == 1, result.output
    doc = json.loads(result.stdout)
    assert "--chunked does not support post-scan integrity" in doc["error"]
    assert "reason" not in doc


# --- AT-C2a7: the load_detectors preflight and -v ----------------------------------------------


def test_a_model_that_cannot_load_refuses_before_any_source_is_read(tmp_path: Path) -> None:
    from decoy_engine import ModelStatus, ModelUnavailableError

    from decoy.cli.models import hint

    cfg = write_pipeline(tmp_path, post=CLASSIFIER)
    refused = ModelUnavailableError("classifier_unavailable", cause="pack")
    with (
        mock.patch("decoy_engine.load_detectors", side_effect=refused),
        mock.patch("decoy.cli.run._prepare._load_sources_from_config") as loads,
    ):
        result = runner.invoke(app, ["run", str(cfg), "--json"])

    assert result.exit_code == 1, result.output
    loads.assert_not_called()
    doc = json.loads(result.stdout)
    assert [m["code"] for m in doc["messages"]] == ["classifier_unavailable"]
    expected = hint(ModelStatus("classifier", "lgbm-v1", False, None, None, refused.reason, "pack"))
    assert expected is not None
    assert expected in doc["messages"][0]["message"]
    assert not default_report(tmp_path).exists()


def test_the_gate_refusal_still_comes_first_for_a_disabled_classifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DECOY_ML_DISABLED", "1")
    cfg = write_pipeline(tmp_path, post=CLASSIFIER)
    with mock.patch("decoy.cli.run._prepare._load_sources_from_config") as loads:
        result = runner.invoke(app, ["run", str(cfg)])

    assert result.exit_code == 1, result.output
    loads.assert_not_called()
    assert "classifier_unavailable" in " ".join(result.output.split())


@pytest.mark.parametrize("verbose", [True, False], ids=["verbose", "default"])
def test_verbose_sends_the_detector_record_to_stderr(tmp_path: Path, verbose: bool) -> None:
    cfg = write_pipeline(tmp_path, post=CLASSIFIER)

    result = runner.invoke(app, ["run", str(cfg), *(["-v"] if verbose else [])])

    assert result.exit_code == 0, result.output
    line = "post_scan.detectors sources=regex,classifier classifier=lgbm-v1@0.1.0"
    assert (line in result.stderr) is verbose
    assert line not in result.stdout


# --- AT-C2a8: every detector with sockets blocked ----------------------------------------------

_NO_NETWORK = """\
import socket
from pathlib import Path
_seen = Path({seen!r})
def _refuse(*args, **kwargs):
    _seen.write_text("attempted")
    raise OSError("network blocked by the test")
socket.socket.connect = _refuse
socket.socket.connect_ex = _refuse
socket.create_connection = _refuse
socket.getaddrinfo = _refuse
"""


@pytest.mark.timeout(1200)
def test_real_model_run_with_every_detector_needs_no_network(
    tmp_path: Path, ner_python: Path
) -> None:
    post = {"integrity": True, "detectors": ["regex", "classifier", "ner"]}
    cfg = write_pipeline(tmp_path, post=post, notes=True)
    seen = tmp_path / "network-attempt"

    proc = run_cli(
        ner_python,
        ["run", str(cfg), "--json"],
        tmp_path,
        child_env(),
        prelude=_NO_NETWORK.format(seen=str(seen)),
    )

    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    assert not seen.exists()
    doc = json.loads(proc.stdout)
    assert [d["source"] for d in doc["post_scan"]["detectors"]] == ["regex", "classifier", "ner"]
    assert doc["post_scan"]["counts"]["warning"] >= 1
    assert default_report(tmp_path).is_file()


def test_a_model_that_cannot_load_refuses_before_a_duckdb_relation_is_read(tmp_path: Path) -> None:
    import duckdb
    from decoy_engine import ModelUnavailableError

    cfg = write_pipeline(tmp_path, post=CLASSIFIER)
    db = tmp_path / "people.duckdb"
    con = duckdb.connect(str(db))
    try:
        con.execute("CREATE TABLE customers AS SELECT 1 AS id, 'a@example.invalid' AS email")
    finally:
        con.close()
    refused = ModelUnavailableError("classifier_unavailable", cause="pack")
    with (
        mock.patch("decoy_engine.load_detectors", side_effect=refused),
        mock.patch("decoy.cli.run._prepare.acquire_relation") as acquire,
    ):
        result = runner.invoke(
            app, ["run", str(cfg), "--duckdb-source", f"customers={db}", "--json"]
        )

    assert result.exit_code == 1, result.output
    acquire.assert_not_called()
    assert [m["code"] for m in json.loads(result.stdout)["messages"]] == ["classifier_unavailable"]
