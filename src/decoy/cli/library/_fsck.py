"""`decoy library fsck [--repair]`: check a library against its own rules (plan 4.10; L1c.2).

The shape is `git fsck`: read-only by default, every problem one line with a stable code and a
target relative to the library root, and a separate repair step that never deletes a valid
record. Checks:

- every object's id, by the one id rule (`Library.get` parses before hashing, so a CRLF copy
  passes), its envelope, and its payload against the read model (an opaque kind by id only);
- every ref points at a stored record; every link target exists (a dangling link is a warning,
  since prune may remove an unprotected target);
- the index matches the objects it can hold (read-only `mode=ro` open, never created here);
- no temp file under `library/tmp/` is older than an hour;
- POSIX modes: the index, `tmp/`, `scratch/` and `logs/` must be private (a finding); records
  and refs get an advisory note, since git checks them out 0644 and they hold no values (4.6);
- job log lines parse (`records.read_job_log`); a truncated last line is a warning.

`repair` copies each corrupt object into `library/quarantine/` through the atomic writer and only
then removes it (nothing is moved by a raw rename; G-ONE-ATOMIC-WRITER), deletes stale temp
files, removes refs to missing records under the library lock, and rebuilds the index. A library
whose `LAYOUT` this version does not write is reported and never repaired.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import stat
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from decoy_engine import records

from decoy.cli.library import _fsck_codes as C
from decoy.cli.library import _index, _refs
from decoy.cli.library._errors import (
    LIBRARY_FILE_TOO_LARGE,
    LIBRARY_PATH_UNSAFE,
    LIBRARY_READ_FAILED,
    RECORD_INVALID,
    LibraryError,
)
from decoy.cli.library._fs import (
    Entry,
    ensure_private_dir,
    entries,
    kind_of,
    read_capped,
    remove_file,
    walk_tree,
    write_once,
)
from decoy.cli.library._paths import (
    INDEX_FILE,
    LAYOUT_FILE,
    LAYOUT_VERSION,
    LIBRARY,
    LOGS,
    OBJECTS,
    QUARANTINE,
    REFS,
    SCRATCH,
    TMP,
    id_from_name,
    object_entries,
)
from decoy.cli.library._store import (
    MAX_LAYOUT_BYTES,
    MAX_RECORD_BYTES,
    Library,
    open_library,
)

__all__ = ["Action", "Finding", "FsckReport", "check", "repair"]

STALE_TEMP_SECONDS = 3600  # the git `gc.pruneExpire` idea, scaled to a write's lifetime
# Job logs are read through the one small-file reader too; a log is one run's value-free events.
_MAX_LOG_BYTES = 64 * 1024 * 1024
_POSIX = sys.platform != "win32"
# A `get` that could not read the file says nothing about its content: never quarantined.
_UNREADABLE_CODES = frozenset({LIBRARY_READ_FAILED, LIBRARY_FILE_TOO_LARGE, LIBRARY_PATH_UNSAFE})


@dataclass(frozen=True)
class Finding:
    level: C.Level
    code: str
    target: str  # relative to the library root, or a record id


@dataclass(frozen=True)
class Action:
    code: str
    target: str


@dataclass(frozen=True)
class FsckReport:
    items: tuple[Finding, ...]
    objects: int
    # What repair may act on, as fsck judged it: the inode of each target, so an entry replaced
    # since the check is left alone, and the ref entries to drop.
    inodes: Mapping[str, tuple[int, int]] = field(default_factory=dict, compare=False)
    dangling_refs: tuple[Entry, ...] = field(default=(), compare=False)

    @property
    def clean(self) -> bool:
        return not any(f.level == "finding" for f in self.items)


class _Walk:
    """One read-only pass over a library root. Every listing and read goes through `_fs`, so a
    linked folder is reported (`path_linked`) and never descended through."""

    def __init__(self, root: Path, now: float) -> None:
        self.root = root
        self.lib = root / LIBRARY
        self.now = now
        self.items: list[Finding] = []
        self.inodes: dict[str, tuple[int, int]] = {}
        self.library = Library(root)  # no open: fsck must not catch the index up first
        self.present: set[str] = set()
        self.indexable: set[str] = set()
        self.objects = 0
        self.dangling_refs: list[Entry] = []

    def add(self, kind: C.FsckCode, path_or_id: Path | str, entry: Entry | None = None) -> None:
        """Report one finding. `entry` is the regular file as judged now; only a finding whose
        descriptor allows a repair keeps it, and repair acts on nothing else."""
        target = path_or_id if isinstance(path_or_id, str) else self.rel(path_or_id)
        self.items.append(Finding(kind.level, kind.code, target))
        if kind.repair is None or entry is None:
            return
        self.inodes[target] = entry.inode
        if kind.repair == "remove_ref":
            self.dangling_refs.append(entry)

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def folder(self, path: Path) -> bool:
        """True when `path` is a real folder to walk; a link or non-folder is a finding."""
        found = kind_of(self.root, path)
        if found is None:
            return False
        if found != "dir":
            self.add(C.PATH_LINKED, path)
            return False
        return True

    def listing(self, path: Path) -> list[Entry]:
        if not self.folder(path):
            return []
        return walk_tree(self.root, path)

    def layout_newer(self) -> bool:
        """True when the walk must stop: a `LAYOUT` this version did not write, or one it
        cannot read. Either way nothing is repaired."""
        data: bytes | None = None
        try:
            data = read_capped(self.root, self.lib / LAYOUT_FILE, MAX_LAYOUT_BYTES)
        except LibraryError:
            self.add(C.LAYOUT_UNREADABLE, self.lib / LAYOUT_FILE)
            return True
        if data is None:
            return False
        found: object = None
        with contextlib.suppress(ValueError):
            found = json.loads(data)
        version = found.get("layout") if isinstance(found, dict) else None
        if version == LAYOUT_VERSION and not isinstance(version, bool):
            return False
        self.add(C.LAYOUT_NEWER, self.lib / LAYOUT_FILE)
        return True

    def objects_and_links(self) -> None:
        links: list[tuple[str, str]] = []
        objects = self.lib / OBJECTS
        if not self.folder(objects):
            return
        for found in object_entries(self.root, objects):
            path, record_id, entry = found.path, found.record_id, found.entry
            if entry is None:
                self.add(C.OBJECT_UNREADABLE, path)
                continue
            if entry.kind == "link":
                self.add(C.PATH_LINKED, path)
                continue
            if record_id is None:
                self.add(C.OBJECT_NAME_INVALID, path, entry if entry.kind == "file" else None)
                continue
            self.objects += 1
            self.present.add(record_id)
            decoded: object = None
            code: str | None = None
            try:
                decoded = self.library.get(record_id)
            except LibraryError as exc:
                code = exc.code
            if code in _UNREADABLE_CODES:
                self.add(C.OBJECT_UNREADABLE, path)
            elif code == RECORD_INVALID:
                self.add(C.PAYLOAD_INVALID, path)
            elif code is not None:
                self.add(C.OBJECT_CORRUPT, path, entry)
            elif isinstance(decoded, records.RecordNeedsNewer):
                self.add(C.NEEDS_NEWER, path)
            else:
                self.indexable.add(record_id)
                raw = getattr(decoded, "raw", {})
                links += [(record_id, str(link.get("id"))) for link in raw.get("links") or ()]
        for src, dst in links:
            if dst not in self.present:
                self.add(C.LINK_DANGLING, src)

    def refs(self) -> None:
        refs_dir = self.lib / REFS
        if not self.folder(refs_dir):
            return
        for entry, read, record_id in _refs.iter_refs(self.root, refs_dir):
            if entry.kind == "link":
                self.add(C.PATH_LINKED, entry.path)
            elif not read:
                self.add(C.REF_UNREADABLE, entry.path)
            elif record_id is None:
                self.add(C.REF_CORRUPT, entry.path)
            elif record_id not in self.present:
                self.add(C.REF_DANGLING, entry.path, entry)

    def index(self) -> None:
        path = self.lib / INDEX_FILE
        found_kind = kind_of(self.root, path)
        if found_kind is None:
            if self.present:
                self.add(C.INDEX_MISSING, path)
            return
        if found_kind != "file":
            self.add(C.INDEX_NOT_FILE, path)  # a FIFO would block the open
            return
        found = _indexed_ids(path)
        if found is None:
            self.add(C.INDEX_CORRUPT, path)
            return
        version, ids = found
        if version != _index.SCHEMA_VERSION or (self.indexable - ids) or (ids - self.present):
            self.add(C.INDEX_STALE, path)

    def temps(self) -> None:
        tmp = self.lib / TMP
        if not self.folder(tmp):
            return
        for entry in entries(self.root, tmp) or []:
            if entry.kind == "file" and self.now - entry.mtime > STALE_TEMP_SECONDS:
                self.add(C.TEMP_STALE, entry.path, entry)

    def modes(self) -> None:
        if not _POSIX:
            return
        private = [self.lib / INDEX_FILE, self.lib / TMP, self.root / SCRATCH, self.root / LOGS]
        advisory = [self.lib / OBJECTS, self.lib / REFS]
        classes = ((C.MODE_OPEN, private), (C.MODE_OPEN_ADVISORY, advisory))
        for kind, paths in classes:
            for path in paths:
                for entry in _mode_entries(self.root, path):
                    if entry.mode & 0o077:
                        self.add(kind, entry.path)

    def logs(self) -> None:
        try:
            found = self.listing(self.root / LOGS)
        except LibraryError:
            self.add(C.LOG_UNREADABLE, self.root / LOGS)
            return
        for entry in found:
            if entry.kind != "file" or not entry.name.endswith(".jsonl"):
                continue
            if entry.path.parent != self.root / LOGS:
                continue
            try:
                data = read_capped(self.root, entry.path, _MAX_LOG_BYTES) or b""
            except LibraryError:
                self.add(C.LOG_UNREADABLE, entry.path)
                continue
            log = None
            with contextlib.suppress(records.RecordError):
                log = records.read_job_log(data)
            if log is None:
                self.add(C.LOG_HEADER_INVALID, entry.path)
                continue
            if log.bad_lines:
                self.add(C.LOG_BAD_LINE, entry.path)
            if log.truncated_tail:
                self.add(C.LOG_TRUNCATED, entry.path)


def _mode_entries(root: Path, path: Path) -> list[Entry]:
    """`path` and, for a real folder, everything below it; nothing through a link."""
    found = kind_of(root, path)
    if found is None or found == "link":
        return []
    if found == "dir":
        return walk_tree(root, path, unreadable=[])  # unlistable folders are reported elsewhere
    info = os.lstat(path)
    return [Entry(path.name, path, found, (0, 0), 0, 0.0, stat.S_IMODE(info.st_mode))]


def _indexed_ids(path: Path) -> tuple[int, set[str]] | None:
    """The index's schema version and ids, read-only; None when it is not a readable index."""
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(f"{Path(os.path.abspath(path)).as_uri()}?mode=ro", uri=True)
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if version != _index.SCHEMA_VERSION:
            return version, set()
        return version, {r[0] for r in conn.execute("SELECT id FROM records")}
    except sqlite3.Error:
        return None
    finally:
        if conn is not None:
            conn.close()


def _report(walk: _Walk) -> FsckReport:
    return FsckReport(tuple(walk.items), walk.objects, walk.inodes, tuple(walk.dangling_refs))


def check(
    root: Path,
    *,
    probe: Callable[[Path], str | None] | None = None,
    now: float | None = None,
) -> FsckReport:
    """Every finding for the library at `root`; read-only. `probe` is accepted for symmetry
    with `repair` and unused: a check needs no lock."""
    del probe
    walk = _Walk(root, time.time() if now is None else now)
    if not walk.folder(walk.lib):
        return _report(walk)
    if not walk.layout_newer():
        walk.objects_and_links()
        walk.refs()
        walk.index()
        walk.temps()
        walk.modes()
        walk.logs()
    return _report(walk)


QuarantineOutcome = Literal["quarantined", "kept", "failed"]


def _still_corrupt(root: Path, source: Path) -> bool | None:
    """Read `source` again: True when it does not parse or its content is not the record its
    name says (the one id rule), False when it is that record, None when it cannot be read."""
    try:
        data = read_capped(root, source, MAX_RECORD_BYTES)
    except LibraryError:
        return None
    if data is None:
        return None
    expected = id_from_name(source.parent.name, source.name)
    if expected is None:
        return True  # a stray name: no record can live there
    parsed: object = None
    with contextlib.suppress(ValueError):
        parsed = json.loads(data)
    if not isinstance(parsed, dict):
        return True
    try:
        return bool(records.record_id(parsed) != expected)
    except (records.RecordError, TypeError, ValueError):
        return True


def _quarantine(root: Path, source: Path, inode: tuple[int, int] | None) -> QuarantineOutcome:
    """Copy `source` into `quarantine/` (atomic, create-once), then remove it; called under the
    library lock. A file that now reads as the record its name says is kept. Every failure is
    this entry's outcome, never an abort."""
    corrupt = _still_corrupt(root, source)
    if corrupt is None:
        return "failed"
    if not corrupt:
        return "kept"
    lib = root / LIBRARY
    try:
        data = read_capped(root, source, MAX_RECORD_BYTES)
        if data is None:
            return "failed"
        folder = lib / QUARANTINE
        ensure_private_dir(root, folder)
        named = id_from_name(source.parent.name, source.name)
        base = source.parent.name + source.name if named is not None else "stray"
        for n in range(1000):
            name = base if n == 0 else f"{base}.{n}"
            if (
                write_once(root, folder, name, data, tmp_dir=lib / TMP)
                or read_capped(root, folder / name, MAX_RECORD_BYTES) == data
            ):
                remove_file(root, source, inode=inode)
                break
    except LibraryError:
        return "failed"
    return "failed" if kind_of(root, source) is not None else "quarantined"


def repair(
    root: Path,
    *,
    probe: Callable[[Path], str | None] | None = None,
    now: float | None = None,
) -> tuple[tuple[Action, ...], FsckReport]:
    """Apply the repairs plan 4.10 allows; return them and the report after them.

    Nothing under a linked folder is repaired (the walk never listed it), and one entry that
    cannot be repaired is reported for itself while the rest goes on.
    """
    before = check(root, now=now)
    kinds = [(f, C.descriptor(f)) for f in before.items]
    linked = {f.target for f, kind in kinds if kind is C.PATH_LINKED}
    lib = root / LIBRARY
    if any(kind.blocks_repair for _f, kind in kinds) or LIBRARY in linked:
        return (), before
    if kind_of(root, lib) != "dir":
        return (), before
    tmp_ok = f"{LIBRARY}/{TMP}" not in linked
    if tmp_ok:
        ensure_private_dir(root, lib / TMP)
    actions: list[Action] = []
    candidates = [
        f for f, kind in kinds if kind.repair == "quarantine" and f.target in before.inodes
    ]
    if candidates and tmp_ok:
        actions += _quarantine_all(root, lib, candidates, before)
    for f, kind in kinds:
        if kind.repair == "delete_temp":
            try:
                remove_file(root, root / f.target, inode=before.inodes.get(f.target))
            except LibraryError:
                actions.append(Action(C.TEMP_DELETE_FAILED.code, f.target))
                continue
            actions.append(Action(C.TEMP_DELETED.code, f.target))
    library = open_library(root, probe=probe)
    if library.degraded is None:
        removed = _refs.remove_refs(library, list(before.dangling_refs))
        actions += [Action(C.REF_REMOVED.code, p.relative_to(root).as_posix()) for p in removed]
        library.rebuild_index()
        actions.append(Action(C.INDEX_REBUILT.code, f"{LIBRARY}/{INDEX_FILE}"))
    return tuple(actions), check(root, now=now)


def _quarantine_all(
    root: Path, lib: Path, candidates: list[Finding], before: FsckReport
) -> list[Action]:
    """Each candidate re-judged and moved under the library lock; no lock, no move."""
    actions: list[Action] = []
    try:
        with _index.locked(lib):
            for f in candidates:
                outcome = _quarantine(root, root / f.target, before.inodes.get(f.target))
                if outcome == "quarantined":
                    actions.append(Action(C.OBJECT_QUARANTINED.code, f.target))
                elif outcome == "failed":
                    actions.append(Action(C.QUARANTINE_FAILED.code, f.target))
    except LibraryError:
        actions += [Action(C.QUARANTINE_FAILED.code, f.target) for f in candidates]
    return actions
