"""The locks two strict runs share when they publish to one vault or evidence file.

Pattern: the engine's `OutputDir.lock` (a `flock` on `.<leaf>.decoy-lock` in the leaf's folder,
never unlinked), taken once per destination in one sorted order before the pointer lock, so two
runs that share a file cannot deadlock. The lock is opened on the entry the writer really
replaces, so two aliases of one file share one lock. A holder fails the contender closed: it does
not wait, and a lock that cannot be taken refuses the run rather than letting it go unlocked.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from decoy._atomic import destination_entry


@dataclass(frozen=True)
class SideFile:
    """A vault or evidence file a run publishes. `follow_final` is the writer's link policy:
    `--evidence-out` follows a final symlink, `--vault` replaces it."""

    path: Path
    follow_final: bool


def resolved(entry: SideFile) -> Path | None:
    """The file the writer would replace, or None when its folder does not exist yet."""
    try:
        return destination_entry(entry.path, follow_final=entry.follow_final)
    except (OSError, ValueError):  # no folder yet, or a spelling no file system can hold
        return None


def hold_side_files(held: contextlib.ExitStack, entries: Iterable[SideFile]) -> bool:
    """Lock each destination on `held`. True when another run holds one, or one cannot be locked.

    A destination whose folder does not exist has no other publisher yet: nothing to lock.
    """
    from decoy_engine.fileaccess import FileRequest, FileRole, LockTimeout, LockUnavailable, current

    destinations = {path for entry in entries if (path := resolved(entry)) is not None}
    for path in sorted(destinations, key=str):
        request = FileRequest(FileRole.TARGET_OUTPUT, "write", str(path), "side_file")
        try:
            held.enter_context(current().output_dir(request).lock(0.0))
        except (LockTimeout, LockUnavailable, OSError):
            return True
    return False
