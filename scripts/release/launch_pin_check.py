"""Launch pin check (RG-F3): the CLI is fit to launch on one engine D-4 tag.

Usage: ``python scripts/release/launch_pin_check.py --engine-tag vX.Y.Z``

Exit 0 pass, 1 failure, 2 usage error. Output is one line per step and never carries file
contents. The engine reason pin is not re-run here; ``release_checks.sh`` ran it at G1.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
Runner = Callable[[Sequence[str]], tuple[int, str]]
_TAG = re.compile(r"v\d+\.\d+\.\d+")
_VERSION = re.compile(r"\d+\.\d+\.\d+\S*")
_SENTRY = (
    "tests/sentry/test_ci_lock_installs.py::test_lock_profile_lives_in_lock_version_and_the_policy"
)


@dataclass(frozen=True)
class Result:
    ok: bool
    step: str
    code: str = ""
    detail: str = ""

    @property
    def line(self) -> str:
        if self.ok:
            return f"PASS {self.step}"
        return f"FAIL {self.step} {self.code} {self.detail}".rstrip()


def run_subprocess(argv: Sequence[str]) -> tuple[int, str]:
    proc = subprocess.run(list(argv), cwd=ROOT, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout


def _engine_tag(tag: str, run: Runner, root: Path) -> Result:
    rc, out = run(["bash", str(root / "scripts/dev/lock_version.sh"), "--engine-spec"])
    # Strip only the one newline `echo` adds: a second line or a stray CR must still fail.
    spec = out[:-1] if out.endswith("\n") else out
    if rc == 0 and re.fullmatch(rf"[^\n\r]*@{re.escape(tag)}", spec):
        return Result(True, "engine_tag")
    return Result(False, "engine_tag", "launch_pin_not_d4_tag", f"want @{tag}")


def _agreement(run: Runner, root: Path) -> list[Result]:
    steps = {
        "sentry": [sys.executable, "-m", "pytest", _SENTRY, "-q", "-p", "no:cacheprovider"],
        "lock_check": ["bash", str(root / "scripts/dev/lock.sh"), "--check"],
    }
    results = []
    for name, argv in steps.items():
        rc, _ = run(argv)
        if rc == 0:
            results.append(Result(True, name))
        else:
            results.append(Result(False, name, "pin_agreement_failed", name))
    return results


def _versions(run: Runner, root: Path) -> Result:
    # Any unreadable source is a failed step, not a crash, so every run still prints one line
    # per step. The detail stays value-free: no file text or exception message.
    try:
        try:
            import tomllib  # type: ignore[import-not-found,unused-ignore]
        except ModuleNotFoundError:  # Python 3.10
            import tomli as tomllib  # type: ignore[no-redef,import-not-found,unused-ignore]
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
        declared = str(tomllib.loads(text)["project"]["version"])
        source = (root / "src/decoy/_version.py").read_text(encoding="utf-8")
    except (OSError, KeyError, ModuleNotFoundError, ValueError):
        return Result(False, "versions", "version_disagreement", "version source unreadable")
    literal = re.search(r'^__version__ = "([^"]+)"', source, re.M)
    rc, out = run([sys.executable, "-m", "decoy", "--version"])
    cli = out.strip().removeprefix("decoy ") if rc == 0 else "unavailable"
    found = (declared, literal.group(1) if literal else "missing", cli)
    if len(set(found)) == 1 and _VERSION.fullmatch(found[0]):
        return Result(True, "versions")
    return Result(False, "versions", "version_disagreement", " ".join(found))


def check(tag: str, run: Runner, root: Path = ROOT) -> list[Result]:
    tag_result = _engine_tag(tag, run, root)
    return [tag_result, *_agreement(run, root), _versions(run, root)]


def main(argv: Sequence[str], runner: Runner = run_subprocess) -> int:
    args = list(argv)
    if len(args) != 2 or args[0] != "--engine-tag" or not _TAG.fullmatch(args[1]):
        print("usage: launch_pin_check.py --engine-tag vX.Y.Z", file=sys.stderr)
        return 2
    results = check(args[1], runner)
    for result in results:
        print(result.line)
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
