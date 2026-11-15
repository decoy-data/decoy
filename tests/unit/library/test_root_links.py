"""A linked `library/` folder or object file reaches nothing outside the root (#210 round 2, V1-A).

`Library._open` used `Path.is_dir()` and the index opened its SQLite file directly, so with
`.decoy/library -> outside/` an existing `outside/index.sqlite` was replaced by a fresh database;
`has` and `put`'s link check used `is_file()`, so an object file linked to an outside copy counted
as stored. Both now go through `cli/library/_fs.py`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tests.unit.library._helpers import envelope, object_path

from decoy.cli.io import DECOY_DIR
from decoy.cli.library import LibraryError, open_library
from decoy.cli.library._errors import LIBRARY_PATH_UNSAFE, RECORD_LINK_MISSING

pytestmark = pytest.mark.skipif(os.name != "posix", reason="symlinks without privilege")


def _local(_p: Path) -> None:
    return None


def test_a_linked_library_folder_never_touches_the_outside_index(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "index.sqlite").write_bytes(b"0123456789")
    root = tmp_path / "proj" / DECOY_DIR
    root.mkdir(parents=True)
    (root / "library").symlink_to(outside, target_is_directory=True)
    with pytest.raises(LibraryError) as caught:
        open_library(root, probe=_local)
    assert caught.value.code == LIBRARY_PATH_UNSAFE
    assert (outside / "index.sqlite").read_bytes() == b"0123456789"
    assert sorted(p.name for p in outside.iterdir()) == ["index.sqlite"]


def test_a_linked_object_file_is_not_stored(tmp_path: Path) -> None:
    root = tmp_path / "proj" / DECOY_DIR
    root.parent.mkdir()
    library = open_library(root, probe=_local)
    base = envelope(1)
    library.put(base)
    stored = object_path(root, base.id)
    outside = tmp_path / "copy.json"
    copy = stored.read_bytes()
    outside.write_bytes(copy)
    stored.unlink()
    stored.symlink_to(outside)
    assert library.has(base.id) is False
    with pytest.raises(LibraryError) as caught:
        library.put(envelope(2, links=[base.id]))
    assert caught.value.code == RECORD_LINK_MISSING
    assert outside.read_bytes() == copy
