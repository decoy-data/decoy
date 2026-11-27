"""Collection must give the same test ids, in the same order, in every process.

pytest-xdist aborts when two workers collect different ids ("Different tests were collected
between gw2 and gw3"). A parametrize value that holds a random salt, an object address, a
set order or a timestamp makes the ids differ per process. This collects the whole suite in
two fresh processes with different hash seeds and compares the ordered id lists.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from tests.child_env import child_env

ROOT = Path(__file__).resolve().parents[3]
TIMEOUT = 600


def _collect(seed: str) -> subprocess.Popen[str]:
    # Same isolation as the serial-resources collector: no inherited PYTEST_* options such as
    # PYTEST_ADDOPTS=-k, no addopts, and no xdist in the child.
    env = child_env(drop_prefixes=("PYTEST_",))
    env["PYTHONHASHSEED"] = seed
    cmd = [
        sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
        "-p", "no:xdist", "-p", "no:randomly", "-o", "addopts=", "tests",
    ]  # fmt: skip
    return subprocess.Popen(
        cmd, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )


def _ids(proc: subprocess.Popen[str]) -> list[str]:
    out, _ = proc.communicate(timeout=TIMEOUT)
    assert proc.returncode == 0, out[-2000:]
    return [line for line in out.splitlines() if "::" in line]


@pytest.mark.serial
@pytest.mark.timeout(2 * TIMEOUT + 60)
def test_two_processes_collect_the_same_ids_in_the_same_order() -> None:
    procs = [_collect("1"), _collect("2")]
    try:
        a, b = (_ids(p) for p in procs)
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
                p.communicate()
    assert len(a) > 1000, f"collected too little to mean anything: {len(a)}"
    if a != b:
        only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
        pytest.fail(
            "ids differ between processes; give the parametrize stable ids=... "
            f"(first only: {only_a[:5]}, second only: {only_b[:5]}, same set: {not only_a})"
        )
