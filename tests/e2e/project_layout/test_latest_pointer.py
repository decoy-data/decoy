"""AT-11, AT-13, AT-62, AT-73 and AT-74 (DELIV C2p): `LATEST` is read and swapped in `io/_pointer.py`.

`swap_latest` takes the engine's pointer lock, reads once, keeps "later run id wins" and swaps
by compare-and-set. `read_latest` keeps the values `run_history` has always seen. A `LATEST` the
engine cannot read (a link, a folder, over 4 KiB) is warned about and left alone.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from decoy_engine.fileaccess import FileRequest, FileRole, current
from decoy_engine.publication import (
    CurrentPointer,
    LocalPointerStore,
    PointerResult,
    PointerState,
)

from decoy.cli.io import PipelineName, RunLayout, _pointer, mint_invocation_id

START = datetime(2026, 11, 9, 10, 15, 0, 123456, tzinfo=timezone.utc)
ORDERS = PipelineName("orders", True, "pipelines/orders/pipeline.yaml")
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="the pointer path is POSIX")
CANARY = "CANARY-7f3a91"


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "decoy.yaml").write_text("kind: decoy-project/v1\n", encoding="utf-8")
    return root


def _open(root: Path, seconds: int = 0) -> RunLayout:
    started = START + timedelta(seconds=seconds)
    return RunLayout.open(root, ORDERS, mint_invocation_id(), started)


def _latest(root: Path) -> Path:
    return root / "out" / "orders" / "LATEST"


def _leaf(folder: Path):
    request = FileRequest(FileRole.TARGET_OUTPUT, "write", str(folder / "LATEST"), "layout.latest")
    return current().output_dir(request)


def _codes(warnings: tuple) -> list[str]:
    return [w.code for w in warnings]


# --- AT-13 read_latest keeps today's values ------------------------------------------------


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"r1\n", "r1"),
        (b"../x\n", "../x"),
        (b"r1\nr2", "r1\nr2"),
        (b"", None),
        (b"  \n", None),
    ],
    ids=["run id", "traversal text", "two lines", "empty", "blank"],
)
def test_read_latest_returns_the_decoded_text_or_none(
    tmp_path: Path, content: bytes, expected: str | None
) -> None:
    (tmp_path / "LATEST").write_bytes(content)
    assert _pointer.read_latest(tmp_path) == expected


def test_read_latest_of_an_absent_file_is_none(tmp_path: Path) -> None:
    assert _pointer.read_latest(tmp_path) is None


@posix_only
@pytest.mark.parametrize("kind", ["symlink", "fifo", "folder"])
def test_read_latest_of_something_unreadable_is_the_empty_string(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "LATEST"
    if kind == "symlink":
        target = tmp_path / "t.txt"
        target.write_text("r1\n", encoding="utf-8")
        path.symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        path.mkdir()
    assert _pointer.read_latest(tmp_path) == ""


# --- AT-62 later run id wins ---------------------------------------------------------------


class _CountingStore(LocalPointerStore):
    """A real store that counts the swaps it is asked for."""

    swaps = 0

    def replace_if(self, expected: PointerState, new: bytes) -> PointerResult:
        type(self).swaps += 1
        return super().replace_if(expected, new)


def _use_store(monkeypatch: pytest.MonkeyPatch, store_type: type[LocalPointerStore]) -> None:
    def build(folder: Path) -> CurrentPointer:
        leaf = _leaf(folder)
        return CurrentPointer(store_type(leaf), leaf)

    monkeypatch.setattr(_pointer, "latest_pointer", build)


@posix_only
def test_an_older_run_id_never_swaps_and_a_newer_one_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    r5, r9, r10 = _open(root, 5), _open(root, 9), _open(root, 10)
    assert r5.run is not None and r9.run is not None and r10.run is not None
    _latest(root).write_text(f"{r9.run.run_id}\n", encoding="utf-8")
    _CountingStore.swaps = 0
    _use_store(monkeypatch, _CountingStore)

    assert r5.commit_latest() == ()
    assert _CountingStore.swaps == 0
    assert _latest(root).read_text(encoding="utf-8") == f"{r9.run.run_id}\n"

    assert r10.commit_latest() == ()
    assert _CountingStore.swaps == 1
    assert _latest(root).read_text(encoding="utf-8") == f"{r10.run.run_id}\n"


# --- AT-11 a file that changed between read and swap ---------------------------------------


class _ChangedAfterRead(LocalPointerStore):
    """Another writer replaces the file right after the one read `swap_latest` makes."""

    def __init__(self, leaf, folder: Path) -> None:
        super().__init__(leaf)
        self._folder = folder

    def read(self) -> PointerState:
        state = super().read()
        (self._folder / "LATEST").write_bytes(b"INTERLOPER\n")
        return state


@posix_only
def test_a_stale_swap_is_a_write_failure_and_leaves_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    layout = _open(root)
    _latest(root).write_text("20200101T000000000000Z-00000000\n", encoding="utf-8")

    def build(folder: Path) -> CurrentPointer:
        leaf = _leaf(folder)
        return CurrentPointer(_ChangedAfterRead(leaf, folder), leaf)

    monkeypatch.setattr(_pointer, "latest_pointer", build)

    warnings = layout.commit_latest()

    assert _codes(warnings) == ["layout.latest_write_failed"]
    assert _latest(root).read_bytes() == b"INTERLOPER\n"


class _Uncertain(LocalPointerStore):
    """The replace lands, then the folder sync fails: the engine answers "uncertain"."""

    def replace_if(self, expected: PointerState, new: bytes) -> PointerResult:
        super().replace_if(expected, new)
        return "uncertain"


@posix_only
def test_an_uncertain_swap_warns_and_still_points_current_at_the_new_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    layout = _open(root)
    assert layout.run is not None
    _latest(root).write_text("20200101T000000000000Z-00000000\n", encoding="utf-8")
    _use_store(monkeypatch, _Uncertain)

    warnings = layout.commit_latest()

    assert _codes(warnings) == ["layout.latest_commit_uncertain"]
    assert _latest(root).read_text(encoding="utf-8") == f"{layout.run.run_id}\n"
    link = root / "out" / "orders" / "current"
    assert link.is_symlink() and link.readlink() == Path(layout.run.run_id)


# --- AT-73 an unreadable LATEST is warned about and kept -----------------------------------


@posix_only
@pytest.mark.parametrize("kind", ["symlink", "folder", "over 4 KiB"])
def test_an_unreadable_latest_is_kept_and_warned_without_a_value(tmp_path: Path, kind: str) -> None:
    root = _project(tmp_path)
    layout = _open(root)
    latest = _latest(root)
    target = tmp_path / f"{CANARY}.txt"
    if kind == "symlink":
        target.write_text(f"{CANARY}\n", encoding="utf-8")
        latest.symlink_to(target)
    elif kind == "folder":
        latest.mkdir()
    else:
        latest.write_bytes(f"{CANARY}\n".encode() + b"x" * 5120)
    before = latest.read_bytes() if kind == "over 4 KiB" else None

    warnings = layout.commit_latest()

    assert _codes(warnings) == ["layout.latest_write_failed"]
    assert all(CANARY not in w.message for w in warnings)
    if kind == "symlink":
        assert latest.is_symlink() and latest.readlink() == target
        assert target.read_text(encoding="utf-8") == f"{CANARY}\n"
    elif kind == "folder":
        assert latest.is_dir()
    else:
        assert latest.read_bytes() == before


# --- AT-74 the non-POSIX branch ------------------------------------------------------------


def test_the_predicate_follows_the_engines_win32_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    for platform, expected in (("win32", False), ("linux", True), ("darwin", True)):
        monkeypatch.setattr(sys, "platform", platform)
        assert _pointer._pointer_supported() is expected, platform


def test_an_unsupported_host_writes_latest_the_old_way(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    layout = _open(root)
    assert layout.run is not None

    def never(folder: Path) -> CurrentPointer:
        raise AssertionError("a CurrentPointer was built on an unsupported host")

    monkeypatch.setattr(_pointer, "_pointer_supported", lambda: False)
    monkeypatch.setattr(_pointer, "latest_pointer", never)

    assert layout.commit_latest() == ()
    assert _latest(root).read_text(encoding="utf-8") == f"{layout.run.run_id}\n"
    assert not (root / "out" / "orders" / ".LATEST.decoy-lock").exists()


# --- V1 a stale `current` never shows as Latest --------------------------------------------

OLD_RUN = "20200101T000000000000Z-00000000"


def _fail_link(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(link: Path, target: str) -> None:
        raise OSError(28, "no space left")

    monkeypatch.setattr(_pointer, "replace_symlink", boom)


@posix_only
def test_a_failed_link_swap_leaves_summary_and_readers_on_the_new_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    layout = _open(root)
    assert layout.run is not None
    folder = root / "out" / "orders"
    (folder / OLD_RUN).mkdir()
    _latest(root).write_text(f"{OLD_RUN}\n", encoding="utf-8")
    (folder / "current").symlink_to(OLD_RUN)
    _fail_link(monkeypatch)

    warnings = layout.commit_latest()

    assert _codes(warnings) == ["layout.latest_link_failed"]
    assert (folder / "current").readlink() == Path(OLD_RUN)
    assert _pointer.read_latest(folder) == layout.run.run_id
    assert _pointer.latest_shown(folder) == folder / layout.run.run_id
    shown = dict(layout.summary_facts())["Latest"]
    assert shown.endswith(layout.run.run_id)
    assert OLD_RUN not in shown


@posix_only
def test_a_fresh_link_is_what_the_summary_shows(tmp_path: Path) -> None:
    root = _project(tmp_path)
    layout = _open(root)
    assert layout.commit_latest() == ()
    folder = root / "out" / "orders"
    assert _pointer.latest_shown(folder) == folder / "current"
    assert dict(layout.summary_facts())["Latest"].endswith("current")


@posix_only
def test_a_missing_link_with_a_valid_latest_shows_the_run_folder(tmp_path: Path) -> None:
    folder = tmp_path / "orders"
    (folder / OLD_RUN).mkdir(parents=True)
    (folder / "LATEST").write_text(f"{OLD_RUN}\n", encoding="utf-8")
    assert _pointer.latest_shown(folder) == folder / OLD_RUN


# --- DESIGN the decision is made once, for both paths --------------------------------------

LATER = "20300101T000000000000Z-00000000"


@pytest.mark.parametrize(
    ("seen", "proceed", "codes"),
    [
        (None, True, []),
        (OLD_RUN, True, []),
        ("garbage", True, ["layout.latest_invalid"]),
        (LATER, False, []),
    ],
    ids=["absent", "older", "malformed", "later"],
)
def test_the_decision_helper(seen: str | None, proceed: bool, codes: list[str]) -> None:
    warnings, go = _pointer._judge(Path("p"), seen, "20250101T000000000000Z-00000000")
    assert go is proceed
    assert [w.code for w in warnings] == codes


@pytest.mark.parametrize("host", ["posix", "no lock"])
@pytest.mark.parametrize(
    ("seen", "codes", "moves"),
    [
        (OLD_RUN, [], True),
        ("garbage", ["layout.latest_invalid"], True),
        (LATER, [], False),
    ],
    ids=["older", "malformed", "later"],
)
def test_both_paths_apply_the_same_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    host: str,
    seen: str,
    codes: list[str],
    moves: bool,
) -> None:
    if host == "posix" and sys.platform == "win32":
        pytest.skip("the pointer path is POSIX")
    root = _project(tmp_path)
    layout = _open(root, 5)
    assert layout.run is not None
    _latest(root).write_text(f"{seen}\n", encoding="utf-8")
    if host == "no lock":
        monkeypatch.setattr(_pointer, "_pointer_supported", lambda: False)

    warnings = layout.commit_latest()

    assert _codes(warnings) == codes
    expected = layout.run.run_id if moves else seen
    assert _latest(root).read_text(encoding="utf-8") == f"{expected}\n"
