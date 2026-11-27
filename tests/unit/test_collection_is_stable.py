"""Collection must give the same test ids in every process.

pytest-xdist aborts when two workers collect different ids ("Different tests were collected
between gw2 and gw3"). A parametrize value that holds a random salt, an object address, a
set order or a timestamp makes the ids differ per process. This collects the whole suite in
two fresh processes with different hash seeds and compares the ids.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _collect(seed: str) -> subprocess.Popen[str]:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:randomly", "tests"]
    return subprocess.Popen(
        cmd, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )


def _ids(proc: subprocess.Popen[str]) -> set[str]:
    out, _ = proc.communicate()
    assert proc.returncode == 0, out[-2000:]
    return {line for line in out.splitlines() if "::" in line}


@pytest.mark.serial
@pytest.mark.timeout(900)
def test_two_processes_collect_the_same_ids() -> None:
    first, second = _collect("1"), _collect("2")
    a, b = _ids(first), _ids(second)
    assert a, "collected nothing"
    only_a, only_b = sorted(a - b), sorted(b - a)
    assert not only_a and not only_b, (
        "ids differ between processes; give the parametrize stable ids=... "
        f"(first: {only_a[:5]}, second: {only_b[:5]})"
    )
