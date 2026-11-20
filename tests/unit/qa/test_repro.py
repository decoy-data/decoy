"""AT-9: a launcher-owned `decoy` shim attests the run; the repro command cannot attest to itself."""

from __future__ import annotations

import sys

import pytest
from scripts.qa import repro

# A stand-in for the installed decoy: fails the way the recorded finding did.
FAKE = "import os,sys; sys.stderr.write('error: disk full\\n'); sys.stdout.write('ran\\n'); sys.exit(3)"
REAL = [sys.executable, "-c", FAKE]
CALLS_DECOY = ["sh", "-c", "decoy run shop"]


def go(cmd: list[str], code: int = 3, sig: str = "disk full", **kw) -> repro.Result:
    return repro.run(cmd, code, sig, real=REAL, **kw)


def test_a_failure_that_decoy_itself_gave_reproduces() -> None:
    assert go(CALLS_DECOY) == repro.Result(True, "reproduced")


def test_the_exit_is_decoys_not_the_commands() -> None:
    assert go(["sh", "-c", "decoy run; exit 0"]).reproduced  # the wrapper's own exit is ignored


def test_a_script_that_echoes_the_signature_without_calling_decoy_fails() -> None:
    cmd = ["sh", "-c", "echo 'error: disk full' >&2; exit 3"]
    assert go(cmd) == repro.Result(False, "needs-manual-repro")


def test_a_command_cannot_forge_the_witness_from_its_environment_or_folders() -> None:
    probe = (
        "env | grep -qi -e witness -e nonce -e qa_ && exit 9; "
        "ls -a . 2>/dev/null | grep -qi -e witness -e shim && exit 9; decoy run"
    )
    assert go(["sh", "-c", probe]).reproduced


def test_the_exit_and_the_signature_must_both_recur_in_decoys_output() -> None:
    assert go(CALLS_DECOY, 4).reason == "wrong-exit"
    assert go(CALLS_DECOY, 3, "no such text").reason == "signature-missing"
    # The signature must come from decoy's own capture, not from what the command printed.
    cmd = ["sh", "-c", "decoy run; echo 'forged signature text' >&2"]
    assert go(cmd, 3, "forged signature text").reason == "signature-missing"


def test_each_run_gets_a_fresh_decoy_home_and_a_clean_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DECOY_HOME", "/tmp/testers-own-home")
    monkeypatch.setenv("QA_SECRET", "carried-over")
    body = "import os,sys; sys.stderr.write('home=%s leak=%s' % (os.environ['DECOY_HOME'], 'QA_SECRET' in os.environ)); sys.exit(3)"
    real = [sys.executable, "-c", body]
    assert repro.run(CALLS_DECOY, 3, "leak=False", real=real).reproduced
    assert not repro.run(CALLS_DECOY, 3, "testers-own-home", real=real).reproduced


def test_a_stall_is_reported_not_hung() -> None:
    cmd = ["sh", "-c", "sleep 30"]
    assert go(cmd, 0, "x-signature", timeout=0.5).reason == "stalled"


def test_a_grandchild_holding_the_pipe_cannot_hang_the_runner() -> None:
    cmd = ["sh", "-c", "sleep 30 & sleep 30"]
    assert go(cmd, 0, "x-signature", timeout=0.5).reason == "stalled"


def test_no_command_no_decoy_or_a_short_signature_is_not_a_repro() -> None:
    assert go([]).reason == "invalid"
    assert go(CALLS_DECOY, 3, "error").reason == "invalid"
    assert repro.run(CALLS_DECOY, 3, "disk full", real=[]).reason == "needs-manual-repro"


def test_cli_exit_follows_the_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repro, "_real_decoy", lambda: REAL)
    ok = ["--recorded-exit", "3", "--signature", "disk full", "--", *CALLS_DECOY]
    assert repro.main(ok) == 0
    assert repro.main(["--recorded-exit", "2", *ok[2:]]) == 1


@pytest.mark.parametrize(
    "cmd",
    [
        ["/usr/bin/decoy", "run"],
        ["./decoy", "run"],
        ["../bin/decoy", "run"],
        ["python", "-m", "decoy", "run"],
        ["uv", "run", "decoy", "run"],
        ["sh", "-c", "/opt/x/decoy run shop"],
        ["sh", "-c", "uv run decoy run"],
        ["sh", "-c", "python -m decoy run"],
    ],
)
def test_a_command_that_bypasses_the_shim_is_refused(cmd: list[str]) -> None:
    assert go(cmd) == repro.Result(False, "bypass")


def test_the_repro_runs_in_a_copy_of_its_folder(tmp_path) -> None:
    src = tmp_path / "finding"
    src.mkdir()
    (src / "input.csv").write_text("a,b\n1,2\n")
    cmd = ["sh", "-c", "test -f input.csv && echo changed > input.csv && decoy run"]
    assert go(cmd, folder=src).reproduced
    assert (src / "input.csv").read_text() == "a,b\n1,2\n"  # the original is untouched
    assert go(["sh", "-c", "test -f input.csv && decoy run"]).reason == "needs-manual-repro"


def test_cli_exit_2_means_needs_manual_repro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repro, "_real_decoy", lambda: REAL)
    args = ["--recorded-exit", "3", "--signature", "disk full", "--", "sh", "-c", "exit 3"]
    assert repro.main(args) == 2
