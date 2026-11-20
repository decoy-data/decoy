"""Run a finding's repro on a clean node and decide if the failure recurs (plan 5.7 step 4, AT-9).

    python -m scripts.qa.repro --recorded-exit 3 --signature "disk full" -- sh repro.sh

No repro, no bug. The repro command must not be able to vouch for itself, so the launcher owns the
evidence. It puts a `decoy` shim first on PATH. The shim runs the real installed decoy, captures
decoy's own output and exit code, and records them with a nonce in a witness file. That file sits
in a launcher folder that is not the command's cwd or HOME, and its path is not passed to the
command. "Reproduced" needs a witness line with the nonce, decoy's own exit equal to the recorded
exit, and the signature in decoy's own captured output. A script that prints the signature and
exits with the right code, without calling decoy, leaves no witness and fails.

This is a guard against a mistaken or replayed repro, not against a hostile one: the command runs as
the same user and could in principle search the disk for the witness.

The signature is a fixed phrase from the finding (an error class or message key), never data. The
result holds a verdict word and no output.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from scripts.qa.io import PRIVATE_EXEC, private_scratch_dir, publish_private_once

TIMEOUT = 120
# A short signature such as "error" recurs by luck, so it proves nothing.
MIN_SIGNATURE = 8

# The shim runs under the tester's PATH, so it uses only the standard library. Everything it needs
# is baked in at launch time; nothing is read from the environment.
_SHIM = """#!{python}
import json, os, subprocess, sys
real = {real!r}
done = subprocess.run(real + sys.argv[1:], capture_output=True)
sys.stdout.buffer.write(done.stdout)
sys.stderr.buffer.write(done.stderr)
line = json.dumps({{
    "nonce": {nonce!r},
    "argv": sys.argv[1:],
    "exit": done.returncode,
    "output": (done.stdout + done.stderr).decode("utf-8", "replace"),
}})
fd = os.open({witness!r}, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
os.write(fd, (line + "\\n").encode())
os.close(fd)
sys.exit(done.returncode)
"""


@dataclass(frozen=True)
class Result:
    reproduced: bool
    reason: str  # reproduced, not-run, wrong-exit, signature-missing, stalled


def _real_decoy() -> list[str]:
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(folder, "decoy")
        if folder and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return [candidate]
    return []


def _witness_lines(path: str, nonce: str) -> list[dict[str, object]]:
    if not os.path.isfile(path):
        return []
    found = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            try:
                doc = json.loads(line)
            except ValueError:
                continue
            if isinstance(doc, dict) and doc.get("nonce") == nonce:
                found.append(doc)
    return found


def run(
    argv: Sequence[str],
    recorded_exit: int,
    signature: str,
    *,
    real: Sequence[str] | None = None,
    timeout: float = TIMEOUT,
) -> Result:
    """Run `argv` in a fresh home with the shim first on PATH. `real` is the decoy to attest."""
    real = list(_real_decoy() if real is None else real)
    if not argv or not real or len(signature) < MIN_SIGNATURE:
        return Result(False, "not-run")
    nonce = secrets.token_hex(16)
    with private_scratch_dir() as home, private_scratch_dir() as control:
        witness = str(control / "witness.jsonl")
        shim_dir = control / "bin"
        shim = _SHIM.format(python=sys.executable, real=real, nonce=nonce, witness=witness)
        publish_private_once(shim_dir / "decoy", shim.encode(), mode=PRIVATE_EXEC)
        env = {
            "PATH": f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "HOME": str(home),
            "DECOY_HOME": str(home / "decoy"),
        }
        # A new session lets the timeout kill the whole group, so a grandchild that keeps the
        # pipes open cannot hang the runner.
        proc = subprocess.Popen(
            list(argv),
            env=env,
            cwd=home,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            return Result(False, "stalled")
        calls = _witness_lines(witness, nonce)
    if not calls:
        return Result(False, "not-run")
    if not any(c.get("exit") == recorded_exit for c in calls):
        return Result(False, "wrong-exit")
    if not any(c.get("exit") == recorded_exit and signature in str(c.get("output")) for c in calls):
        return Result(False, "signature-missing")
    return Result(True, "reproduced")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recorded-exit", type=int, required=True)
    ap.add_argument("--signature", required=True)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    result = run(cmd, args.recorded_exit, args.signature, real=_real_decoy())
    sys.stdout.write(f"{result.reason}\n")
    return 0 if result.reproduced else 1


if __name__ == "__main__":
    sys.exit(main())
