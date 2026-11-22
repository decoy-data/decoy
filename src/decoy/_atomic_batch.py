"""The one-folder batch publish, split out of `_atomic` to keep that file under its size cap.

`publish_local_targets` publishes a few files of one folder as one rollback unit; the rules
are in `_atomic`'s docstring. This module depends on `_atomic` and `_atomic` never imports it.
Four steps that move or link a file (`_stage_bytes`, `_backup`, `_publish`, `_rollback`) stay
in `_atomic`, the one choke point for them, and are read off that module at call time, so a
test that patches `_atomic._publish` still reaches the batch. This module holds the folder
lock and the order of the steps.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from decoy import _atomic
from decoy._atomic import (
    ATOMIC_BATCH_BUSY,
    ATOMIC_BATCH_INVALID,
    ATOMIC_ROLLBACK_INCOMPLETE,
    ATOMIC_TARGET_BUSY,
    ATOMIC_TARGET_EXISTS,
    ATOMIC_WRITE_FAILED,
    AtomicWriteError,
    WriteMode,
    _final_bits,
    _require_component,
    _sync_directories,
    _TargetHeld,
    destination_entry,
)
from decoy._private_file import (
    PRIVATE_BUSY,
    PRIVATE_OPEN_FAILED,
    PrivateFileError,
    advisory_lock_available,
    try_lock_exclusive,
)

__all__ = ["LocalTarget", "publish_local_targets"]


@dataclass(frozen=True)
class LocalTarget:
    """One file of a `publish_local_targets` batch. `private` publishes it 0600."""

    path: Path
    data: bytes
    mode: WriteMode = WriteMode.REPLACE
    private: bool = False


def _unlink_quietly(path: str | Path) -> None:
    with contextlib.suppress(OSError):
        os.unlink(path)


@contextlib.contextmanager
def _folder_lock(directory: Path) -> Iterator[None]:
    """Hold a non-blocking exclusive lock on the folder itself, so no loose lock file exists.

    POSIX only: without `fcntl` (Windows) there is no lock and two publishers can interleave.
    """
    if not advisory_lock_available():
        yield
        return
    failure: PrivateFileError | None = None
    fd = -1
    try:
        fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try_lock_exclusive(fd)
    except PrivateFileError as exc:
        failure = exc
    except OSError as exc:
        failure = PrivateFileError(PRIVATE_OPEN_FAILED, exc.errno)
    if failure is not None:
        if fd >= 0:
            os.close(fd)
        raise AtomicWriteError(
            ATOMIC_BATCH_BUSY if failure.code == PRIVATE_BUSY else ATOMIC_WRITE_FAILED,
            failure.errno,
        )
    try:
        yield
    finally:
        os.close(fd)  # closing releases the lock


def publish_local_targets(
    targets: Sequence[LocalTarget], *, check: Callable[[list[Path]], None] | None = None
) -> None:
    """Publish every target in order, or none: on any failure the old files come back.

    All targets sit in one folder, which this holds locked until it is done. Every file is
    staged and fsynced before the first replace. A file that already exists keeps a hard-link
    backup (the old inode, so its bytes and mode return exactly). If a replace fails, the
    published files are restored or removed and `AtomicWriteError` is raised; so are they on
    any other exception, `KeyboardInterrupt` included, which then propagates. A restore that
    fails keeps its backup and raises `ATOMIC_ROLLBACK_INCOMPLETE` instead. A `CREATE_ONCE`
    target that exists once the lock is held is refused before anything changes. Lock, backup
    or staging failures also refuse before the first replace. `check`, when given, receives the
    staged temp paths (in target order) once everything is staged and before the first replace;
    whatever it raises propagates and nothing has changed. The directory sync after the
    last replace can fail with `ATOMIC_SYNC_FAILED`: the new files are then in place.
    """
    if not targets:
        raise AtomicWriteError(ATOMIC_BATCH_INVALID)
    for target in targets:
        _require_component(target.path.name)
    resolve_failed = False
    resolve_errno: int | None = None
    try:
        reals = [destination_entry(t.path, follow_final=True) for t in targets]
    except OSError as exc:
        resolve_failed, resolve_errno = True, exc.errno
    if resolve_failed:
        raise AtomicWriteError(ATOMIC_WRITE_FAILED, resolve_errno)
    directory = reals[0].parent
    if any(r.parent != directory for r in reals) or len({r.name for r in reals}) != len(reals):
        raise AtomicWriteError(ATOMIC_BATCH_INVALID)

    staged: list[tuple[str, int]] = []
    backups: list[str | None] = []
    done: list[tuple[Path, str | None]] = []
    stuck: list[str] = []
    left: list[str] = []
    restored: list[str] = []
    settled = False  # the batch finished, or its rollback ran to the end
    failed = False
    failed_code = ATOMIC_WRITE_FAILED
    failed_errno: int | None = None
    try:
        with _folder_lock(directory):
            try:
                existing = [_existing(real) for real in reals]
                for target, old in zip(targets, existing, strict=True):
                    if target.mode is WriteMode.CREATE_ONCE and old is not None:
                        raise AtomicWriteError(ATOMIC_TARGET_EXISTS)
                for target, real in zip(targets, reals, strict=True):
                    staged.append(_atomic._stage_bytes(real, target.data, target.private))
                for real, old in zip(reals, existing, strict=True):
                    backups.append(None if old is None else _atomic._backup(real))
                if check is not None:
                    check([Path(tmp) for tmp, _created in staged])
                for target, real, old, (tmp, created) in zip(
                    targets, reals, existing, staged, strict=True
                ):
                    bits = _final_bits(tmp, old, target.private, created)
                    # Recorded before the replace: an interrupt that lands just after it must
                    # still find this target in the rollback.
                    done.append((real, backups[len(done)]))
                    if not _atomic._publish(tmp, real, bits, target.mode):
                        done.pop()  # refused with nothing replaced
                        raise AtomicWriteError(ATOMIC_TARGET_EXISTS)
                settled = True
            except BaseException as exc:
                stuck, left = _atomic._rollback(done, restored)
                settled = True
                if stuck or left:
                    pass  # reported below, after the backups are left in place
                elif isinstance(exc, OSError):
                    failed, failed_errno = True, exc.errno
                    if isinstance(exc, _TargetHeld):
                        failed_code = ATOMIC_TARGET_BUSY
                else:
                    raise
    finally:
        for tmp, _created in staged:
            _unlink_quietly(tmp)
        # An interrupt can end the rollback early: then only a backup that is back in place
        # (or never used) may go, because the rest still hold the old bytes.
        unsafe = set() if settled else {b for _real, b in done if b is not None} - set(restored)
        for backup in backups:
            if backup is not None and backup not in stuck and backup not in unsafe:
                _unlink_quietly(backup)
    if stuck or left:
        raise AtomicWriteError(
            ATOMIC_ROLLBACK_INCOMPLETE,
            kept=tuple(Path(name).name for name in stuck),
            left=tuple(left),
        )
    if failed:
        raise AtomicWriteError(failed_code, failed_errno)
    _sync_directories(directory, None)


def _existing(real: Path) -> os.stat_result | None:
    try:
        return os.stat(real)
    except FileNotFoundError:
        return None
