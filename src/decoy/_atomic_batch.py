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
    ledger = [_atomic._Entry(real) for real in reals]
    stuck: list[str] = []
    left: list[str] = []
    kept: list[str] = []
    pending: BaseException | None = None
    committed = False
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
                for entry, old in zip(ledger, existing, strict=True):
                    _link_backup(entry, old)
                if check is not None:
                    check([Path(tmp) for tmp, _created in staged])
                for target, entry, old, (tmp, created) in zip(
                    targets, ledger, existing, staged, strict=True
                ):
                    bits = _final_bits(tmp, old, target.private, created)
                    # Marked before the replace: an interrupt that lands just after it must
                    # still find this target in the rollback.
                    entry.stage = _atomic._Stage.REPLACED
                    if not _atomic._publish(tmp, entry.real, bits, target.mode):
                        entry.stage = _atomic._Stage.LINKED  # refused with nothing replaced
                        raise AtomicWriteError(ATOMIC_TARGET_EXISTS)
                committed = True
            except BaseException as exc:
                try:
                    stuck, left = _atomic._rollback(ledger)
                except BaseException as second:
                    # A second interrupt: the first fault's text can name a path, so it is
                    # not chained onto the one that propagates.
                    second.__context__ = None
                    raise
                if stuck or left:
                    pass  # reported below, after the backups are left in place
                elif isinstance(exc, OSError):
                    failed, failed_errno = True, exc.errno
                    if isinstance(exc, _TargetHeld):
                        failed_code = ATOMIC_TARGET_BUSY
                else:
                    raise
    except BaseException as exc:
        pending = exc
    # Cleanup runs outside the handler, so an interrupt in it is raised with no chained fault
    # (the fault's text can name a path).
    for tmp, _created in staged:
        _unlink_quietly(tmp)
    kept, interrupted = _settle(ledger, committed)
    if interrupted is not None:
        interrupted.__context__ = None
        raise interrupted
    if pending is not None:
        raise pending
    if kept or left:
        raise AtomicWriteError(
            ATOMIC_ROLLBACK_INCOMPLETE,
            kept=tuple(Path(name).name for name in kept),
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


def _link_backup(entry: _atomic._Entry, old: os.stat_result | None) -> None:
    """Make the hard-link backup of one target; the name is owned only once the link returns.

    The name is proposed first, so a failed link (`EEXIST`, `EPERM`, `EXDEV`, anything) leaves
    it unowned and whatever sits there untouched. An interrupt can land after the kernel made
    the link but before `os.link` returned; the fresh random name then shares the target's
    inode, which proves this run made it, so only that case is adopted.
    """
    if old is None:
        entry.stage = _atomic._Stage.LINKED  # a new target needs no backup
        return
    name = _atomic._backup_name(entry.real)
    entry.backup = name
    try:
        _atomic._backup(entry.real, name)
    except BaseException:
        if _atomic._same_file(name, entry.real):
            entry.stage = _atomic._Stage.LINKED
        raise
    entry.stage = _atomic._Stage.LINKED


def _settle(
    ledger: Sequence[_atomic._Entry], committed: bool
) -> tuple[list[str], BaseException | None]:
    """The one cleanup decision, the same for every outcome and every `BaseException`.

    Only owned (`LINKED` or later) backups are considered; a proposed, unlinked name is never
    touched. An owned backup goes when the batch committed, when its target was restored from
    it, or when the target is still the backup's inode (nothing changed, so the backup holds
    nothing the target lacks). That identity is checked here, not trusted from the rollback.
    Anything else is a value-bearing old file: it stays and its name is returned, and so is a
    backup whose delete failed. Each entry runs under its own `try`: an interrupt in one never
    stops the others, and the first one is returned for the caller to re-raise.
    """
    kept: list[str] = []
    interrupted: BaseException | None = None
    for entry in ledger:
        backup = entry.backup
        if entry.stage < _atomic._Stage.LINKED or backup is None:
            continue
        try:
            if (
                committed
                or entry.stage is _atomic._Stage.RESTORED
                or _atomic._same_file(backup, entry.real)
            ):
                try:
                    os.unlink(backup)
                except FileNotFoundError:
                    pass
                except OSError:
                    kept.append(backup)
            else:
                kept.append(backup)
            entry.stage = _atomic._Stage.SETTLED
        except BaseException as exc:
            kept.append(backup)  # unknown whether it went: report it rather than lose it
            if interrupted is None:
                interrupted = exc
    return kept, interrupted
