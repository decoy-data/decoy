"""Named refs (plan 4.5, 4.8; L1b.3).

A ref is git's named ref: a small file `library/refs/<kind>/<name>` holding one record id and a
newline. It is replaced in one step through `_atomic` (`REPLACE`, which retries a held-open
target on Windows), so a reader sees the old id or the new one. Refs are the roots prune keeps.

Every ref update runs under the library lock, `_index.locked` (`BEGIN IMMEDIATE` on
`library/index.sqlite`, pre-created 0600; the one open and lock mechanism the index uses too).
A waiter gives up with `library_busy` and never overwrites; a lock that cannot be taken, or a
library in degraded mode (a network filesystem, plan 4.8), is `library_lock_unavailable`. The
target's existence is checked under the lock, so a later prune (which takes the same lock)
cannot remove it in between.

`latest` is virtual and computed from the index (`Library.latest`); it is not a stored ref.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from decoy_engine import records

from decoy.cli.library import _index
from decoy.cli.library._errors import (
    LIBRARY_LOCK_UNAVAILABLE,
    LIBRARY_PATH_UNSAFE,
    RECORD_CORRUPT,
    REF_NAME_INVALID,
    REF_NAME_RESERVED,
    LibraryError,
)
from decoy.cli.library._fs import (
    Entry,
    ensure_private_dir,
    entries,
    read_capped,
    remove_file,
    replace_file,
)
from decoy.cli.library._paths import REFS, record_digest

if TYPE_CHECKING:
    from decoy.cli.library._store import Library

__all__ = ["iter_refs", "read_ref", "remove_refs", "set_ref"]

# "sha256:" + 64 hex + a newline is 72 bytes; the rest is slack for a CRLF or editor newline.
_MAX_REF_BYTES = 128
# One-part names that are a scope for two-part refs (plan 4.5: `scan-set/baseline/<slug>`); as a
# file they would collide with that folder.
_RESERVED_NAMES = frozenset({"baseline"})
# One name segment (plan 4.5); a name may hold two, `<scope>/<name>`, for a pipeline scope.
_SEGMENT = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_MAX_SEGMENTS = 2


def _ref_parts(kind: str, name: str) -> tuple[str, ...]:
    """The path parts under `refs/`; `ref_name_invalid` for anything outside the grammar and
    `ref_name_reserved` for a one-part name that is a scope."""
    kinds = {spec.kind for spec in records.registered_kinds()}
    parts = name.split("/")
    ok = (
        kind in kinds
        and len(parts) <= _MAX_SEGMENTS
        and all(_SEGMENT.fullmatch(part) for part in parts)
    )
    if not ok:
        raise LibraryError(REF_NAME_INVALID)
    if len(parts) == 1 and parts[0] in _RESERVED_NAMES:
        raise LibraryError(REF_NAME_RESERVED)
    return (kind, *parts)


def set_ref(library: Library, kind: str, name: str, record_id: str) -> None:
    """Point the ref at `record_id`, which must be stored. Raises `LibraryError`:
    `ref_name_invalid`, `ref_name_reserved`, `record_not_found`, `record_corrupt`, `library_busy`,
    `library_lock_unavailable` or `library_write_failed`."""
    parts = _ref_parts(kind, name)
    if library.degraded is not None:
        raise LibraryError(LIBRARY_LOCK_UNAVAILABLE)  # a remote or unlockable library (plan 4.8)
    library.prepare()
    with _index.locked(library.library_dir):
        library.get(record_id)  # exists and is the record its id names
        folder = library.library_dir / REFS
        ensure_private_dir(library.root, folder)
        for part in parts[:-1]:
            folder = folder / part
            ensure_private_dir(library.root, folder)
        replace_file(
            library.root, folder, parts[-1], f"{record_id}\n".encode(), tmp_dir=library.tmp_dir
        )


def read_ref(library: Library, kind: str, name: str) -> str | None:
    """The id the ref holds, or None when it is not set. A ref file is replaced in one step, so
    it is read without the lock. A file that holds no record id is `record_corrupt`."""
    path = library.library_dir / REFS
    for part in _ref_parts(kind, name):
        path = path / part
    data = read_capped(library.root, path, _MAX_REF_BYTES)
    if data is None:
        return None
    text = parse_ref(data)
    if text is None:
        raise LibraryError(RECORD_CORRUPT)
    return text


def parse_ref(data: bytes) -> str | None:
    """The record id a ref file's bytes hold, or None. A leading U+FEFF (an editor's BOM) and
    surrounding whitespace are not part of the id."""
    text = data.decode("utf-8", errors="replace").strip().lstrip("\ufeff").strip()
    return text if record_digest(text) is not None else None


def ref_target(root: Path, path: Path) -> tuple[bool, str | None]:
    """(read, id): whether the ref file could be read, and the id it holds when it holds one.
    An unreadable, oversized or linked ref file is (False, None): it is never treated as one
    that points nowhere."""
    data: bytes | None = None
    try:
        data = read_capped(root, path, _MAX_REF_BYTES)
    except LibraryError:
        return False, None
    if data is None:
        return False, None
    return True, parse_ref(data)


def iter_refs(root: Path, refs_dir: Path) -> Iterator[tuple[Entry, bool, str | None]]:
    """Every entry under `refs_dir` that is not a real folder: (entry, read, id).

    Never descends through a link: a linked kind folder or ref is yielded as a `link` entry,
    unread, for fsck to report. A folder that cannot be listed is yielded as itself, unread.
    `library_path_unsafe` when `refs_dir` itself is linked.
    """
    pending = [refs_dir]
    while pending:
        folder = pending.pop(0)
        try:
            found = entries(root, folder) or []
        except LibraryError as exc:
            if exc.code == LIBRARY_PATH_UNSAFE and folder == refs_dir:
                raise
            info = _folder_entry(folder)
            if info is not None:
                yield info, False, None
            continue
        for entry in found:
            if entry.kind == "dir":
                pending.append(entry.path)
            elif entry.kind == "file":
                read, target = ref_target(root, entry.path)
                yield entry, read, target
            else:
                yield entry, False, None


def _folder_entry(folder: Path) -> Entry | None:
    try:
        info = os.lstat(folder)
    except OSError:
        return None
    return Entry(folder.name, folder, "dir", (info.st_dev, info.st_ino), 0, 0.0, 0)


def remove_refs(library: Library, entries_: list[Entry]) -> list[Path]:
    """Remove the given ref files under the library lock (fsck --repair, plan 4.10), each only
    when it is read again, holds a record id and that record is not stored. Returns the ones
    removed; a ref set meanwhile, one that cannot be read, and an entry replaced since fsck
    judged it (another inode) are kept."""
    removed: list[Path] = []
    if not entries_:
        return removed
    with _index.locked(library.library_dir):
        for entry in entries_:
            read, target = ref_target(library.root, entry.path)
            if not read or target is None or library.has(target):
                continue
            if remove_file(library.root, entry.path, inode=entry.inode):
                removed.append(entry.path)
    return removed
