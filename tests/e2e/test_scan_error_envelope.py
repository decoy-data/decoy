"""CL4 (24zf), AT-10 for `scan`: each error site writes the standard `decoy-error-v1` order,
`hint` as plain text, and no `code` (plan 7.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_USAGE
from tests.e2e.first_user.test_items_error_envelope import SCHEMA

runner = CliRunner()


@pytest.fixture
def scans(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "raw.csv").write_text("email,age\na@x.com,4\nb@x.com,5\n", encoding="utf-8")
    (tmp_path / "bad.json").write_text("{nope", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    made = runner.invoke(app, ["scan", "raw.csv", "--has-header", "--output", "scan.json"])
    assert made.exit_code == 0, made.output
    return tmp_path


def _doc(argv: list[str]) -> dict:
    jsonschema = pytest.importorskip("jsonschema")
    result = runner.invoke(app, [*argv, "--json"])
    assert result.exit_code == EXIT_USAGE, result.output
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1, result.stdout
    doc = json.loads(lines[0])
    jsonschema.validate(doc, SCHEMA)
    return doc


def test_a_raw_data_file_gives_the_scan_it_first_hint(scans: Path) -> None:
    doc = _doc(["scan", "show", "raw.csv", "email"])

    assert list(doc) == ["command", "status", "error", "hint", "scan"]
    assert doc["hint"] == "scan it first: decoy scan raw.csv --has-header --output scan.json"
    assert doc["command"] == "scan show"


def test_a_bad_json_scan_gives_the_pass_the_file_hint(scans: Path) -> None:
    doc = _doc(["scan", "diff", "bad.json", "scan.json"])

    assert list(doc) == ["command", "status", "error", "hint", "scan"]
    assert doc["hint"] == "pass the JSON file produced by decoy scan --output scan.json"


def test_a_missing_field_with_a_close_name_suggests_it(scans: Path) -> None:
    doc = _doc(["scan", "show", "scan.json", "emial"])

    assert list(doc) == ["command", "status", "error", "hint", "scan", "field", "suggestion"]
    assert doc["suggestion"] == "email"
    assert doc["hint"] == "did you mean email"


def test_a_missing_field_with_no_close_name_lists_the_fields(scans: Path) -> None:
    doc = _doc(["scan", "show", "scan.json", "zzzzzz"])

    assert list(doc) == ["command", "status", "error", "hint", "scan", "field", "suggestion"]
    assert doc["suggestion"] is None
    assert doc["hint"] == "list all fields with decoy scan fields scan.json"


def test_two_stdin_scans_have_no_scan_member(scans: Path) -> None:
    doc = _doc(["scan", "diff", "-", "-"])

    assert list(doc) == ["command", "status", "error", "hint"]
    assert doc["hint"] == "pipe one scan, pass the other as a path."


def test_no_scan_error_has_a_code(scans: Path) -> None:
    for argv in (["scan", "show", "raw.csv", "x"], ["scan", "show", "scan.json", "zzz"]):
        assert "code" not in _doc(argv)
