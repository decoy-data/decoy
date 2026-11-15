"""`decoy run` stores its evidence manifest as a library record by default (LIB L3a, evidence half).

Plan 4.16: a successful run builds its evidence manifest once and stores it as an `evidence`
record in the pipeline's project library, `--evidence-out` still writes the same manifest to a
file, and `--no-library` or `DECOY_LIBRARY=off` skips the record. Plan 4.17: a failed store
warns and keeps the run's exit code. The run card and `--json` name the record and the root.

Cells (plan L3a acceptance table, evidence rows): L3-records (evidence part), L3-evidence-same,
L3-failed-run (no evidence on a failed run), L3-no-library, L3-readonly, L3-canary, and the
amendment's "exactly one caller".
"""

from __future__ import annotations

import ast
import json
import os
import stat
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml
from decoy_engine import records
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.io import DECOY_DIR
from decoy.cli.library import open_library

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[3]
MARKER = "kind: decoy-project/v1\n"
CANARY = "zq9canary@canary-host.test"


def _pipeline(folder: Path, emails: list[str]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"email": emails}).to_csv(folder / "in.csv", index=False)
    cfg = {
        "version": 2,
        "global_settings": {"seed": 3},
        "sources": {"a": {"type": "file", "format": "csv", "has_header": True, "path": "in.csv"}},
        "tables": [{"name": "a", "columns": [{"name": "email", "strategy": "redact"}]}],
        "targets": {"a": {"type": "file", "format": "csv", "path": "masked.csv"}},
    }
    path = folder / "pipeline.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "decoy.yaml").write_text(MARKER, encoding="utf-8")
    (root / ".git").mkdir()
    monkeypatch.chdir(root)
    monkeypatch.delenv("DECOY_LIBRARY", raising=False)
    monkeypatch.delenv("DECOY_PROJECT", raising=False)
    return root


@pytest.fixture
def pipeline(project: Path) -> Path:
    return _pipeline(project / "pipelines" / "orders", ["a@example.invalid", "b@example.invalid"])


def _run(*args: str) -> Any:
    return runner.invoke(app, ["run", *args])


def _evidence_rows(root: Path) -> list[Any]:
    return [r for r in open_library(root).rows() if r.kind == "evidence"] if root.exists() else []


# -- L3-records, L3-evidence-same -----------------------------------------------------------------


def test_a_successful_run_stores_one_evidence_record(project: Path, pipeline: Path) -> None:
    result = _run(str(pipeline), "--json")
    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    rows = _evidence_rows(project / DECOY_DIR)
    assert len(rows) == 1
    assert doc["library"]["status"] == "stored"
    assert doc["library"]["evidence"] == rows[0].id
    assert doc["library"]["root"] == str(project / DECOY_DIR)
    assert rows[0].pipeline == "pipelines/orders/pipeline.yaml"
    record = open_library(project / DECOY_DIR).get(rows[0].id)
    assert record.raw["payload"]["run_id"] == record.invocation_id  # the run's one invocation id


def test_the_record_payload_equals_the_evidence_out_file(project: Path, pipeline: Path) -> None:
    out = project / "evidence.json"
    result = _run(str(pipeline), "--evidence-out", str(out))
    assert result.exit_code == 0, result.output
    (row,) = _evidence_rows(project / DECOY_DIR)
    stored = open_library(project / DECOY_DIR).get(row.id).raw["payload"]
    written = json.loads(out.read_text(encoding="utf-8"))
    assert records.canonical_bytes(stored) == records.canonical_bytes(written)  # built once


def test_without_a_marker_paths_are_stored_relative_to_the_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "plain"
    cfg = _pipeline(root, ["a@example.invalid"])
    monkeypatch.chdir(root)
    monkeypatch.delenv("DECOY_LIBRARY", raising=False)
    out = root / "ev.json"
    assert _run(str(cfg), "--evidence-out", str(out)).exit_code == 0
    (row,) = _evidence_rows(root / DECOY_DIR)
    stored = open_library(root / DECOY_DIR).get(row.id).raw["payload"]
    written = json.loads(out.read_text(encoding="utf-8"))
    assert Path(written["pipeline_path"]).is_absolute()  # the file keeps what it always had
    assert stored["pipeline_path"] == "pipeline.yaml"  # the record: relative to the project
    assert all(not Path(f["path"]).is_absolute() for f in stored["input_fingerprints"])
    rest = {k: v for k, v in stored.items() if k not in ("pipeline_path", "input_fingerprints",
                                                         "output_fingerprints")}  # fmt: skip
    assert rest == {k: written[k] for k in rest}


# -- L3-failed-run --------------------------------------------------------------------------------


def test_a_failed_run_stores_no_evidence(project: Path, pipeline: Path) -> None:
    (pipeline.parent / "in.csv").unlink()  # the source is gone: a runtime failure
    result = _run(str(pipeline))
    assert result.exit_code != 0
    assert _evidence_rows(project / DECOY_DIR) == []


# -- L3-no-library --------------------------------------------------------------------------------


def test_no_library_flag_writes_no_record(project: Path, pipeline: Path) -> None:
    result = _run(str(pipeline), "--no-library", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["library"]["status"] == "off"
    assert not (project / DECOY_DIR / "library").exists()


def test_decoy_library_off_writes_no_record(
    project: Path, pipeline: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DECOY_LIBRARY", "off")
    result = _run(str(pipeline), "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["library"]["status"] == "off"
    assert not (project / DECOY_DIR / "library").exists()


# -- L3-readonly ----------------------------------------------------------------------------------


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="a read-only folder for root")
def test_a_read_only_library_warns_and_keeps_the_exit_code(project: Path, pipeline: Path) -> None:
    root = project / DECOY_DIR
    root.mkdir()
    root.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        result = _run(str(pipeline), "--json")
    finally:
        root.chmod(stat.S_IRWXU)
    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    assert doc["library"]["status"] == "failed" and doc["library"]["code"]


def test_a_failed_store_warns_and_keeps_the_exit_code(
    project: Path, pipeline: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same rule where a read-only folder cannot be made (root, Windows): the put fails."""
    from decoy.cli.library import LibraryError, _store

    def full(*_a: object, **_k: object) -> object:
        raise LibraryError("library_write_failed", "OSError")

    monkeypatch.setattr(_store.Library, "put", full)
    result = _run(str(pipeline), "--json")
    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    assert doc["library"] == {
        "status": "failed",
        "code": "library_write_failed",
        "root": str(project / DECOY_DIR),
    }
    human = _run(str(pipeline))
    assert human.exit_code == 0
    assert human.stderr.count("library_write_failed") == 1


# -- the run card ---------------------------------------------------------------------------------


def test_the_run_card_names_the_record(project: Path, pipeline: Path) -> None:
    result = _run(str(pipeline))
    assert result.exit_code == 0, result.output
    (row,) = _evidence_rows(project / DECOY_DIR)
    assert row.id[:19] in result.output


# -- L3-canary ------------------------------------------------------------------------------------


def test_no_cell_value_reaches_the_library(project: Path) -> None:
    cfg = _pipeline(project / "pipelines" / "canary", [CANARY, CANARY.upper()])
    assert _run(str(cfg)).exit_code == 0
    assert _evidence_rows(project / DECOY_DIR)  # non-vacuous: a record was written
    needle = CANARY.encode("utf-8")
    leaked = [
        p.relative_to(project).as_posix()
        for p in (project / DECOY_DIR).rglob("*")
        if p.is_file() and (needle in p.read_bytes() or needle.upper() in p.read_bytes())
    ]
    assert leaked == []


# -- one caller -----------------------------------------------------------------------------------


def test_exactly_one_caller_stores_evidence() -> None:
    callers = []
    for path in (ROOT / "src" / "decoy").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", None))
                if name == "store_evidence":
                    callers.append(path.relative_to(ROOT).as_posix())
    assert callers == ["src/decoy/cli/run/_evidence.py"]
