"""Every end of `decoy run` gives one run result document (RESULT C-DOC2).

The early refusals (a bad `--notify`, a `--rows` that cannot run, a bad `--master-key`), the
evidence write failure and Ctrl-C each print one `--json` envelope with `result` and
`result_status`. The exit integer is the one they had before: the document carries it, and the
process exits with it. Named limits (no document) are pinned at the end.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.e2e.run_result.test_run_result import MARKER, _model, _write

runner = CliRunner()
ADDED = {"result", "result_status"}
# The `--json` members each path printed before this slice, recorded on the base head. A path
# that printed nothing before has no entry: its set is new and the changelog says so.
BASE_KEYS = {
    "x3": {"command", "status", "error", "code", "config"},
    "x4": {"command", "status", "config", "error"},
}
DEFAULTS = ("x3", "x4", "x5")


def _evidence_failure():
    from decoy._atomic import AtomicWriteError

    return mock.patch(
        "decoy.cli.run._evidence.write_local_target", side_effect=AtomicWriteError("zz_marker_code")
    )


def _case(name: str, tmp_path: Path):
    """`(argv, patcher or None, expected exit)` for one exit path."""
    cfg = str(_write(tmp_path))
    run = ["run", cfg, "--json"]
    if name == "x3":
        return [*run, "--notify", "bogus"], None, 1
    if name == "x4":
        return [*run, "--rows", "5"], None, 1
    if name == "x5":
        return [*run, "--master-key", "zz", "--key-label", "k"], None, 2
    if name == "x6":
        patcher = mock.patch("decoy_engine.run_pipeline", side_effect=RuntimeError(MARKER))
        return run, patcher, 3
    if name == "x8":
        return [*run, "--evidence-out", str(tmp_path / "ev.json")], _evidence_failure(), 3
    if name == "x10":
        return run, None, 0
    assert name == "x11"
    patcher = mock.patch("decoy_engine.run_pipeline", side_effect=KeyboardInterrupt())
    return run, patcher, 130


def _invoke(argv: list[str], patcher):
    if patcher is None:
        return runner.invoke(app, argv)
    with patcher:
        return runner.invoke(app, argv)


@pytest.mark.parametrize("name", ["x3", "x4", "x5", "x6", "x8", "x10", "x11"])
def test_every_path_has_one_document(name: str, tmp_path: Path) -> None:
    argv, patcher, expected = _case(name, tmp_path)
    result = _invoke(argv, patcher)
    assert result.exit_code == expected, result.output
    payload = json.loads(result.stdout)  # exactly one object: the parse fails on a second
    doc = payload["result"]
    _model(doc)
    assert doc["exit_code"] == expected == result.exit_code
    assert payload["result_status"] == {"document": "built", "file": "not_requested", "code": None}
    if name in BASE_KEYS:
        assert set(payload) - ADDED == BASE_KEYS[name]
    if name in DEFAULTS:
        timings = doc["timings"]
        assert timings["started_at"] <= timings["finished_at"]
        assert doc["config"] is None
        assert doc["pipeline_kind"] is None
        assert doc["tables"] == []
        assert doc["route"]["execution_mode"] is None
        assert doc["delivery"]["mode"] == "in_place"
        assert doc["delivery"]["vault"] == "not_used"
        assert doc["failure"]["reason"] is None
    if name == "x5":
        assert "must be valid hex" in result.stderr
        assert payload["error"].startswith("--master-key must be valid hex")
    if name == "x8":
        assert doc["failure"]["category"] == "runtime"
        assert doc["failure"]["reason"] is None
        assert doc["status"] == "failed"
        assert "reason" not in payload
        assert payload["status"] == "error"
        assert "zz_marker_code" not in json.dumps(doc)
    assert MARKER not in json.dumps(doc)


# What each path wrote to stderr under `--json` on the base head. The envelope is added; the
# terminal text is not changed, and the evidence failure keeps its `error:` line.
JSON_STDERR = {"x5": "must be valid hex", "x8": "error:"}


@pytest.mark.parametrize("name", ["x3", "x4", "x5", "x6", "x8", "x10", "x11"])
def test_json_mode_stderr_matches_base(name: str, tmp_path: Path) -> None:
    argv, patcher, _ = _case(name, tmp_path)
    result = _invoke(argv, patcher)
    expected = JSON_STDERR.get(name)
    if expected is None:
        assert result.stderr == ""
    else:
        assert expected in result.stderr


def test_ctrl_c(tmp_path: Path) -> None:
    argv, patcher, _ = _case("x11", tmp_path)
    result = _invoke(argv, patcher)
    # The measurement on the base head: a CliRunner run exits 130 and prints nothing on stderr.
    assert result.exit_code == 130
    assert result.stderr == ""
    doc = json.loads(result.stdout)["result"]
    assert doc["status"] == "cancelled"
    assert doc["failure"]["category"] == "cancelled"
    assert doc["failure"]["reason"]["code"] == "run_cancelled"
    assert doc["exit_code"] == 130

    human = _invoke([a for a in argv if a != "--json"], patcher)
    assert human.exit_code == 130
    assert human.stderr == ""


def test_one_json_object(tmp_path: Path) -> None:
    # A failed build falls back to the exit alone and still writes one object.
    broken = mock.patch(
        "decoy_engine.run_result.build_run_result", side_effect=RuntimeError(MARKER)
    )
    for name in ("x3", "x8", "x11"):
        argv, patcher, expected = _case(name, tmp_path)
        with broken:
            result = _invoke(argv, patcher)
        assert result.exit_code == expected
        payload = json.loads(result.stdout)
        assert "result" not in payload
        assert payload["result_status"]["code"] == "run_result_build_failed"
        assert MARKER not in result.output


def test_human_mode_text_is_unchanged(tmp_path: Path) -> None:
    cfg = str(_write(tmp_path))
    bad_spec = runner.invoke(app, ["run", cfg, "--notify", "bogus"])
    assert bad_spec.exit_code == 1
    assert bad_spec.stderr.strip().startswith("error: [notify_spec_invalid]")
    assert bad_spec.stdout == ""
    preview = runner.invoke(app, ["run", cfg, "--rows", "5"])
    assert preview.exit_code == 1
    assert preview.stderr.strip().startswith("error: --rows previews generate tables only")
    argv, patcher, _ = _case("x8", tmp_path)
    failed = _invoke([a for a in argv if a != "--json"], patcher)
    assert failed.exit_code == 3
    assert failed.stdout == ""
    assert failed.stderr.startswith("error:")


def test_post_try_crash_is_a_named_limit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DECOY_DEBUG", raising=False)
    cfg = str(_write(tmp_path))
    boom = mock.patch("decoy.cli.evidence.build_manifest", side_effect=OSError("zz_marker_exc"))
    argv = ["run", cfg, "--json", "--evidence-out", str(tmp_path / "e.json")]
    with boom:
        result = runner.invoke(app, argv)
    assert result.exit_code == 1
    assert "internal error (OSError)" in result.stderr
    assert result.stdout == ""
    assert "zz_marker_exc" not in result.output


def test_no_document_limits(tmp_path: Path) -> None:
    cfg = str(_write(tmp_path))
    parse = runner.invoke(app, ["run", cfg, "--json", "--no-such-flag"])
    assert parse.exit_code == 2
    assert parse.stdout == ""

    conflict = runner.invoke(app, ["run", cfg, "--json", "--quiet"])
    assert conflict.exit_code == 1
    assert "result" not in conflict.stdout

    guard = mock.patch("decoy.distribution.runtime_guard.enforce", return_value="zz_refused")
    with guard:
        managed = runner.invoke(app, ["run", cfg, "--json"])
    assert managed.exit_code == 3
    assert "result" not in managed.stdout
    # SIGTERM, SIGKILL and the kernel OOM killer end the process with no document: a limit of
    # process termination, not covered by a test.


def _refusal_classes() -> list[type]:
    from decoy.cli.run import _context

    return [
        value
        for value in vars(_context).values()
        if isinstance(value, type)
        and issubclass(value, _context.RunRefusal)
        and value is not _context.RunRefusal
    ]


def test_typed_refusals_carry_no_context(tmp_path: Path) -> None:
    from decoy.cli import exit_codes
    from decoy.cli.run import _errors

    members = {*exit_codes.usage_error_types(), *_errors._cli_refusal_types()}
    assert set(_refusal_classes()) <= members

    caught: list[BaseException] = []
    real = _errors.refused

    def spy(ctx, refusal):
        caught.append(refusal)
        return real(ctx, refusal)

    with mock.patch.object(_errors, "refused", spy):
        for name in ("x3", "x4", "x8"):
            argv, patcher, _ = _case(name, tmp_path)
            _invoke(argv, patcher)
        _integrity_failure(tmp_path / "integrity")
        _invoke(["run", str(_write(tmp_path)), "--json"], _nothing_delivered())
    assert {type(r) for r in caught} == set(_refusal_classes())
    for refusal in caught:
        assert refusal.__context__ is None
        assert refusal.__cause__ is None


def _nothing_delivered():
    from decoy_engine.publication import DeliveryReceipt

    from decoy.cli.io import DeliverySink

    receipt = DeliveryReceipt("nothing", "delivery_pointer_moved")
    return mock.patch.object(DeliverySink, "deliver", return_value=receipt)


def _integrity_failure(root: Path):
    from decoy._atomic import AtomicWriteError
    from tests.e2e.integrity._fixtures import write_pipeline

    root.mkdir(exist_ok=True)
    cfg = write_pipeline(root, post={"integrity": True})
    failing = mock.patch(
        "decoy.cli.io._integrity_report.write_local_target",
        side_effect=AtomicWriteError("zz_marker_code"),
    )
    return _invoke(["run", str(cfg), "--json"], failing)


def test_integrity_write_failure_has_one_document(tmp_path: Path) -> None:
    """x8i: the post-scan report that cannot be written ends the run through the one choke
    point: exit 3, a built run result, failure category runtime, code in the envelope."""
    result = _integrity_failure(tmp_path)

    assert result.exit_code == 3, result.output
    payload = json.loads(result.stdout)
    doc = payload["result"]
    _model(doc)
    assert doc["exit_code"] == 3
    assert doc["status"] == "failed"
    assert doc["failure"]["category"] == "runtime"
    assert payload["status"] == "error"
    assert payload["code"] == "run.integrity_write_failed"
    assert {"config", "mode"} <= set(payload)
    assert payload["result_status"] == {"document": "built", "file": "not_requested", "code": None}
    assert "error:" in result.stderr
    assert "zz_marker_code" not in json.dumps(doc)
