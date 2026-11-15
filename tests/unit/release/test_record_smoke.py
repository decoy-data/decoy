"""`scripts/release/record_smoke.py` (REL-GATE design note 6, AT-S1, AT-S4, AT-S7).

Each test copies the committed smoke log into a throwaway git repo, so the append-only check
reads a real `git show` and the repo's own log is never written.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from packaging_tools import candidate as cand

ROOT = Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    "record_smoke", ROOT / "scripts" / "release" / "record_smoke.py"
)
record_smoke = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(record_smoke)

SUMS = "c" * 64
RECORD = {
    "schema": cand.SCHEMA,
    "cli_version": "1.0.0",
    "cli_sha": "a" * 40,
    "engine_tag": "v0.27.0",
    "engine_commit": "b" * 40,
    "sha256sums_sha256": SUMS,
}


def _summary(**changes) -> dict:
    summary = {
        "schema": cand.SUMMARY_SCHEMA,
        "platform": "macos-arm64",
        "cli_version": "1.0.0",
        "engine_version": "0.27.0",
        "sha256sums_sha256": SUMS,
        "steps": dict.fromkeys(cand.SMOKE_STEPS, "pass"),
        "seconds": 42.5,
    }
    summary.update(changes)
    return summary


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=smoke", "-c", "user.email=smoke@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copyfile(ROOT / "docs" / "release" / "smoke-log.md", repo / "smoke-log.md")
    _git(repo, "init", "-q")
    _git(repo, "add", "smoke-log.md")
    _git(repo, "commit", "-q", "-m", "log")
    (tmp_path / "candidate.json").write_text(json.dumps(RECORD))
    return repo


def _record(repo: Path, summary: dict | str, capsys, *extra: str) -> tuple[int, str]:
    path = repo.parent / "summary.json"
    path.write_text(summary if isinstance(summary, str) else json.dumps(summary))
    rc = record_smoke.main(
        [str(path), "--candidate", str(repo.parent / "candidate.json"), "--run", "mac-mini",
         "--log", str(repo / "smoke-log.md"), "--date", "2026-12-04", *extra]
    )  # fmt: skip
    return rc, capsys.readouterr().err


def _log(repo: Path) -> str:
    return (repo / "smoke-log.md").read_text(encoding="utf-8")


def test_green_matching_summary_appends_one_row(repo, capsys) -> None:
    before = _log(repo)
    rc, _ = _record(repo, _summary(), capsys, "--note", "first candidate")
    row = f"| 2026-12-04 | {'a' * 40} | v0.27.0 | macos-arm64 | {SUMS[:16]} | mac-mini | first candidate |\n"
    assert rc == 0
    assert _log(repo) == before + row


def test_summary_as_the_smoke_prints_it_is_recorded(repo, capsys) -> None:
    # `smoke_install.py` prints with sorted keys, so the steps are not in pipeline order.
    printed = json.dumps(_summary(), sort_keys=True)
    assert list(json.loads(printed)["steps"]) != list(cand.SMOKE_STEPS)
    assert _record(repo, printed, capsys)[0] == 0


def test_summary_not_matching_the_candidate_is_refused(repo, capsys) -> None:
    before = _log(repo)
    for change in (
        {"sha256sums_sha256": "d" * 64},
        {"cli_version": "1.0.1"},
        {"engine_version": "0.26.0"},
    ):
        rc, err = _record(repo, _summary(**change), capsys)
        assert (rc, err.split()[0]) == (1, "smoke_candidate_mismatch"), change
    assert _log(repo) == before


def test_red_or_partial_runs_are_refused(repo, capsys) -> None:
    steps = dict.fromkeys(cand.SMOKE_STEPS, "pass")
    red = {**steps, "native": "fail"}
    left = {**steps, "cleanup": "fail"}
    partial = dict.fromkeys(cand.SMOKE_STEPS[:4], "pass")
    for bad in (red, left, partial):
        rc, err = _record(repo, _summary(steps=bad), capsys)
        assert (rc, err.split()[0]) == (1, "smoke_not_green")


def test_existing_rows_are_never_rewritten(repo, capsys) -> None:
    assert _record(repo, _summary(), capsys)[0] == 0
    _git(repo, "commit", "-q", "-am", "row")
    committed = _log(repo)
    row = committed.splitlines()[-1]

    (repo / "smoke-log.md").write_text(committed.replace(row, row.replace("mac-mini", "elsewhere")))
    rc, err = _record(repo, _summary(), capsys)
    assert (rc, err.split()[0]) == (1, "smoke_log_edited")

    (repo / "smoke-log.md").write_text(committed[: -len(row) - 1])
    assert _record(repo, _summary(), capsys)[1].split()[0] == "smoke_log_edited"

    (repo / "smoke-log.md").write_text(committed + "a note under the table\n")
    assert _record(repo, _summary(), capsys)[1].split()[0] == "smoke_log_edited"

    (repo / "smoke-log.md").write_text(committed)
    assert _record(repo, _summary(), capsys)[0] == 0
    assert _log(repo).startswith(committed)


def test_canonical_table_must_stay_the_last_section(repo, capsys) -> None:
    (repo / "smoke-log.md").write_text(_log(repo) + "\n## Later section\n")
    _git(repo, "commit", "-q", "-am", "heading after the table")
    rc, err = _record(repo, _summary(), capsys)
    assert (rc, err.split()[0]) == (1, "smoke_log_edited")


def test_unknown_schema_major_and_loose_types_refused(repo, capsys) -> None:
    before = _log(repo)
    cases = {
        "smoke_schema_unknown": [
            _summary(schema="decoy-release-smoke/v2"),
            _summary(schema="decoy-release-smoke"),
            _summary(schema=1),
        ],
        "smoke_field_type": [
            _summary(seconds="42.5"),
            _summary(seconds=True),
            _summary(seconds=-1),
            _summary(engine_version=27),
            _summary(platform="/Users/someone"),
            _summary(platform="camkeep-macmini"),
            _summary(platform="windows-x86_64"),
            _summary(steps={**dict.fromkeys(cand.SMOKE_STEPS, "pass"), "native": True}),
            {**_summary(), "host": "box"},
        ],
    }
    for code, summaries in cases.items():
        for summary in summaries:
            rc, err = _record(repo, summary, capsys)
            assert (rc, err.split()[0]) == (1, code), summary
    duplicate = json.dumps(_summary())[:-1] + ', "seconds": 1}'
    assert _record(repo, duplicate, capsys)[1].split()[0] == "smoke_field_type"
    assert _log(repo) == before


def test_run_and_note_cells_are_usage_checked(repo, capsys) -> None:
    assert _record(repo, _summary(), capsys, "--note", "a | b")[0] == 2
    path = repo.parent / "summary.json"
    rc = record_smoke.main(
        [str(path), "--candidate", str(repo.parent / "candidate.json"), "--run", "/home/someone",
         "--log", str(repo / "smoke-log.md")]
    )  # fmt: skip
    assert rc == 2
    assert _record(repo, _summary(), capsys, "--base-ref=--output=x")[0] == 2
    assert _record(repo, _summary(), capsys, "--base-ref=")[0] == 2


@pytest.mark.parametrize(
    "sep", ["\n", "\r", "\r\n", "\u2028", "\u2029", "\x85", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"]
)
def test_note_with_any_line_boundary_is_refused(repo, capsys, sep) -> None:
    before = _log(repo)
    assert _record(repo, _summary(), capsys, "--note", f"first{sep}second")[0] == 2
    assert _record(repo, _summary(), capsys, "--note", f"trailing{sep}")[0] == 2
    assert _log(repo) == before
