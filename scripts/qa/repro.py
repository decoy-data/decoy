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
import re
import secrets
import shlex
import signal
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.qa.io import (
    PRIVATE_EXEC,
    copy_private_tree,
    private_scratch_dir,
    publish_private_once,
)

TIMEOUT = 120
# A short signature such as "error" recurs by luck, so it proves nothing.
MIN_SIGNATURE = 8

# The shim runs under the tester's PATH. It writes its witness through `scripts.qa.io`, the one QA
# writer, so it has no file writer of its own. A test parses it and fails on any open or write call.
# Everything it needs is baked in at launch time; nothing is read from the environment.
_SHIM = """#!{python}
import json, subprocess, sys
sys.path.insert(0, {root!r})
from scripts.qa.io import append_private_line
real = {real!r}
done = subprocess.run(real + sys.argv[1:], capture_output=True)
sys.stdout.buffer.write(done.stdout)
sys.stderr.buffer.write(done.stderr)
append_private_line({witness!r}, json.dumps({{
    "nonce": {nonce!r},
    "argv": sys.argv[1:],
    "exit": done.returncode,
    "output": (done.stdout + done.stderr).decode("utf-8", "replace"),
}}))
sys.exit(done.returncode)
"""
ROOT = str(Path(__file__).resolve().parents[2])


@dataclass(frozen=True)
class Result:
    reproduced: bool
    # reproduced, needs-manual-repro (nothing attested the run: a person must try it, and it is
    # not a finding that failed to reproduce), bypass, invalid, wrong-exit, signature-missing,
    # stalled
    reason: str


def _real_decoy() -> list[str]:
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(folder, "decoy")
        if folder and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return [candidate]
    return []


_SEPARATORS = {";", "&&", "||", "|", "&", "(", ")"}


def _commands(text: str) -> list[list[str]]:
    """The commands inside a `sh -c` string, split on shell separators."""
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    commands: list[list[str]] = [[]]
    try:
        for word in lexer:
            if word in _SEPARATORS:
                commands.append([])
            else:
                commands[-1].append(word)
    except ValueError:
        return []
    return [c for c in commands if c]


_SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
_WRAPPERS = {"exec", "command", "nohup", "time", "env"}
_PYTHON = re.compile(r"python[0-9.]*")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def _program(words: Sequence[str]) -> list[str]:
    """The command with leading `NAME=value` words and wrapper words (`env`, `exec`) removed."""
    rest = list(words)
    while rest and (_ASSIGNMENT.match(rest[0]) or rest[0] in _WRAPPERS):
        rest = [w for w in rest[1:] if not w.startswith("-")] if rest[0] == "env" else rest[1:]
    return rest


def _starts_decoy_around_the_shim(words: Sequence[str]) -> bool:
    """True when `words` itself, at the program position, runs decoy by another route."""
    words = _program(words)
    if not words:
        return False
    name = words[0].rstrip("/").rsplit("/", 1)[-1]
    if words[:2] == ["uv", "run"]:
        return True
    if "/" in words[0]:
        if name == "decoy":
            return True
    if _PYTHON.fullmatch(name):
        i = 1
        while i < len(words) and words[i].startswith("-"):
            if words[i] == "-m":
                module = words[i + 1] if i + 1 < len(words) else ""
                return module == "decoy" or module.startswith("decoy.")
            i += 2 if words[i] in {"-W", "-X"} else 1
    return False


def _shell_strings(argv: Sequence[str]) -> list[str]:
    """The `-c` command string of a shell invocation, and nothing else: an argument of any other
    program is data, not a command."""
    words = _program(argv)
    if not words or words[0].rstrip("/").rsplit("/", 1)[-1] not in _SHELLS:
        return []
    for i, word in enumerate(words[1:], 1):
        if re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", word):  # -c, -lc
            return words[i + 1 : i + 2]
        if not word.startswith("-"):
            break
    return []


def _bypasses(argv: Sequence[str]) -> bool:
    """True when the command starts decoy by a route that skips the PATH shim.

    Only the program position counts: argv[0], and the first word of each command inside a
    shell's `-c` string. A path or flag that merely ends in `decoy` anywhere else, such as
    `cat /tmp/decoy` or `tool -m decoy`, is an argument and not a bypass.
    """
    lines = [list(argv)] + [c for text in _shell_strings(argv) for c in _commands(text)]
    return any(_starts_decoy_around_the_shim(words) for words in lines)


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
    folder: Path | None = None,
    timeout: float = TIMEOUT,
) -> Result:
    """Run `argv` in a fresh home with the shim first on PATH. `real` is the decoy to attest.

    `folder` is the finding's repro folder. The command runs in a private copy of it, so a repro
    cannot change the original.
    """
    real = list(_real_decoy() if real is None else real)
    if not argv or len(signature) < MIN_SIGNATURE:
        return Result(False, "invalid")
    if _bypasses(argv):
        return Result(False, "bypass")
    if not real:
        return Result(False, "needs-manual-repro")
    nonce = secrets.token_hex(16)
    with private_scratch_dir() as home, private_scratch_dir() as control:
        witness = str(control / "witness.jsonl")
        shim_dir = control / "bin"
        shim = _SHIM.format(
            python=sys.executable, root=ROOT, real=real, nonce=nonce, witness=witness
        )
        publish_private_once(shim_dir / "decoy", shim.encode(), mode=PRIVATE_EXEC)
        cwd = home
        if folder is not None:
            cwd = home / "repro"
            try:
                copy_private_tree(folder, cwd)
            except ValueError:  # a symlink in the folder, or over the size cap
                return Result(False, "invalid")
        env = {
            "PATH": f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "HOME": str(home),
            "DECOY_HOME": str(home / "decoy"),
        }
        # A new session lets the timeout kill the whole group, so a grandchild that keeps the
        # pipes open cannot hang the runner.
        try:
            proc = subprocess.Popen(
                list(argv),
                env=env,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError:  # the program is missing or not executable
            return Result(False, "invalid")
        try:
            proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            return Result(False, "stalled")
        calls = _witness_lines(witness, nonce)
    if not calls:
        return Result(False, "needs-manual-repro")
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
    if result.reproduced:
        return 0
    return 2 if result.reason in {"invalid", "bypass", "needs-manual-repro"} else 1


if __name__ == "__main__":
    sys.exit(main())
