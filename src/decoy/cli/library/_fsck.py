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
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from decoy_engine import records

from decoy.cli.library import _index, _refs
from decoy.cli.library._errors import RECORD_INVALID, LibraryError
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
    record_digest,
)
from decoy.cli.library._store import (
    MAX_LAYOUT_BYTES,
    MAX_RECORD_BYTES,
    Library,
    open_library,
)

__all__ = ["Action", "Finding", "FsckReport", "check", "repair"]

Level = Literal["finding", "warning", "note"]
STALE_TEMP_SECONDS = 3600  # the git `gc.pruneExpire` idea, scaled to a write's lifetime
# Job logs are read through the one small-file reader too; a log is one run's value-free events.
_MAX_LOG_BYTES = 64 * 1024 * 1024
_SUFFIX = ".json"
_POSIX = sys.platform != "win32"
_CORRUPT_CODES = frozenset({"object_corrupt", "object_name_invalid"})


@dataclass(frozen=True)
class Finding:
    level: Level
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

    def add(self, level: Level, code: str, path_or_id: Path | str) -> None:
        target = path_or_id if isinstance(path_or_id, str) else self.rel(path_or_id)
        self.items.append(Finding(level, code, target))

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def folder(self, path: Path) -> bool:
        """True when `path` is a real folder to walk; a link or non-folder is a finding."""
        found = kind_of(self.root, path)
        if found is None:
            return False
        if found != "dir":
            self.add("finding", "path_linked", path)
            return False
        return True

    def listing(self, path: Path) -> list[Entry]:
        if not self.folder(path):
            return []
        return walk_tree(self.root, path)

    def layout_newer(self) -> bool:
        data = read_capped(self.root, self.lib / LAYOUT_FILE, MAX_LAYOUT_BYTES)
        if data is None:
            return False
        found: object = None
        with contextlib.suppress(ValueError):
            found = json.loads(data)
        version = found.get("layout") if isinstance(found, dict) else None
        if version == LAYOUT_VERSION and not isinstance(version, bool):
            return False
        self.add("finding", "layout_newer", self.lib / LAYOUT_FILE)
        return True

    def objects_and_links(self) -> None:
        links: list[tuple[str, str]] = []
        objects = self.lib / OBJECTS
        if not self.folder(objects):
            return
        for path, record_id, entry in _object_files(self.root, objects):
            if entry.kind == "link":
                self.add("finding", "path_linked", path)
                continue
            if record_id is None:
                self.add("finding", "object_name_invalid", path)
                self.inodes[self.rel(path)] = entry.inode
                continue
            self.objects += 1
            self.present.add(record_id)
            decoded: object = None
            code: str | None = None
            try:
                decoded = self.library.get(record_id)
            except LibraryError as exc:
                code = exc.code
            if code is not None:
                bad = "payload_invalid" if code == RECORD_INVALID else "object_corrupt"
                self.add("finding", bad, path)
                self.inodes[self.rel(path)] = entry.inode
            elif isinstance(decoded, records.RecordNeedsNewer):
                self.add("warning", "needs_newer", path)
            else:
                self.indexable.add(record_id)
                raw = getattr(decoded, "raw", {})
                links += [(record_id, str(link.get("id"))) for link in raw.get("links") or ()]
        for src, dst in links:
            if dst not in self.present:
                self.add("warning", "link_dangling", src)

    def refs(self) -> None:
        refs_dir = self.lib / REFS
        if not self.folder(refs_dir):
            return
        for entry, record_id in _refs.iter_refs(self.root, refs_dir):
            if entry.kind == "link":
                self.add("finding", "path_linked", entry.path)
            elif record_id is None:
                self.add("finding", "ref_corrupt", entry.path)
                self.dangling_refs.append(entry)
            elif record_id not in self.present:
                self.add("finding", "ref_dangling", entry.path)
                self.dangling_refs.append(entry)

    def index(self) -> None:
        path = self.lib / INDEX_FILE
        if kind_of(self.root, path) is None:
            if self.present:
                self.add("finding", "index_missing", path)
            return
        found = _indexed_ids(path)
        if found is None:
            self.add("finding", "index_corrupt", path)
            return
        version, ids = found
        if version != _index.SCHEMA_VERSION or (self.indexable - ids) or (ids - self.present):
            self.add("finding", "index_stale", path)

    def temps(self) -> None:
        tmp = self.lib / TMP
        if not self.folder(tmp):
            return
        for entry in entries(self.root, tmp) or []:
            if entry.kind == "file" and self.now - entry.mtime > STALE_TEMP_SECONDS:
                self.add("finding", "temp_stale", entry.path)
                self.inodes[self.rel(entry.path)] = entry.inode

    def modes(self) -> None:
        if not _POSIX:
            return
        private = [self.lib / INDEX_FILE, self.lib / TMP, self.root / SCRATCH, self.root / LOGS]
        advisory = [self.lib / OBJECTS, self.lib / REFS]
        classes: tuple[tuple[Level, list[Path]], ...] = (("finding", private), ("note", advisory))
        for level, paths in classes:
            for path in paths:
                for entry in _mode_entries(self.root, path):
                    if entry.mode & 0o077:
                        self.add(level, "mode_open", entry.path)

    def logs(self) -> None:
        for entry in self.listing(self.root / LOGS):
            if entry.kind != "file" or not entry.name.endswith(".jsonl"):
                continue
            if entry.path.parent != self.root / LOGS:
                continue
            data = read_capped(self.root, entry.path, _MAX_LOG_BYTES) or b""
            log = None
            with contextlib.suppress(records.RecordError):
                log = records.read_job_log(data)
            if log is None:
                self.add("finding", "log_header_invalid", entry.path)
                continue
            if log.bad_lines:
                self.add("finding", "log_bad_line", entry.path)
            if log.truncated_tail:
                self.add("warning", "log_truncated", entry.path)


def _object_files(root: Path, objects: Path) -> Iterator[tuple[Path, str | None, Entry]]:
    """Every entry under `objects/`, with its record id, or None for a name that is not one.

    A linked fan folder or object is yielded as a `link` entry and never entered.
    """
    for fan in entries(root, objects) or []:
        if fan.kind != "dir":
            yield fan.path, None, fan
            continue
        for item in entries(root, fan.path) or []:
            stem = item.name[: -len(_SUFFIX)] if item.name.endswith(_SUFFIX) else ""
            candidate = f"sha256:{fan.name}{stem}"
            ok = item.kind == "file" and record_digest(candidate) is not None
            yield item.path, candidate if ok else None, item


def _mode_entries(root: Path, path: Path) -> list[Entry]:
    """`path` and, for a real folder, everything below it; nothing through a link."""
    found = kind_of(root, path)
    if found is None or found == "link":
        return []
    if found == "dir":
        return walk_tree(root, path)
    info = os.lstat(path)
    return [Entry(path.name, path, found, (0, 0), 0, 0.0, stat.S_IMODE(info.st_mode))]


def _indexed_ids(path: Path) -> tuple[int, set[str]] | None:
    """The index's schema version and ids, read-only; None when it is not a readable index."""
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
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


def _quarantine(root: Path, source: Path, inode: tuple[int, int] | None) -> None:
    """Copy `source` into `quarantine/` (atomic, create-once), then remove it."""
    lib = root / LIBRARY
    data = read_capped(root, source, MAX_RECORD_BYTES)
    if data is None:
        return
    folder = lib / QUARANTINE
    ensure_private_dir(root, folder)
    base = source.parent.name + source.name if source.parent.name != OBJECTS else "stray"
    if record_digest(f"sha256:{base[: -len(_SUFFIX)]}") is None:
        base = "stray"
    for n in range(1000):
        name = base if n == 0 else f"{base}.{n}"
        if (
            write_once(root, folder, name, data, tmp_dir=lib / TMP)
            or read_capped(root, folder / name, MAX_RECORD_BYTES) == data
        ):
            remove_file(root, source, inode=inode)
            return


def repair(
    root: Path,
    *,
    probe: Callable[[Path], str | None] | None = None,
    now: float | None = None,
) -> tuple[tuple[Action, ...], FsckReport]:
    """Apply the repairs plan 4.10 allows; return them and the report after them.

    Nothing under a linked folder is repaired: the walk never listed it.
    """
    before = check(root, now=now)
    linked = {f.target for f in before.items if f.code == "path_linked"}
    lib = root / LIBRARY
    if any(f.code == "layout_newer" for f in before.items) or LIBRARY in linked:
        return (), before
    if kind_of(root, lib) != "dir":
        return (), before
    tmp_ok = f"{LIBRARY}/{TMP}" not in linked
    if tmp_ok:
        ensure_private_dir(root, lib / TMP)
    actions: list[Action] = []
    for f in before.items:
        if f.code in _CORRUPT_CODES and tmp_ok:
            _quarantine(root, root / f.target, before.inodes.get(f.target))
            actions.append(Action("object_quarantined", f.target))
        elif f.code == "temp_stale":
            remove_file(root, root / f.target, inode=before.inodes.get(f.target))
            actions.append(Action("temp_deleted", f.target))
    library = open_library(root, probe=probe)
    if library.degraded is None:
        removed = _refs.remove_refs(library, list(before.dangling_refs))
        actions += [Action("ref_removed", p.relative_to(root).as_posix()) for p in removed]
        library.rebuild_index()
        actions.append(Action("index_rebuilt", f"{LIBRARY}/{INDEX_FILE}"))
    return tuple(actions), check(root, now=now)
