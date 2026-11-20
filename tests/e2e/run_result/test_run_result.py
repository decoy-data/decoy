"""The `result` member of `decoy run --json`: the `decoy-run-result/v1` document of one run.

Each case reads the document from the real command, never from a helper, and checks it against
the process exit code and the legacy envelope it rides in.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pandas as pd
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.evidence import hash_file
from tests.csv_sources import csv_source

runner = CliRunner()
MARKER = "zz_marker_exc"
CELL_A, CELL_B = "zz_marker_a", "zz_marker_b"
BASE_KEYS = {
    "command",
    "status",
    "config",
    "mode",
    "elapsed_s",
    "tables",
    "warnings",
    "resources",
    "pipeline",
    "project",
}


def _write(tmp_path: Path, tables: int = 1, generate: bool = False, crlf: bool = False) -> Path:
    cfg: dict = {
        "version": 2,
        "global_settings": {"seed": 7},
        "sources": {},
        "tables": [],
        "targets": {},
    }
    for i in range(tables):
        name = f"t{i + 1}"
        src = tmp_path / f"in{i + 1}.csv"
        pd.DataFrame({"code": [CELL_A, CELL_B]}).to_csv(src, index=False)
        cfg["sources"][name] = csv_source(src)
        cfg["tables"].append({"name": name, "columns": [{"name": "code", "strategy": "redact"}]})
        cfg["targets"][name] = {
            "type": "file",
            "format": "csv",
            "path": str(tmp_path / f"out{i + 1}.csv"),
        }
    if generate:
        cfg["tables"].append(
            {
                "name": "g",
                "row_count": 3,
                "generate_columns": [{"name": "id", "type": "sequence", "start": 1, "step": 1}],
            }
        )
        cfg["targets"]["g"] = {
            "type": "file",
            "format": "csv",
            "path": str(tmp_path / "gen.csv"),
        }
    path = tmp_path / "pipeline.yaml"
    text = yaml.dump(cfg)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    return path


def _run(args: list[str], patch: str | None = None, exc: BaseException | None = None):
    if patch is None:
        return runner.invoke(app, args)
    with mock.patch(patch, side_effect=exc):
        return runner.invoke(app, args)


def _read(result) -> dict:
    return json.loads(result.output)


def _model(payload: dict):
    from decoy_engine.run_result import RunResultRead

    return RunResultRead.model_validate(payload)


def test_success_document(tmp_path: Path) -> None:
    cfg = _write(tmp_path, tables=1, generate=True, crlf=True)
    result = _run(["run", str(cfg), "--json"])
    assert result.exit_code == 0, result.output
    payload = _read(result)
    doc = payload["result"]
    _model(doc)
    assert doc["exit_code"] == 0 == result.exit_code
    assert doc["status"] == "succeeded"
    assert doc["pipeline_kind"] == "mixed"
    assert payload["mode"] != "mixed"
    assert doc["config"]["file_sha256"] == hash_file(cfg)
    assert [t["name"] for t in doc["tables"]] == ["t1", "g"]
    assert all(t["outcome"] == "succeeded" for t in doc["tables"])
    assert doc["delivery"] == {"mode": "in_place", "outcome": "delivered", "vault": "not_used"}
    assert payload["result_status"] == {"document": "built", "file": "not_requested", "code": None}
    assert set(payload) >= BASE_KEYS | {"result", "result_status"}
    assert set(payload) - {"result", "result_status"} <= BASE_KEYS | {
        "outputs",
        "output_dir",
        "native_route",
    }


def _failing(tmp_path: Path, exc: BaseException):
    cfg = _write(tmp_path)
    return _run(["run", str(cfg), "--json"], "decoy_engine.run_pipeline", exc)


def test_failure_document(tmp_path: Path) -> None:
    from decoy_engine.execution import ExecutionError

    result = _failing(tmp_path, RuntimeError(MARKER))
    payload = _read(result)
    doc = payload["result"]
    _model(doc)
    assert result.exit_code == 3 == doc["exit_code"]
    assert doc["status"] == "failed"
    assert doc["failure"]["category"] == "runtime"
    assert doc["failure"]["reason"] == payload["reason"]

    result = _failing(
        tmp_path, ExecutionError(code="out_of_core_insufficient_memory", message=MARKER)
    )
    doc = _read(result)["result"]
    assert (result.exit_code, doc["exit_code"], doc["failure"]["category"]) == (5, 5, "capacity")

    from decoy.cli.gate import PreRunCheckError

    gate = PreRunCheckError(
        "refused", exit_code=5, error_kind="capacity", code=None, extra=None, messages=[]
    )
    result = _failing(tmp_path, gate)
    payload = _read(result)
    doc = payload["result"]
    assert (result.exit_code, doc["exit_code"], doc["failure"]["category"]) == (5, 5, "capacity")
    assert doc["failure"]["reason"] is None


def test_value_free(tmp_path: Path) -> None:
    from decoy_engine import ConfigError
    from decoy_engine.execution import ExecutionError

    cases = [
        _run(["run", str(_write(tmp_path)), "--json"]),
        _failing(tmp_path, RuntimeError(f"{MARKER} {CELL_A}")),
        _failing(tmp_path, ConfigError(f"{MARKER} {CELL_B}")),
        _failing(tmp_path, ExecutionError(code="out_of_core_insufficient_memory", message=MARKER)),
    ]
    for result in cases:
        payload = _read(result)
        text = json.dumps({"r": payload["result"], "s": payload["result_status"]})
        for forbidden in (MARKER, CELL_A, CELL_B, str(tmp_path)):
            assert forbidden not in text


def test_build_failure_keeps_exit(tmp_path: Path) -> None:
    broken = "decoy_engine.run_result.build_run_result"
    ok = _run(["run", str(_write(tmp_path)), "--json"], broken, RuntimeError(MARKER))
    assert ok.exit_code == 0
    payload = json.loads(ok.stdout)
    assert "result" not in payload
    assert payload["result_status"]["document"] == "failed"
    assert payload["result_status"]["code"] == "run_result_build_failed"
    assert MARKER not in ok.output

    cfg = _write(tmp_path)
    with (
        mock.patch(broken, side_effect=RuntimeError(MARKER)),
        mock.patch("decoy_engine.run_pipeline", side_effect=RuntimeError("boom")),
    ):
        bad = runner.invoke(app, ["run", str(cfg), "--json"])
    assert bad.exit_code == 3
    payload = json.loads(bad.stdout)
    assert "result" not in payload
    assert payload["result_status"]["code"] == "run_result_build_failed"
    assert MARKER not in bad.output


def test_in_place_delivery(tmp_path: Path) -> None:
    cfg = _write(tmp_path, tables=2)
    result = _run(["run", str(cfg), "--json"])
    doc = _read(result)["result"]
    assert doc["delivery"]["mode"] == "in_place"
    assert doc["delivery"]["outcome"] == "delivered"
    assert [t["delivery"]["state"] for t in doc["tables"]] == ["delivered", "delivered"]

    from decoy.cli.io import _targets

    real, calls = _targets.write_table, []

    def second_fails(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise OSError(MARKER)
        return real(*args, **kwargs)

    with mock.patch.object(_targets, "write_table", second_fails):
        result = _run(["run", str(cfg), "--json"])
    assert result.exit_code == 3
    doc = _read(result)["result"]
    assert doc["delivery"]["outcome"] == "partial"
    assert [t["delivery"]["state"] for t in doc["tables"]] == ["delivered", "none"]


def test_preview_document(tmp_path: Path) -> None:
    cfg = tmp_path / "gen.yaml"
    cfg.write_text(
        yaml.dump(
            {
                "version": 2,
                "global_settings": {"seed": 1},
                "sources": {},
                "tables": [
                    {
                        "name": "g",
                        "row_count": 50,
                        "generate_columns": [{"name": "id", "type": "sequence", "start": 1}],
                    }
                ],
                "targets": {
                    "g": {"type": "file", "format": "csv", "path": str(tmp_path / "g.csv")}
                },
            }
        ),
        encoding="utf-8",
    )
    result = _run(["run", str(cfg), "--rows", "5", "--json"])
    assert result.exit_code == 0, result.output
    payload = _read(result)
    assert payload["preview"] is True
    assert payload["result"]["delivery"]["outcome"] == "not_applicable"
    assert not (tmp_path / "g.csv").exists()


def test_collector_registered(tmp_path: Path) -> None:
    from decoy_engine import PhaseEvent

    cfg = _write(tmp_path, tables=3)

    def fake(*_args, progress=None, **_kwargs):
        progress.on_event(PhaseEvent("mask", "start", "t1"))
        progress.on_event(PhaseEvent("mask", "finish", "t1", rows_out=2, elapsed_s=0.1))
        progress.on_event(PhaseEvent("mask", "start", "t2"))
        progress.on_event(PhaseEvent("mask", "error", "t2", error_class="RuntimeError"))
        raise RuntimeError(MARKER)

    with mock.patch("decoy_engine.run_pipeline", fake):
        result = runner.invoke(app, ["run", str(cfg), "--json"])
    assert result.exit_code == 3
    doc = _read(result)["result"]
    assert [t["outcome"] for t in doc["tables"]] == ["succeeded", "failed", "not_run"]
    assert doc["tables"][0]["rows_out"] == 2


def test_one_blocking_decision(tmp_path: Path) -> None:
    cfg = _write(tmp_path)
    metrics = {"failed_checks": [{"code": "zz_check"}], "quality_summary": {}}

    from decoy.cli.io import RunLayout

    def run(extra: list[str]):
        from decoy_engine import run_pipeline as real

        def wrapped(*a, **kw):
            res = real(*a, **kw)
            res.quality_metrics.update(metrics)
            return res

        with mock.patch("decoy_engine.run_pipeline", wrapped):
            return runner.invoke(app, ["run", str(cfg), "--json", "--post-validate", *extra])

    with mock.patch.object(RunLayout, "commit_latest", autospec=True, return_value=()) as moved:
        enforced = run(["--post-validate-enforce"])
        assert enforced.exit_code == 4
        doc = _read(enforced)["result"]
        assert (doc["status"], doc["exit_code"]) == ("findings", 4)
        assert moved.call_count == 0

        plain = run([])
        assert plain.exit_code == 0
        assert _read(plain)["result"]["status"] == "succeeded"
        assert moved.call_count == 1
