"""The locks two runs share when they publish to one vault or evidence file.

Pattern: the engine's `OutputDir.lock` (a `flock` on `.<leaf>.decoy-lock` in the leaf's folder,
never unlinked), taken once per destination in one sorted order before the pointer lock, so two
runs that share a file cannot deadlock. A holder fails the contender closed: it does not wait.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from pathlib import Path

from decoy.cli.io import _pointer
from decoy.cli.io._placement import _destination_key


def hold_side_files(held: contextlib.ExitStack, paths: Iterable[Path]) -> bool:
    """Lock each path on `held`, sorted by destination identity. True when another run holds one.

    A host with no lock, or a folder the lock cannot open, runs without it: the lock arbitrates
    between runs, it does not gate a run that has no contender it can see.
    """
    if not _pointer.pointer_supported():
        return False
    from decoy_engine.fileaccess import (
        FileRequest,
        FileRole,
        LockTimeout,
        LockUnavailable,
        current,
    )

    for path in sorted(set(paths), key=_destination_key):
        request = FileRequest(FileRole.TARGET_OUTPUT, "write", str(path), "side_file")
        try:
            held.enter_context(current().output_dir(request).lock(0.0))
        except LockTimeout:
            return True
        except (LockUnavailable, OSError):
            continue
    return False
