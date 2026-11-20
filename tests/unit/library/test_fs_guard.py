"""`cli/library/_fs.py`: no read, write, replace, list or remove leaves the library root.

Each cell plants a link (or a `..` path) and proves the folder outside the root is unchanged and
the call is refused with `library_path_unsafe`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from decoy.cli.library import LibraryError, _fs
from decoy.cli.library._errors import LIBRARY_PATH_UNSAFE

pytestmark = pytest.mark.skipif(os.name != "posix", reason="symlinks without privilege")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "proj" / ".decoy"
    (root / "library" / "tmp").mkdir(parents=True)
    return root


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    folder = tmp_path / "outside"
    (folder / "sub").mkdir(parents=True)
    (folder / "keep").write_bytes(b"outside data")
    (folder / "sub" / "deep").write_bytes(b"more outside data")
    return folder


def _snapshot(folder: Path) -> dict[str, bytes | None]:
    return {
        p.relative_to(folder).as_posix(): (p.read_bytes() if p.is_file() else None)
        for p in sorted(folder.rglob("*"))
    }


def _refused(call: object, *args: object, **kw: object) -> None:
    with pytest.raises(LibraryError) as caught:
        call(*args, **kw)  # type: ignore[operator]
    assert caught.value.code == LIBRARY_PATH_UNSAFE
    assert "outside" not in str(caught.value)


def test_remove_file_through_a_linked_folder_is_refused(root: Path, outside: Path) -> None:
    before = _snapshot(outside)
    (root / "scratch").symlink_to(outside, target_is_directory=True)
    _refused(_fs.remove_file, root, root / "scratch" / "keep")
    assert _snapshot(outside) == before


def test_remove_tree_of_a_linked_folder_is_refused(root: Path, outside: Path) -> None:
    before = _snapshot(outside)
    (root / "scratch").symlink_to(outside, target_is_directory=True)
    _refused(_fs.remove_tree, root, root / "scratch")
    _refused(_fs.remove_tree, root, root / "scratch" / "sub")
    assert _snapshot(outside) == before


def test_remove_tree_unlinks_an_inner_link_and_never_enters_it(root: Path, outside: Path) -> None:
    before = _snapshot(outside)
    tree = root / "scratch" / "job"
    tree.mkdir(parents=True)
    (tree / "file").write_bytes(b"x")
    (tree / "out").symlink_to(outside, target_is_directory=True)
    assert _fs.remove_tree(root, root / "scratch") is True
    assert not (root / "scratch").exists()
    assert _snapshot(outside) == before


def test_a_write_into_a_linked_folder_is_refused(root: Path, outside: Path) -> None:
    before = _snapshot(outside)
    (root / "library" / "refs").symlink_to(outside, target_is_directory=True)
    tmp = root / "library" / "tmp"
    _refused(_fs.replace_file, root, root / "library" / "refs", "keep", b"id", tmp_dir=tmp)
    _refused(_fs.write_once, root, root / "library" / "refs" / "sub", "new", b"x", tmp_dir=tmp)
    _refused(_fs.ensure_private_dir, root, root / "library" / "refs" / "made")
    assert _snapshot(outside) == before


def test_a_read_through_a_linked_folder_is_refused(root: Path, outside: Path) -> None:
    (root / "library" / "refs").symlink_to(outside, target_is_directory=True)
    _refused(_fs.read_capped, root, root / "library" / "refs" / "sub" / "deep", 1024)
    _refused(_fs.entries, root, root / "library" / "refs" / "sub")


def test_a_path_that_climbs_out_is_refused(root: Path, outside: Path) -> None:
    before = _snapshot(outside)
    _refused(_fs.remove_file, root, root / ".." / ".." / "outside" / "keep")
    _refused(_fs.read_capped, root, outside / "keep", 1024)
    assert _snapshot(outside) == before


def test_remove_file_removes_a_link_not_its_target(root: Path, outside: Path) -> None:
    before = _snapshot(outside)
    link = root / "library" / "tmp" / "planted"
    link.symlink_to(outside / "keep")
    assert _fs.remove_file(root, link) is True
    assert not os.path.lexists(link) and _snapshot(outside) == before


def test_remove_file_leaves_an_entry_replaced_since_it_was_judged(root: Path) -> None:
    path = root / "library" / "tmp" / "old"
    path.write_bytes(b"a")
    judged = (os.lstat(path).st_dev, os.lstat(path).st_ino)
    os.link(path, root / "held")  # keeps the old inode alive, so it cannot be reused
    path.unlink()
    path.write_bytes(b"someone else's")
    assert (os.lstat(path).st_dev, os.lstat(path).st_ino) != judged
    assert _fs.remove_file(root, path, inode=judged) is False
    assert path.read_bytes() == b"someone else's"
