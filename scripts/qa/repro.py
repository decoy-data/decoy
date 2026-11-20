"""Run a finding's repro on a clean node and decide if the failure recurs (plan 5.7 step 4, AT-9).

    python -m scripts.qa.repro --recorded-exit 3 --signature "disk full" -- sh repro.sh

No repro, no bug. A recorded exit code proves nothing, because anything can print one. So the
runner gives the command a fresh `DECOY_HOME` and a launcher nonce, and the command must write
that nonce to the witness file. A run with no witness did not run the repro and fails. The failure
only counts when the exit code and the recorded signature both recur.

The signature is a fixed phrase from the finding (an error class or message key), never data. The
result holds a verdict word and no output.
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from scripts.qa.io import private_scratch_dir

NONCE_VAR = "QA_REPRO_NONCE"
WITNESS_VAR = "QA_REPRO_WITNESS"
TIMEOUT = 120


@dataclass(frozen=True)
class Result:
    reproduced: bool
    reason: str  # reproduced, not-run, wrong-exit, signature-missing, stalled


def run(
    argv: Sequence[str], recorded_exit: int, signature: str, *, timeout: float = TIMEOUT
) -> Result:
    """Run `argv` in a fresh home. The environment is cleaned so no tester state carries over."""
    if not argv or not signature:
        return Result(False, "not-run")
    nonce = secrets.token_hex(16)
    with private_scratch_dir() as home:
        witness = home / "witness"
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(home),
            "DECOY_HOME": str(home / "decoy"),
            NONCE_VAR: nonce,
            WITNESS_VAR: str(witness),
        }
        try:
            done = subprocess.run(
                list(argv), env=env, cwd=home, capture_output=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired:
            return Result(False, "stalled")
        saw = witness.read_text(encoding="utf-8") if witness.is_file() else ""
    if saw != nonce:
        return Result(False, "not-run")
    if done.returncode != recorded_exit:
        return Result(False, "wrong-exit")
    if signature.encode() not in done.stdout + done.stderr:
        return Result(False, "signature-missing")
    return Result(True, "reproduced")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recorded-exit", type=int, required=True)
    ap.add_argument("--signature", required=True)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    result = run(cmd, args.recorded_exit, args.signature)
    sys.stdout.write(f"{result.reason}\n")
    return 0 if result.reproduced else 1


if __name__ == "__main__":
    sys.exit(main())
