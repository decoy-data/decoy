"""The one QA writer: private, create-once, atomic file publication.

Every file the QA tooling writes goes through this module, so a tester record or a corpus item is
never half written, never world readable and never silently replaced. A sentry
(`tests/unit/qa/test_io_sentry.py`) rejects any other open-for-write in `scripts/qa`.

Why a hard link: `os.replace` alone overwrites an existing target. The finished, fsynced
temporary file is linked to the target instead, which is atomic and fails if the target exists,
so two writers racing on one id cannot both win and a killed writer never leaves an empty target.
An interruption at any point removes the temporary file, so a retry with the same id works.

Standard library only, and no private product module (`decoy._*`). Plan section 4 chose this small
helper on purpose: the product's own atomic writers are private, and making them public would
widen the frozen surface, so QA keeps its own copy of the few primitives it needs.
"""

from __future__ import annotations

import contextlib
import os
import stat
import tempfile
from collections.abc import Iterator
from pathlib import Path

PRIVATE_FILE = 0o600
PRIVATE_DIR = 0o700


class AlreadyPublished(FileExistsError):
    """The target exists. The message names the path only, never any content."""


class StagedFile:
    """A private temporary file next to its target, published at most once.

    The temporary file lives in the target's folder so the hard link stays on one filesystem and
    is atomic. Nothing appears at the target until `publish`.
    """

    def __init__(self, target: Path, fd: int, temp: Path) -> None:
        self.target = target
        self.path = temp
        self._fd: int | None = fd
        self._published = False

    def write(self, data: bytes) -> None:
        if self._fd is None:
            raise ValueError("the staged file is closed")
        view = memoryview(data)
        while view:
            view = view[os.write(self._fd, view) :]

    def close(self) -> None:
        if self._fd is not None:
            os.fsync(self._fd)
            os.close(self._fd)
            self._fd = None

    def publish(self) -> None:
        """Link the finished file to the target, then drop the temporary name.

        `os.link` is atomic and refuses an existing target, so the target either does not exist
        or is complete: there is no empty reservation for a killed process to leave behind. A
        kill after the link leaves the finished target plus a stray `.part` name, which is
        harmless.
        """
        self.close()
        if self._published:
            raise ValueError("the staged file was already published")
        exists = False
        try:
            os.link(self.path, self.target)
        except FileExistsError:
            exists = True
        if exists:  # raised outside the handler so the error carries no __context__
            raise AlreadyPublished(f"already exists: {self.target}")
        self._published = True
        with contextlib.suppress(FileNotFoundError):
            os.unlink(self.path)
        _fsync_dir(self.target.parent)

    def discard(self) -> None:
        self.close()
        if not self._published:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self.path)


def _fsync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ensure_parents(directory: Path) -> None:
    """Create each missing level as a private folder; refuse a symlinked parent."""
    missing = []
    probe = directory
    while not probe.exists() and not probe.is_symlink():
        missing.append(probe)
        probe = probe.parent
    # `probe` is the nearest level that exists. A symlink there could point anywhere.
    if probe.is_symlink() or not probe.is_dir():
        raise NotADirectoryError(f"refused: {probe} is not a real folder")
    for level in reversed(missing):
        make_private_dir(level)


@contextlib.contextmanager
def staged_private(target: Path) -> Iterator[StagedFile]:
    """Yield a `StagedFile` for `target`; remove the temporary file unless it was published."""
    target = Path(target)
    _ensure_parents(target.parent)
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".part", dir=target.parent)
    os.fchmod(fd, PRIVATE_FILE)
    staged = StagedFile(target, fd, Path(name))
    try:
        yield staged
    finally:
        staged.discard()


def publish_private_once(target: Path, data: bytes) -> None:
    """Write `data` to `target` as a 0600 file that did not exist before, atomically."""
    with staged_private(target) as staged:
        staged.write(data)
        staged.publish()


@contextlib.contextmanager
def private_scratch_dir() -> Iterator[Path]:
    """A 0700 temporary folder for tools that must write a file themselves (a DuckDB database)."""
    with tempfile.TemporaryDirectory(prefix="qa-scratch-") as name:
        os.chmod(name, PRIVATE_DIR)
        yield Path(name)


def make_private_dir(path: Path, mode: int = PRIVATE_DIR) -> None:
    """Create one directory level with exactly `mode`; the parent must already exist.

    A path that exists is accepted only when it is a real directory (not a symlink) owned by this
    user with exactly `mode`; anything else is refused, so a pre-planted folder cannot be reused.
    """
    path = Path(path)
    exists = False
    try:
        os.mkdir(path, mode)
    except FileExistsError:
        exists = True
    if not exists:
        os.chmod(path, mode)  # mkdir applies the umask; the caller asked for exact bits
        return
    info = os.lstat(path)
    same = (
        stat.S_ISDIR(info.st_mode)
        and info.st_uid == os.getuid()
        and stat.S_IMODE(info.st_mode) == mode
    )
    if not same:
        raise FileExistsError(f"refused: {path} exists with another type, owner or mode")


def open_private_capture(path: Path, *, inheritable: bool = False) -> int:
    """Create `path` once as a 0600 append-only file and return its fd (a symlink is refused).

    The fd is close-on-exec unless `inheritable` is set, for a launcher that hands it to a child.
    """
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW | os.O_APPEND
    flags |= getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags, PRIVATE_FILE)
    try:
        os.fchmod(fd, PRIVATE_FILE)  # the umask can strip the bits `os.open` asked for
        if stat.S_IMODE(os.fstat(fd).st_mode) != PRIVATE_FILE:
            raise PermissionError(f"refused: {path} is not mode 0600")
        os.set_inheritable(fd, inheritable)
    except BaseException:
        os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            os.unlink(path)
        raise
    return fd
