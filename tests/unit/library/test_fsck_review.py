"""fsck and repair on a damaged library: review round 1 on #210, items 1, 2, 3, 4 and 6.

- 1: a FIFO at `index.sqlite` hangs neither check nor repair; it is a finding.
- 2: one unreadable entry (LAYOUT, a log, a fan folder, an object, a FIFO object) is its own
  finding and never aborts check or repair.
- 3: repair removes a ref only when it was read, parsed and points at no stored record; a ref
  it cannot read is `ref_unreadable` and kept; a BOM before the id is not corruption.
- 4: repair re-reads each quarantine candidate under the lock and moves it only when it does
  not parse or its content is not the id its name says.
- 6: a failed unlink after the quarantine copy is reported for that entry and repair goes on.

The test process may run as root, where a 0000 mode does not stop a read, so "cannot read" is
the CLI's one reader (or `os.scandir`) refusing that one path.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from tests.unit.library._helpers import envelope, job_log, object_path

from decoy.cli.io import DECOY_DIR, UnsafeFileError
from decoy.cli.library import _fs, _fsck, open_library

posix_only = pytest.mark.skipif(os.name != "posix", reason="FIFOs")


def _local(_p: Path) -> None:
    return None


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / DECOY_DIR


def _library(root: Path, count: int = 2) -> list[str]:
    library = open_library(root, probe=_local)
    return [library.put(envelope(n)).id for n in range(count)]


def _codes(report: _fsck.FsckReport, level: str = "finding") -> set[tuple[str, str]]:
    return {(f.code, f.target) for f in report.items if f.level == level}


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _refuse_reads(
    monkeypatch: pytest.MonkeyPatch, refused: Callable[[Path], bool], times: int = -1
) -> list[Path]:
    """The one reader refuses the matching paths (`times` < 0: always)."""
    seen: list[Path] = []
    real = _fs.read_small_file

    def reader(path: Path, max_bytes: int) -> object:
        if refused(Path(path)) and (times < 0 or len(seen) < times):
            seen.append(Path(path))
            raise UnsafeFileError("unreadable")
        return real(path, max_bytes)

    monkeypatch.setattr(_fs, "read_small_file", reader)
    return seen


def _in_thread(call: Callable[[], object]) -> tuple[bool, list[object]]:
    out: list[object] = []

    def run() -> None:
        try:
            out.append(call())
        except BaseException as exc:
            out.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=10)
    return worker.is_alive(), out


def _free_fifo(path: Path) -> None:
    """Unblock a reader stuck on the FIFO so a hung test can finish."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return
    os.write(fd, b"x" * 100)
    os.close(fd)


# -- item 1 ---------------------------------------------------------------------------------------


@posix_only
@pytest.mark.parametrize("step", ["check", "repair"])
def test_a_fifo_index_hangs_nothing_and_is_a_finding(root: Path, step: str) -> None:
    _library(root)
    index = root / "library" / "index.sqlite"
    index.unlink()
    os.mkfifo(index)
    call = (
        (lambda: _fsck.check(root))
        if step == "check"
        else (lambda: _fsck.repair(root, probe=_local))
    )
    hung, out = _in_thread(call)
    if hung:
        _free_fifo(index)
    assert not hung, f"{step} blocked on a FIFO index"
    assert out and not isinstance(out[0], BaseException), out
    report = out[0] if step == "check" else out[0][1]  # type: ignore[index]
    assert ("index_not_file", "library/index.sqlite") in _codes(report)  # type: ignore[arg-type]


# -- item 2 ---------------------------------------------------------------------------------------


def test_an_unreadable_layout_is_a_finding_not_an_abort(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _library(root)
    _refuse_reads(monkeypatch, lambda p: p.name == "LAYOUT")
    report = _fsck.check(root)  # must not raise
    assert ("layout_unreadable", "library/LAYOUT") in _codes(report)
    _actions, after = _fsck.repair(root, probe=_local)  # must not raise
    assert ("layout_unreadable", "library/LAYOUT") in _codes(after)


def test_an_unreadable_log_is_a_finding_not_an_abort(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _library(root)
    logs = root / "logs"
    logs.mkdir(mode=0o700)
    (logs / "a.jsonl").write_bytes(job_log())
    (logs / "b.jsonl").write_bytes(b"not a log\n")
    _refuse_reads(monkeypatch, lambda p: p.name == "a.jsonl")
    report = _fsck.check(root)
    assert ("log_unreadable", "logs/a.jsonl") in _codes(report)
    assert ("log_header_invalid", "logs/b.jsonl") in _codes(report)  # the next log still checked


def test_an_unreadable_fan_folder_is_a_finding_not_an_abort(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _library(root, 2)
    fan = object_path(root, ids[0]).parent
    real = os.scandir

    def scandir(path: object = ".") -> object:
        if Path(str(path)) == fan:
            raise PermissionError(13, "denied")
        return real(path)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "scandir", scandir)
    report = _fsck.check(root)  # must not raise
    assert ("object_unreadable", _rel(root, fan)) in _codes(report)
    _actions, _after = _fsck.repair(root, probe=_local)  # must not raise


def test_an_unreadable_object_is_kept_and_repair_goes_on(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _library(root, 2)
    stored = object_path(root, ids[0])
    refs = root / "library" / "refs" / "sample-run"
    refs.mkdir(parents=True)
    (refs / "gone").write_text(envelope(9).id + "\n", encoding="utf-8")
    _refuse_reads(monkeypatch, lambda p: p == stored)
    report = _fsck.check(root)
    assert ("object_unreadable", _rel(root, stored)) in _codes(report)
    assert not any(f.code == "object_corrupt" for f in report.items)
    actions, _after = _fsck.repair(root, probe=_local)
    assert stored.exists()
    assert not any(a.code == "object_quarantined" for a in actions)
    assert {a.code for a in actions} >= {"ref_removed", "index_rebuilt"}  # repair went on


@posix_only
def test_a_fifo_with_an_object_name_is_never_opened_or_moved(root: Path) -> None:
    _library(root, 1)
    name = object_path(root, envelope(7).id)
    name.parent.mkdir(exist_ok=True)
    os.mkfifo(name)
    hung, out = _in_thread(lambda: _fsck.repair(root, probe=_local))
    if hung:
        _free_fifo(name)
    assert not hung and out and not isinstance(out[0], BaseException), out
    assert name.exists() and not name.is_file()
    actions, after = out[0]  # type: ignore[misc]
    assert ("object_unreadable", _rel(root, name)) in _codes(after)
    assert not any(a.code == "object_quarantined" for a in actions)


# -- item 3 ---------------------------------------------------------------------------------------


def test_a_bom_before_a_stored_id_is_a_sound_ref(root: Path) -> None:
    ids = _library(root, 1)
    refs = root / "library" / "refs" / "sample-run"
    refs.mkdir(parents=True)
    ref = refs / "main"
    ref.write_bytes(("﻿" + ids[0] + "\n").encode("utf-8"))
    report = _fsck.check(root)
    assert not any(t == "library/refs/sample-run/main" for _c, t in _codes(report))
    actions, _after = _fsck.repair(root, probe=_local)
    assert not any(a.code == "ref_removed" for a in actions)
    assert ref.exists()


def test_an_unreadable_ref_is_reported_and_kept(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _library(root, 1)
    library = open_library(root, probe=_local)
    library.set_ref("sample-run", "main", ids[0])
    ref = root / "library" / "refs" / "sample-run" / "main"
    _refuse_reads(monkeypatch, lambda p: p == ref)
    report = _fsck.check(root)
    assert ("ref_unreadable", "library/refs/sample-run/main") in _codes(report)
    actions, _after = _fsck.repair(root, probe=_local)
    assert not any(a.code == "ref_removed" for a in actions)
    monkeypatch.undo()
    assert ref.exists() and library.read_ref("sample-run", "main") == ids[0]


# -- item 4 ---------------------------------------------------------------------------------------


def test_a_read_that_fails_once_during_check_never_quarantines_a_valid_record(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _library(root, 2)
    stored = object_path(root, ids[0])
    seen = _refuse_reads(monkeypatch, lambda p: p == stored, times=1)
    actions, _after = _fsck.repair(root, probe=_local)
    assert seen  # non-vacuous: the check's read failed
    assert stored.exists() and open_library(root, probe=_local).get(ids[0]).id == ids[0]
    assert not any(a.code == "object_quarantined" for a in actions)


def test_a_stale_corrupt_report_is_rechecked_under_the_lock(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The report says corrupt; by the time repair acts the file is the record its name says."""
    ids = _library(root, 2)
    stored = object_path(root, ids[0])
    good = stored.read_bytes()
    stored.write_bytes(b"{broken")
    stale = _fsck.check(root)
    assert ("object_corrupt", _rel(root, stored)) in _codes(stale)  # non-vacuous
    stored.write_bytes(good)
    real_check = _fsck.check
    calls: list[int] = []

    def first_stale(*args: object, **kw: object) -> _fsck.FsckReport:
        calls.append(1)
        return stale if len(calls) == 1 else real_check(*args, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(_fsck, "check", first_stale)
    actions, _after = _fsck.repair(root, probe=_local)
    assert stored.read_bytes() == good
    assert not any(a.code == "object_quarantined" for a in actions)


def test_a_parseable_object_with_another_id_is_still_quarantined(root: Path) -> None:
    """Control for item 4: the id rule moves a file whose content is another record."""
    ids = _library(root, 2)
    stored = object_path(root, ids[0])
    stored.write_bytes(object_path(root, ids[1]).read_bytes())
    actions, _after = _fsck.repair(root, probe=_local)
    assert not stored.exists()
    assert ("object_quarantined", _rel(root, stored)) in {(a.code, a.target) for a in actions}


# -- item 6 ---------------------------------------------------------------------------------------


def test_a_failed_unlink_after_the_copy_is_reported_and_repair_goes_on(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _library(root, 2)
    stored = object_path(root, ids[0])
    stored.write_bytes(b"{broken")
    refs = root / "library" / "refs" / "sample-run"
    refs.mkdir(parents=True)
    (refs / "gone").write_text(envelope(9).id + "\n", encoding="utf-8")
    real = os.unlink

    def unlink(path: object, *a: object, **kw: object) -> None:
        if Path(str(path)) == stored:
            raise PermissionError(13, "denied")
        real(path, *a, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "unlink", unlink)
    actions, _after = _fsck.repair(root, probe=_local)  # must not raise
    codes = {(a.code, a.target) for a in actions}
    assert ("quarantine_failed", _rel(root, stored)) in codes
    assert ("object_quarantined", _rel(root, stored)) not in codes
    assert {c for c, _t in codes} >= {"ref_removed", "index_rebuilt"}
    assert stored.exists()


def test_no_new_message_names_a_value(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _library(root, 1)
    _refuse_reads(monkeypatch, lambda p: p.name == "LAYOUT")
    text = json.dumps([(f.code, f.target) for f in _fsck.check(root).items])
    assert str(root) not in text and "sample" not in text
