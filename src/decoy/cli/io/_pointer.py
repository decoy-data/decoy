"""`out/<name>/LATEST`: the one CLI module that reads or swaps the run pointer.

Pattern: git's ref update with an expected old value (`git update-ref <ref> <new> <old>`). The
engine's `CurrentPointer` takes the lock, `swap` compares the bytes read earlier with the file
and replaces it only on a match. This module builds that pointer for the CLI and keeps two
CLI rules on top: "later run id wins" and value-free warnings.

On a host without the engine's lock (win32) `swap_latest` keeps the plain atomic write the CLI
used before. G-ONE-POINTER (`tests/sentry/io_policy/test_one_pointer.py`) fails on any other
module that builds a pointer or touches `LATEST`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from decoy._atomic import AtomicWriteError, WriteMode, replace_symlink, write_atomic
from decoy.cli.io._layout_errors import (
    LATEST_COMMIT_UNCERTAIN,
    LATEST_INVALID,
    LATEST_LINK_FAILED,
    LATEST_WRITE_FAILED,
    LayoutWarning,
)
from decoy.cli.io._run_id import is_run_id
from decoy.cli.io._small_file import read_small_bytes

if TYPE_CHECKING:
    from decoy_engine.publication import CurrentPointer

_LATEST_FILE = "LATEST"
# Not `latest`: macOS and Windows fold case by default, so it would collide with `LATEST`.
_LATEST_LINK = "current"
# The CLI's one wait on the `LATEST` lock (the engine's own default is not exported).
LATEST_LOCK_TIMEOUT_S: Final = 30.0


def _pointer_supported() -> bool:
    """The engine's own test: on win32 its lock and `adopt_file` are unavailable."""
    return sys.platform != "win32"


def lock_name(leaf: str) -> str:
    """The `.<leaf>.decoy-lock` file the engine's `OutputDir.lock` keeps beside `leaf`."""
    return f".{leaf}.decoy-lock"


def pointer_supported() -> bool:
    """Whether this host runs the engine's pointer (the one answer every delivery caller reads)."""
    return _pointer_supported()


def latest_pointer(folder: Path) -> CurrentPointer:
    """The pointer for `folder / LATEST`, locked through the same leaf."""
    # Imported here: the engine stays unloaded until a command needs it (startup rule).
    from decoy_engine.fileaccess import FileRequest, FileRole, current
    from decoy_engine.publication import CurrentPointer, LocalPointerStore

    request = FileRequest(
        FileRole.TARGET_OUTPUT, "write", str(folder / _LATEST_FILE), "layout.latest"
    )
    leaf = current().output_dir(request)
    return CurrentPointer(LocalPointerStore(leaf), leaf)


def _decode(raw: bytes) -> str | None:
    return raw.decode("utf-8", errors="replace").strip() or None


def read_latest(folder: Path) -> str | None:
    """The run id `LATEST` names; None when absent, "" when something unreadable is there."""
    path = folder / _LATEST_FILE
    data = read_small_bytes(path)
    if data is None:
        # A link, pipe or unreadable file is not absent: "" fails is_run_id, so it is warned.
        return "" if os.path.lexists(path) else None
    return _decode(data)


def link_current(folder: Path, run_id: str) -> list[LayoutWarning]:
    """Point `current` at `run_id`; the warning list is empty on success (POSIX only)."""
    return _link_current(folder, run_id)


def _link_current(folder: Path, run_id: str) -> list[LayoutWarning]:
    if os.name != "posix":
        return []
    try:
        replace_symlink(folder / _LATEST_LINK, run_id)
    except (AtomicWriteError, OSError):
        return [LATEST_LINK_FAILED.warning(path=folder)]
    return []


def _judge(folder: Path, seen: str | None, run_id: str) -> tuple[list[LayoutWarning], bool]:
    """The one "later run id wins" rule: the warnings so far and whether to move `LATEST`.

    A malformed id is warned about and replaced; a later id is kept. Both swap paths call
    this, the locked one while it holds the lock.
    """
    if seen is None:
        return [], True
    if not is_run_id(seen):
        return [LATEST_INVALID.warning(path=folder)], True
    return [], seen <= run_id


def latest_shown(folder: Path) -> Path:
    """The path to show as the latest run: `current` unless it lags behind `LATEST`.

    If the `current` swap failed after `LATEST` moved, the link names the old run. `LATEST` is
    the authority, so a valid id that the link does not name resolves to its run folder.
    """
    if os.name != "posix":
        return folder / _LATEST_FILE
    link = folder / _LATEST_LINK
    named = read_latest(folder)
    if named is None or not is_run_id(named):
        return link
    try:
        current = str(link.readlink())
    except OSError:
        current = None
    return link if current == named else folder / named


def swap_latest(folder: Path, run_id: str) -> tuple[LayoutWarning, ...]:
    """Point `LATEST` and `current` at `run_id`; a failure is a warning, never an exit.

    Moves nothing when `LATEST` already names a later run id. A readable but malformed
    `LATEST` is warned about and replaced; an unreadable one is warned about and kept.
    """
    if not _pointer_supported():
        return _write_latest(folder, run_id)
    from decoy_engine.fileaccess import (
        FileAccessDenied,
        FileAccessUnavailable,
        LockTimeout,
        LockUnavailable,
    )
    from decoy_engine.publication import PointerUnreadable

    warnings: list[LayoutWarning] = []
    failed = uncertain = False
    try:
        pointer = latest_pointer(folder)
        with pointer.locked(LATEST_LOCK_TIMEOUT_S) as held:
            state = pointer.read()
            seen = _decode(state.raw) if state.raw is not None else None
            warnings, proceed = _judge(folder, seen, run_id)
            if not proceed:
                return ()
            result = held.swap(state, run_id)
            if result == "replaced":
                warnings += _link_current(folder, run_id)
            elif result in ("uncertain", "unknown"):
                uncertain = True
                warnings += _link_current(folder, run_id)
            else:
                failed = True
    except (
        PointerUnreadable,
        LockTimeout,
        LockUnavailable,
        FileAccessDenied,
        FileAccessUnavailable,
        OSError,
    ):
        failed = True
    # Decided after the handler closes, so no exception context rides on the warning.
    if failed:
        return (*warnings, LATEST_WRITE_FAILED.warning(path=folder))
    if uncertain:
        warnings.append(LATEST_COMMIT_UNCERTAIN.warning(path=folder))
    return tuple(warnings)


def _write_latest(folder: Path, run_id: str) -> tuple[LayoutWarning, ...]:
    """The pre-pointer write, kept for hosts without the engine's lock (named limit, F22 W1)."""
    warnings, proceed = _judge(folder, read_latest(folder), run_id)
    if not proceed:
        return ()
    try:
        write_atomic(folder, _LATEST_FILE, f"{run_id}\n".encode(), WriteMode.REPLACE)
    except AtomicWriteError:
        return (*warnings, LATEST_WRITE_FAILED.warning(path=folder))
    return (*warnings, *_link_current(folder, run_id))
