"""`decoy run` stores its run-result record in the library (LIB L3a, run-result half).

The record holds the document `cli/run/_result.py` built, once, so its payload is the `result`
member of `--json` (L3-payload-from-finish). On a successful run it links one way to the
evidence record stored a moment earlier (L3-records); a run that fails still stores the document,
with no evidence (L3-failed-run). The log link (L5b) and `report ... <id>` are not in this part.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from decoy.cli.exit_codes import EXIT_OK
from decoy.cli.io import DECOY_DIR
from decoy.cli.library import open_library
from tests.e2e.library.test_run_evidence_records import (
    PIPELINE,
    _run,
    project,  # noqa: F401  (fixture)
)

CANONICAL = dict(sort_keys=True, separators=(",", ":"))


def _rows(root: Path, kind: str) -> list:
    if not (root / DECOY_DIR / "library").exists():
        return []
    return open_library(root / DECOY_DIR).rows(kind=kind)


def _stored(root: Path, row_id: str) -> dict:
    return open_library(root / DECOY_DIR).get(row_id).raw


def test_a_run_stores_a_result_record_that_links_to_its_evidence(project: Path) -> None:  # noqa: F811
    result = _run("--json")
    assert result.exit_code == EXIT_OK, result.output
    out = json.loads(result.stdout)
    (evidence,) = _rows(project, "evidence")
    (row,) = _rows(project, "run-result")
    assert out["library"] == {
        "status": "stored",
        "root": str((project / DECOY_DIR).resolve()),
        "evidence": evidence.id,
        "result": row.id,
    }
    raw = _stored(project, row.id)
    assert raw["invocation_id"] == _stored(project, evidence.id)["invocation_id"]
    assert raw["links"] == [{"rel": "evidence", "id": evidence.id}]
    assert _stored(project, evidence.id)["links"] == []  # one way: evidence links to nothing
    assert row.pipeline == PIPELINE and list(row.tables) == ["customers"]
    assert row.status == "success" and row.exit_code == 0


def test_the_index_finds_the_result_from_the_evidence(project: Path) -> None:  # noqa: F811
    """The reverse direction is a query over the index's links (plan 4.3), never a stored link."""
    assert _run().exit_code == EXIT_OK
    (evidence,) = _rows(project, "evidence")
    rows = open_library(project / DECOY_DIR).rows()
    pointing = [r.id for r in rows if ("evidence", evidence.id) in r.links]
    assert pointing == [_rows(project, "run-result")[0].id]


def test_the_stored_payload_is_the_result_member_of_json(project: Path) -> None:  # noqa: F811
    """L3-payload-from-finish, on a success."""
    result = _run("--json")
    out = json.loads(result.stdout)
    (row,) = _rows(project, "run-result")
    stored = _stored(project, row.id)["payload"]
    assert json.dumps(stored, **CANONICAL) == json.dumps(out["result"], **CANONICAL)


def test_a_failed_run_stores_a_failed_result_and_no_evidence(project: Path) -> None:  # noqa: F811
    """L3-failed-run, and L3-payload-from-finish on a runtime failure."""
    (project / "pipelines" / "input.csv").unlink()
    result = _run("--json")
    assert result.exit_code != EXIT_OK
    assert _rows(project, "evidence") == []
    (row,) = _rows(project, "run-result")
    payload = _stored(project, row.id)["payload"]
    assert payload["status"] == "failed" and payload["exit_code"] == result.exit_code
    assert _stored(project, row.id)["links"] == []
    shown = json.loads(result.stdout)
    document = shown.get("result") or shown["context"]["result"]
    assert json.dumps(payload, **CANONICAL) == json.dumps(document, **CANONICAL)


@pytest.mark.parametrize("how", ["flag", "env"])
def test_no_library_stores_no_result(project: Path, how: str) -> None:  # noqa: F811
    args = ("--no-library",) if how == "flag" else ()
    env = {"DECOY_LIBRARY": "off"} if how == "env" else None
    assert _run(*args, env=env).exit_code == EXIT_OK
    assert not (project / DECOY_DIR / "library").exists()


def test_an_unwritable_library_warns_once_for_both_records(project: Path) -> None:  # noqa: F811
    (project / DECOY_DIR).write_text("not a folder", encoding="utf-8")
    result = _run("--json")
    assert result.exit_code == EXIT_OK, result.output
    assert json.loads(result.stdout)["library"]["status"] == "failed"
    assert len([line for line in result.stderr.splitlines() if "warning" in line]) == 1


def test_the_result_file_and_the_record_hold_the_same_document(project: Path) -> None:  # noqa: F811
    assert _run("--result", "r.json").exit_code == EXIT_OK
    (row,) = _rows(project, "run-result")
    written = json.loads((project / "r.json").read_text(encoding="utf-8"))
    assert _stored(project, row.id)["payload"] == written
