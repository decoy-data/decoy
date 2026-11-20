"""AT-9: a launcher-owned `decoy` shim attests the run; the repro command cannot attest to itself."""

from __future__ import annotations

import sys

import pytest
from scripts.qa import io as qio
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


def test_an_executable_script_in_the_folder_runs_from_its_copy(tmp_path) -> None:
    src = tmp_path / "finding"
    src.mkdir()
    script = src / "repro.sh"
    script.write_text("#!/bin/sh\ndecoy run\n")
    script.chmod(0o700)
    assert go(["./repro.sh"], folder=src).reproduced


def test_a_missing_program_is_invalid_and_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    assert go(["./no-such-program"]) == repro.Result(False, "invalid")
    monkeypatch.setattr(repro, "_real_decoy", lambda: REAL)
    args = ["--recorded-exit", "3", "--signature", "disk full", "--", "./no-such-program"]
    assert repro.main(args) == 2


@pytest.mark.parametrize(
    ("reason", "code"),
    [("reproduced", 0), ("wrong-exit", 1), ("signature-missing", 1), ("stalled", 1),
     ("invalid", 2), ("bypass", 2), ("needs-manual-repro", 2)],
)  # fmt: skip
def test_cli_exit_codes_by_reason(monkeypatch: pytest.MonkeyPatch, reason: str, code: int) -> None:
    monkeypatch.setattr(repro, "run", lambda *a, **k: repro.Result(reason == "reproduced", reason))
    assert repro.main(["--recorded-exit", "3", "--signature", "disk full", "--", "x"]) == code


def test_only_the_program_position_counts_as_a_bypass() -> None:
    for cmd in (
        ["sh", "-c", "mkdir -p x/decoy && cd ./x/decoy && cd - && decoy run"],
        ["sh", "-c", "decoy run --out out/decoy"],
    ):
        assert go(cmd).reproduced, cmd
    assert go(["sh", "-c", "echo hi; /opt/bin/decoy run"]) == repro.Result(False, "bypass")


def test_a_symlink_in_the_folder_is_refused_and_the_size_is_capped(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "finding"
    src.mkdir()
    (src / "link").symlink_to("/etc/hosts")
    assert go(["sh", "-c", "decoy run"], folder=src) == repro.Result(False, "invalid")
    (src / "link").unlink()
    (src / "big.bin").write_bytes(b"x" * 100)
    monkeypatch.setattr(qio, "MAX_TREE_BYTES", 50)
    assert go(["sh", "-c", "decoy run"], folder=src) == repro.Result(False, "invalid")


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


@pytest.mark.parametrize(
    "cmd",
    [
        ["decoy", "run", "/tmp/decoy"],
        ["decoy", "run", "-m", "decoy"],
        ["decoy", "run", "--out", "../out/decoy", "uv", "run"],
        ["sh", "-c", "decoy run /tmp/decoy"],
        ["sh", "-c", "decoy run -m decoy"],
        ["sh", "-c", "decoy run; echo python -m decoy"],
    ],
)
def test_a_decoy_path_or_module_flag_used_as_an_argument_is_not_a_bypass(cmd: list[str]) -> None:
    assert go(cmd) == repro.Result(True, "reproduced")


@pytest.mark.parametrize(
    "cmd",
    [
        ["env", "FOO=1", "/usr/bin/decoy", "run"],
        ["FOO=1", "/usr/bin/decoy", "run"],
        ["python3", "-m", "decoy", "run"],
        ["python3", "-I", "-m", "decoy.cli"],
        ["sh", "-c", "FOO=1 /usr/bin/decoy run"],
        ["bash", "-lc", "cd x && /opt/decoy run"],
    ],
)
def test_the_program_position_is_still_caught_through_wrappers_and_shells(cmd: list[str]) -> None:
    assert go(cmd) == repro.Result(False, "bypass")


@pytest.mark.parametrize(
    "cmd",
    [
        ["echo", "/tmp/decoy"],
        ["cat", "-m", "decoy"],
        ["python3", "tool.py", "-m", "decoy"],
        ["sh", "script.sh", "-c", "/opt/decoy run"],
    ],
)
def test_another_program_that_names_decoy_as_an_argument_is_not_a_bypass(cmd: list[str]) -> None:
    assert not repro._bypasses(cmd)


def test_the_shim_has_no_file_writer_of_its_own() -> None:
    """The witness goes through `io.append_private_line`; the shim itself never opens or writes."""
    import ast

    source = repro._SHIM.format(
        python="/usr/bin/python3", root="/r", real=["/x/decoy"], nonce="n", witness="/w"
    )
    calls = {
        ast.unparse(node.func) for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)
    }
    assert "append_private_line" in calls
    banned = {"open", "os.open", "os.write", "os.fdopen", "io.open", "Path.write_text"}
    assert not calls & banned, calls & banned
    assert not any(c.startswith("os.") for c in calls), calls
