"""CL4 (24zf), AT-8 and AT-13: a pre-run refusal gives its context to the one error emitter
without its code, and `run` and `tokenize` read it through the same accessor."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_CAPACITY, EXIT_USAGE
from decoy.cli.gate import GateFinding, PreRunCheckError
from tests.e2e.first_user.test_items_error_envelope import SCHEMA
from tests.e2e.test_run_error_arms import _config, _doc

runner = CliRunner()
MESSAGES = [
    {"layer": "config", "severity": "error", "code": "a.one", "message": "m1", "location": None},
    {"layer": "config", "severity": "error", "code": "a.two", "message": "m2", "location": None},
]


def _refusal(exit_code: int, code: str | None, extra: str | None = None) -> PreRunCheckError:
    kind = "capacity" if exit_code == EXIT_CAPACITY else "validation"
    return PreRunCheckError(
        "2 error(s) found before the run.",
        exit_code=exit_code,
        error_kind=kind,
        code=code,
        extra=extra,
        messages=MESSAGES,
    )


def test_the_context_accessor_never_holds_the_code() -> None:
    assert list(_refusal(EXIT_USAGE, "a.one").context_members()) == ["error_kind", "messages"]
    with_extra = _refusal(EXIT_USAGE, "a.one", extra="cloud").context_members()
    assert list(with_extra) == ["error_kind", "extra", "messages"]
    assert "code" not in with_extra


def _run_refused(tmp_path: Path, refusal: PreRunCheckError, *flags: str):
    cfg = _config(tmp_path)
    with mock.patch("decoy.cli.run._prepare.check_before_run", side_effect=refusal):
        return runner.invoke(app, ["run", str(cfg), *flags])


@pytest.mark.parametrize(("exit_code", "kind"), [(EXIT_USAGE, "validation"), (5, "capacity")])
def test_run_emits_the_refusal_code_and_every_message(
    tmp_path: Path, exit_code: int, kind: str
) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    result = _run_refused(tmp_path, _refusal(exit_code, "a.one"), "--json")

    assert result.exit_code == exit_code, result.output
    doc = _doc(result)
    jsonschema.validate(doc, SCHEMA)
    assert doc["code"] == "a.one"
    assert doc["error_kind"] == kind
    assert doc["messages"] == MESSAGES
    assert list(doc) == [
        "command", "status", "error", "code", "config", "mode", "error_kind", "messages",
        "result", "result_status",
    ]  # fmt: skip


def test_a_pre_run_capacity_refusal_human_line(tmp_path: Path) -> None:
    result = _run_refused(tmp_path, _refusal(EXIT_CAPACITY, "a.one"))

    line = next(x for x in result.stderr.splitlines() if "capacity:" in x)
    assert line.startswith("error: capacity: ")
    assert "[a.one]" not in result.stderr


def test_an_invalid_top_level_code_is_left_out(tmp_path: Path) -> None:
    result = _run_refused(tmp_path, _refusal(EXIT_USAGE, "Bad-Code"), "--json")

    assert result.exit_code == EXIT_USAGE, result.output
    doc = _doc(result)
    assert "code" not in doc
    assert doc["messages"] == MESSAGES


def test_tokenize_emits_the_first_layout_code_and_every_message(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    findings = [
        GateFinding("config", "error", "layout.first_code", "first", "targets"),
        GateFinding("config", "error", "layout.second_code", "second", "targets"),
    ]
    with mock.patch("decoy.cli.tokenize.layout_findings", return_value=findings):
        result = runner.invoke(
            app, ["tokenize", str(cfg), "--vault", str(tmp_path / "v.db"), "--json"]
        )

    assert result.exit_code == EXIT_USAGE, result.output
    doc = _doc(result)
    assert doc["command"] == "tokenize"
    assert doc["code"] == "layout.first_code"
    assert [m["code"] for m in doc["messages"]] == ["layout.first_code", "layout.second_code"]
    assert list(doc)[:4] == ["command", "status", "error", "code"]
    assert doc["config"] == str(cfg)
    assert json.dumps(doc).count('"layout.first_code"') >= 2
