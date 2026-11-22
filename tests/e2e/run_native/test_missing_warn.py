"""NATIVE-MISSING-WARN C1: `decoy run` prints the engine's native fallback notice.

Each test wraps the real `run_pipeline` and sets `native_fallback_code` itself, so the
companion on the test host never decides the result.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import decoy_engine
import pandas as pd
import pytest
import yaml
from decoy_engine import reasons
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.keyed_secret import TEST_MASK_SECRET_REF

pytestmark = pytest.mark.usefixtures("mask_secret")

runner = CliRunner()

MISSING = str(reasons.warning.NATIVE_COMPANION_MISSING)
SUMMARY = "No compiled kernel ran"
LINE = (
    "warning: No compiled kernel ran: a native kernel this run needs is not available, "
    "so masking ran in Python. Compiled kernels come with the signed bundle; "
    "run `decoy explain native` to see what is missing."
)
TABLE = "tbl_sentinel"
COLUMN = "col_sentinel"


def _set_code(monkeypatch: pytest.MonkeyPatch, code: str | int | None) -> None:
    real = decoy_engine.run_pipeline

    def _wrapped(*args, **kwargs):
        return dataclasses.replace(real(*args, **kwargs), native_fallback_code=code)

    monkeypatch.setattr("decoy_engine.run_pipeline", _wrapped)


def _config(tmp_path: Path, *, generate: bool = False) -> Path:
    if generate:
        table: dict[str, Any] = {
            "name": TABLE,
            "row_count": 20,
            "generate_columns": [{"name": COLUMN, "type": "sequence", "start": 1, "step": 1}],
        }
        sources: dict[str, Any] = {}
    else:
        src = tmp_path / "src_sentinel.parquet"
        pd.DataFrame(
            {"id": [f"C{i}" for i in range(10)], COLUMN: [f"u{i}@example.com" for i in range(10)]}
        ).to_parquet(src, index=False)
        sources = {TABLE: {"type": "file", "format": "parquet", "path": str(src)}}
        table = {
            "name": TABLE,
            "columns": [
                {"name": "id", "strategy": "passthrough"},
                {"name": COLUMN, "strategy": "hash", "namespace": "ns"},
            ],
        }
    config = {
        "version": 2,
        "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
        "sources": sources,
        "tables": [table],
        "targets": {TABLE: {"type": "file", "format": "csv", "path": str(tmp_path / "out.csv")}},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    return path


def _lines(stderr: str) -> list[str]:
    return [ln for ln in stderr.splitlines() if SUMMARY in ln]


def _project(doc: object) -> object:
    """Drop the fields that differ between two runs: timings, ids and run paths."""
    volatile = {
        "elapsed_s",
        "invocation_id",
        "started_at",
        "finished_at",
        "output_dir",
        "output",
        "outputs",
        "path",
        "paths",
        "run_dir",
        "run_id",
    }
    if isinstance(doc, dict):
        return {k: _project(v) for k, v in doc.items() if k not in volatile}
    if isinstance(doc, list):
        return [_project(v) for v in doc]
    return doc


def test_notice_is_one_line_and_stdout_json_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    cfg = _config(tmp_path)
    _set_code(monkeypatch, MISSING)
    plain = runner.invoke(app, ["run", str(cfg)])
    assert plain.exit_code == 0, plain.output
    assert _lines(plain.stderr) == [LINE]

    with_code = runner.invoke(app, ["run", str(cfg), "--json", "--no-library"])
    assert with_code.exit_code == 0, with_code.output
    assert _lines(with_code.stderr) == [LINE]
    assert SUMMARY not in with_code.stdout

    _set_code(monkeypatch, None)
    without = runner.invoke(app, ["run", str(cfg), "--json", "--no-library"])
    assert without.exit_code == 0, without.output
    assert _lines(without.stderr) == []
    assert _project(json.loads(with_code.stdout)) == _project(json.loads(without.stdout))


def test_absent_companion_prints_no_pre_run_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(__import__("sys").modules, "decoy_engine_native", None)
    _set_code(monkeypatch, None)
    result = runner.invoke(app, ["run", str(_config(tmp_path))])
    assert result.exit_code == 0, result.output
    assert not [ln for ln in result.stderr.splitlines() if ln.startswith("native:")]


def test_notice_holds_no_config_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = _config(tmp_path)
    _set_code(monkeypatch, MISSING)
    result = runner.invoke(app, ["run", str(cfg)])
    notice = "\n".join(_lines(result.stderr))
    assert notice
    for text in (TABLE, COLUMN, "src_sentinel", str(tmp_path)):
        assert text not in notice


@pytest.mark.parametrize("flags", [["--no-native"], ["--chunked"], ["--quiet"]])
def test_no_notice_for_other_intents_modes_and_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flags: list[str]
):
    cfg = _config(tmp_path)
    _set_code(monkeypatch, None)
    baseline = runner.invoke(app, ["run", str(cfg), *flags])
    _set_code(monkeypatch, MISSING)
    result = runner.invoke(app, ["run", str(cfg), *flags])
    assert SUMMARY not in result.stderr
    assert SUMMARY not in result.stdout
    assert result.exit_code == baseline.exit_code


def test_rows_preview_prints_no_notice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _set_code(monkeypatch, MISSING)
    result = runner.invoke(app, ["run", str(_config(tmp_path, generate=True)), "--rows", "5"])
    assert SUMMARY not in result.stderr
    assert SUMMARY not in result.stdout


@pytest.mark.parametrize("code", ["not_a_registered_code", 3])
def test_unregistered_or_non_string_code_prints_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: str | int
):
    _set_code(monkeypatch, code)
    result = runner.invoke(app, ["run", str(_config(tmp_path))])
    assert result.exit_code == 0, result.output
    assert SUMMARY not in result.stderr
