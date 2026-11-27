"""C2a-1: two runs that share a lock (AT-51) and a run that is killed (AT-46).

AT-51 holds run 1 inside `PreVisible.restore`, after it failed before the visibility point, and
starts run 2 as a real process. Case A: one pipeline, so run 2 waits at the shared pointer lock.
Case B: two pipelines and one `--evidence-out`, so run 2 is refused at the side-file lock.
AT-46 kills a real `decoy run` at four points and reads what is left on disk.
"""

from __future__ import annotations

import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest import mock

import pytest

from decoy.cli.io import _delivery
from tests.child_env import child_env
from tests.e2e.delivery_sink._support import latest, project, run, runs, vaulted

posix = pytest.mark.skipif(sys.platform == "win32", reason="the strict stage is POSIX only")


def _decoy(*argv: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "decoy", *argv],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=child_env(),
        text=True,
    )


class _HeldRestore:
    """Run 1: fails at the bind, then waits inside `PreVisible.restore` until released."""

    def __init__(self, yml: Path, *args: str) -> None:
        self.paused, self.release = threading.Event(), threading.Event()
        self.result = None
        self._thread = threading.Thread(target=self._run, args=(yml, *args))

    def _run(self, yml: Path, *args: str) -> None:
        real_restore = _delivery.PreVisible.restore

        def held(pre) -> None:
            self.paused.set()
            assert self.release.wait(60)
            real_restore(pre)

        def refuse_bind(*_a, **_k):
            raise OSError("the bind is refused")

        stage = __import__("decoy_engine.publication._stage", fromlist=["x"])
        with (
            mock.patch.object(stage, "publish_unit", refuse_bind),
            mock.patch.object(_delivery.PreVisible, "restore", held),
        ):
            self.result = run(yml, *args)

    def __enter__(self) -> _HeldRestore:
        self._thread.start()
        assert self.paused.wait(60), "run 1 never reached restore"
        return self

    def __exit__(self, *_exc) -> None:
        self.release.set()
        self._thread.join(60)


@posix
def test_at51_a_second_run_on_the_same_pipeline_waits_for_the_restore(tmp_path: Path) -> None:
    root, yml = project(tmp_path, tables=1)
    with _HeldRestore(yml, "--evidence-out", str(tmp_path / "e1.json")) as first:
        second = _decoy("run", str(yml), "--json", "--evidence-out", str(tmp_path / "e2.json"))
        time.sleep(3)
        assert second.poll() is None, "run 2 passed the pointer lock while run 1 was in restore"
        first.release.set()
        out, err = second.communicate(timeout=120)
    assert first.result is not None and first.result.exit_code == 3
    assert second.returncode == 0, (out[-400:], err[-400:])
    (folder,) = runs(root)
    assert latest(root) == folder.name
    assert (tmp_path / "e2.json").is_file()
    assert not list(tmp_path.glob(".*.attempt"))


@posix
def test_at51_a_second_pipeline_on_the_same_evidence_file_is_refused_until_restore_ends(
    tmp_path: Path,
) -> None:
    root, yml = project(tmp_path, tables=1)
    other = yml.parent.parent / "other" / "pipeline.yaml"
    other.parent.mkdir()
    shutil.copy(yml, other)
    shared = tmp_path / "shared.json"
    with _HeldRestore(yml, "--evidence-out", str(shared)) as first:
        refused = _decoy("run", str(other), "--json", "--evidence-out", str(shared))
        out, err = refused.communicate(timeout=120)
        assert refused.returncode == 3, (out[-400:], err[-400:])
        assert not shared.exists()  # run 2 replaced nothing while run 1 held the file
        first.release.set()
    retry = _decoy("run", str(other), "--json", "--evidence-out", str(shared))
    out, err = retry.communicate(timeout=120)
    assert retry.returncode == 0, (out[-400:], err[-400:])
    assert shared.is_file()
    assert not list(tmp_path.glob(".*.attempt"))
    assert (root / "out" / "other" / "LATEST").is_file()


# --- AT-46: SIGKILL at four points ----------------------------------------------------------

_DRIVER = """
import os, signal, sys
point = sys.argv[1]
def die():
    os.kill(os.getpid(), signal.SIGKILL)
def after(owner, name):
    real = getattr(owner, name)
    def wrapper(*a, **k):
        result = real(*a, **k)
        die()
        return result
    setattr(owner, name, wrapper)
def before(owner, name):
    real = getattr(owner, name)
    def wrapper(*a, **k):
        die()
    setattr(owner, name, wrapper)
if point == "end_of_w4":
    from decoy.cli.run import _evidence
    after(_evidence, "write_attempts")
elif point == "after_bind":
    from decoy_engine.publication import LocalPointerStore
    before(LocalPointerStore, "replace_if")
elif point == "after_swap":
    from decoy_engine.publication import LocalPointerStore
    after(LocalPointerStore, "replace_if")
elif point == "after_live_evidence":
    from decoy.cli.run import _evidence
    after(_evidence, "publish_attempts")
from decoy.__main__ import app
sys.argv = ["decoy"] + sys.argv[2:]
app()
"""

_POINTS = ["end_of_w4", "after_bind", "after_swap", "after_live_evidence"]


@posix
@pytest.mark.parametrize("point", _POINTS)
def test_at46_a_killed_run_leaves_a_state_the_next_run_can_read(
    tmp_path: Path, point: str, monkeypatch
) -> None:
    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    evidence, result_file, vault = tmp_path / "e.json", tmp_path / "r.json", tmp_path / "v.db"
    evidence.write_text("old evidence\n", encoding="utf-8")
    result_file.write_text("sentinel\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            _DRIVER,
            point,
            "run",
            str(yml),
            "--json",
            "--vault",
            str(vault),
            "--evidence-out",
            str(evidence),
            "--result",
            str(result_file),
        ],
        capture_output=True,
        text=True,
        env=child_env(),
        timeout=300,
    )
    assert proc.returncode == -signal.SIGKILL, (proc.returncode, proc.stderr[-400:])
    assert proc.stdout.strip() == ""  # no JSON from a killed run
    assert result_file.read_text(encoding="utf-8") == "sentinel\n"
    swapped = point in {"after_swap", "after_live_evidence"}
    assert (latest(root) is not None) is swapped
    assert vault.exists() is (point != "end_of_w4")  # published inside the bind
    live = evidence.read_text(encoding="utf-8")
    if point == "after_live_evidence":
        assert live != "old evidence\n"
    elif not swapped:
        assert live == "old evidence\n"  # never evidence for a run that is not current
    if point == "after_bind":
        rerun = subprocess.run(
            [sys.executable, "-m", "decoy", "run", str(yml), "--json", "--vault", str(vault)],
            capture_output=True,
            text=True,
            env=child_env(),
            timeout=300,
        )
        assert rerun.returncode == 1
        assert "vault_exists" in rerun.stdout + rerun.stderr
