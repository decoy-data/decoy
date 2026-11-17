"""Scratch review fixes (review round 1 on #214).

V1 1: `delete_scratch` never follows a linked `scratch/` (or a link inside it) out of the
scratch area: with `.decoy/scratch` linked to `library/`, deleting `scratch/objects` used to
delete every record. All of it goes through `cli/library/_fs.py`; each cell plants the link and
proves nothing outside changed.

DESIGN 2: a library at any `--library DIR` gets `DIR/.gitignore` and `DIR/.gitattributes` once,
only when absent, from the one writer `decoy.cli.io` owns, and `prepare()` warnings reach the
allocation's caller.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tests.unit.library._helpers import INVOCATION, envelope

from decoy.cli.io import DECOY_DIR
from decoy.cli.library import LibraryError, open_library
from decoy.cli.library._errors import LIBRARY_PATH_UNSAFE

posix_only = pytest.mark.skipif(os.name != "posix", reason="symlinks without privilege")


def _local(_p: Path) -> None:
    return None


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "proj" / DECOY_DIR
    root.parent.mkdir()
    return root


def _snapshot(folder: Path) -> dict[str, bytes | None]:
    return {
        p.relative_to(folder).as_posix(): (p.read_bytes() if p.is_file() else None)
        for p in sorted(folder.rglob("*"))
    }


@posix_only
def test_a_scratch_linked_to_the_library_keeps_every_record(root: Path) -> None:
    library = open_library(root, probe=_local)
    ids = [library.put(envelope(n)).id for n in range(3)]
    before = _snapshot(root / "library")
    (root / "scratch").symlink_to(root / "library", target_is_directory=True)
    with pytest.raises(LibraryError) as caught:
        library.delete_scratch(root / "scratch" / "objects")
    assert caught.value.code == LIBRARY_PATH_UNSAFE
    assert _snapshot(root / "library") == before
    assert [open_library(root, probe=_local).get(i).id for i in ids] == ids


@posix_only
def test_a_scratch_linked_outside_keeps_the_outside_folder(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    (outside / "job").mkdir(parents=True)
    (outside / "job" / "rows.csv").write_bytes(b"the user's rows")
    before = _snapshot(outside)
    library = open_library(root, probe=_local)
    library.prepare()
    (root / "scratch").symlink_to(outside, target_is_directory=True)
    with pytest.raises(LibraryError) as caught:
        library.delete_scratch(root / "scratch" / "job")
    assert caught.value.code == LIBRARY_PATH_UNSAFE
    assert _snapshot(outside) == before


@posix_only
def test_a_link_inside_an_allocation_is_removed_and_never_entered(
    root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.csv").write_bytes(b"the user's rows")
    before = _snapshot(outside)
    library = open_library(root, probe=_local)
    with library.scratch("staging", INVOCATION) as alloc:
        alloc.write("part.csv", b"a,b\n")
        (alloc.path / "out").symlink_to(outside, target_is_directory=True)
        held = alloc.path
    assert not os.path.lexists(held)
    assert _snapshot(outside) == before


@posix_only
def test_a_linked_scratch_is_refused_before_an_allocation(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    library = open_library(root, probe=_local)
    library.prepare()
    (root / "scratch").symlink_to(outside, target_is_directory=True)
    with pytest.raises(LibraryError), library.scratch("staging", INVOCATION):
        pytest.fail("the owner's block ran on a linked scratch/")
    assert list(outside.iterdir()) == []


def test_a_library_dir_gets_its_git_files_once(tmp_path: Path) -> None:
    from decoy.cli.io import DECOY_DIR_GITIGNORE  # exported for every library root

    folder = tmp_path / "records"
    open_library(folder, probe=_local).put(envelope(0))
    assert (folder / ".gitignore").read_text(encoding="utf-8") == DECOY_DIR_GITIGNORE
    assert (folder / ".gitattributes").is_file()


def test_an_existing_gitignore_in_a_library_dir_is_kept(tmp_path: Path) -> None:
    folder = tmp_path / "records"
    folder.mkdir()
    (folder / ".gitignore").write_text("mine\n", encoding="utf-8")
    open_library(folder, probe=_local).put(envelope(0))
    assert (folder / ".gitignore").read_text(encoding="utf-8") == "mine\n"


def test_prepare_warnings_reach_the_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from decoy.cli.io import _project

    def refuse(*_a: object, **_k: object) -> bool:
        raise _project.AtomicWriteError("atomic_write_failed")

    monkeypatch.setattr(_project, "_create_once", refuse)
    folder = tmp_path / "records"
    with open_library(folder, probe=_local).scratch("staging", INVOCATION) as alloc:
        codes = [w.code for w in alloc.warnings]
    assert codes and all(c == codes[0] for c in codes)
