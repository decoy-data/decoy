"""AT-9: the repro runner proves the command ran, then checks the failure recurs."""

from __future__ import annotations

import sys

import pytest
from scripts.qa import repro

WRITE_WITNESS = (
    "import os,sys; open(os.environ['QA_REPRO_WITNESS'],'w').write(os.environ['QA_REPRO_NONCE'])"
)


def py(body: str, honest: bool = True) -> list[str]:
    return [sys.executable, "-c", (WRITE_WITNESS + ";" if honest else "") + body]


def test_a_recurring_failure_with_its_witness_reproduces() -> None:
    cmd = py("sys.stderr.write('error: disk full\\n'); sys.exit(3)")
    assert repro.run(cmd, 3, "disk full") == repro.Result(True, "reproduced")


def test_a_replayed_exit_without_the_witness_fails() -> None:
    cmd = py("sys.stderr.write('error: disk full\\n'); sys.exit(3)", honest=False)
    assert repro.run(cmd, 3, "disk full") == repro.Result(False, "not-run")


def test_a_witness_with_the_wrong_nonce_fails() -> None:
    cmd = [sys.executable, "-c", "import os;open(os.environ['QA_REPRO_WITNESS'],'w').write('x');"]
    assert repro.run(cmd, 0, "x").reason == "not-run"


def test_the_exit_and_the_signature_must_both_recur() -> None:
    cmd = py("sys.stderr.write('error: other\\n'); sys.exit(3)")
    assert repro.run(cmd, 4, "other").reason == "wrong-exit"
    assert repro.run(cmd, 3, "disk full").reason == "signature-missing"


def test_each_run_gets_a_fresh_decoy_home_and_a_clean_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DECOY_HOME", "/tmp/testers-own-home")
    monkeypatch.setenv("QA_SECRET", "carried-over")
    body = "import os; print(os.environ['DECOY_HOME'], 'QA_SECRET' in os.environ); sys.exit(3)"
    assert repro.run(py(body), 3, "decoy False").reproduced  # the home ends in /decoy
    assert not repro.run(py(body), 3, "testers-own-home").reproduced


def test_a_stall_is_reported_not_hung() -> None:
    assert repro.run(py("import time; time.sleep(30)"), 0, "x", timeout=0.5).reason == "stalled"


def test_no_command_or_no_signature_is_not_a_repro() -> None:
    assert repro.run([], 0, "x").reason == "not-run"
    assert repro.run(py("pass"), 0, "").reason == "not-run"


def test_cli_exit_follows_the_verdict() -> None:
    cmd = py("sys.stderr.write('boom'); sys.exit(3)")
    assert repro.main(["--recorded-exit", "3", "--signature", "boom", "--", *cmd]) == 0
    assert repro.main(["--recorded-exit", "2", "--signature", "boom", "--", *cmd]) == 1
