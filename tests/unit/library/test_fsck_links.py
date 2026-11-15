"""fsck never follows a linked library folder out of the root (review round 1 on #210, item 5).

Each cell plants a link from a library folder to a folder outside the root that holds a file
fsck would act on (an old temp, a corrupt object, a dangling ref), runs check and repair, and
proves the outside folder is byte-for-byte unchanged. The link itself is reported
(`path_linked`), never descended through. All of it goes through `cli/library/_fs.py`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from tests.unit.library._helpers import envelope, object_path

from decoy.cli.io import DECOY_DIR
from decoy.cli.library import _fsck, open_library

pytestmark = pytest.mark.skipif(os.name != "posix", reason="symlinks without privilege")


def _local(_p: Path) -> None:
    return None


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "proj" / DECOY_DIR
    root.parent.mkdir()
    library = open_library(root, probe=_local)
    library.put(envelope(0))
    return root


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    folder = tmp_path / "outside"
    folder.mkdir()
    return folder


def _snapshot(folder: Path) -> dict[str, bytes | None]:
    return {
        p.relative_to(folder).as_posix(): (p.read_bytes() if p.is_file() else None)
        for p in sorted(folder.rglob("*"))
    }


def _link(root: Path, rel: str, outside: Path) -> Path:
    """Move the library folder `rel` aside and put a link to `outside` in its place."""
    place = root / rel
    if place.exists():
        place.rename(place.with_name(place.name + ".moved"))
    place.symlink_to(outside, target_is_directory=True)
    return place


def _old(path: Path, data: bytes = b"partial") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    then = time.time() - 2 * 3600
    os.utime(path, (then, then))
    return path


def _findings(report: _fsck.FsckReport) -> set[tuple[str, str]]:
    return {(f.code, f.target) for f in report.items if f.level == "finding"}


def test_a_linked_tmp_folder_keeps_the_outside_file(root: Path, outside: Path) -> None:
    victim = _old(outside / ".x.decoy-1.tmp")
    before = _snapshot(outside)
    _link(root, "library/tmp", outside)
    report = _fsck.check(root)
    assert ("path_linked", "library/tmp") in _findings(report)
    assert not any(f.code == "temp_stale" for f in report.items)
    actions, _after = _fsck.repair(root, probe=_local)
    assert not any(a.code == "temp_deleted" for a in actions)
    assert victim.exists() and _snapshot(outside) == before


def test_a_linked_objects_folder_keeps_the_outside_object(root: Path, outside: Path) -> None:
    env = envelope(5)
    stored = object_path(Path("x"), env.id)  # only the fan and file names
    victim = outside / stored.parent.name / stored.name
    victim.parent.mkdir()
    victim.write_bytes(b"{not a record")
    before = _snapshot(outside)
    _link(root, "library/objects", outside)
    report = _fsck.check(root)
    assert ("path_linked", "library/objects") in _findings(report)
    assert not any(f.code == "object_corrupt" for f in report.items)
    actions, _after = _fsck.repair(root, probe=_local)
    assert not any(a.code == "object_quarantined" for a in actions)
    assert _snapshot(outside) == before
    assert not (root / "library" / "quarantine").exists()


def test_a_linked_fan_folder_is_reported_not_quarantined(root: Path, outside: Path) -> None:
    victim = outside / ("c" * 62 + ".json")
    victim.write_bytes(b"{not a record")
    before = _snapshot(outside)
    fan = root / "library" / "objects" / "cc"
    fan.symlink_to(outside, target_is_directory=True)
    report = _fsck.check(root)
    assert ("path_linked", "library/objects/cc") in _findings(report)
    actions, _after = _fsck.repair(root, probe=_local)  # must not raise
    assert not any(a.code == "object_quarantined" for a in actions)
    assert _snapshot(outside) == before


def test_a_linked_refs_folder_keeps_the_outside_ref(root: Path, outside: Path) -> None:
    victim = outside / "sample-run" / "gone"
    victim.parent.mkdir()
    victim.write_text(envelope(9).id + "\n", encoding="utf-8")
    before = _snapshot(outside)
    _link(root, "library/refs", outside)
    report = _fsck.check(root)
    assert ("path_linked", "library/refs") in _findings(report)
    assert not any(f.code == "ref_dangling" for f in report.items)
    actions, _after = _fsck.repair(root, probe=_local)
    assert not any(a.code == "ref_removed" for a in actions)
    assert victim.exists() and _snapshot(outside) == before


def test_a_linked_ref_kind_folder_keeps_the_outside_ref(root: Path, outside: Path) -> None:
    victim = outside / "gone"
    victim.write_text(envelope(9).id + "\n", encoding="utf-8")
    before = _snapshot(outside)
    refs = root / "library" / "refs"
    refs.mkdir()
    (refs / "sample-run").symlink_to(outside, target_is_directory=True)
    actions, _after = _fsck.repair(root, probe=_local)
    assert not any(a.code == "ref_removed" for a in actions)
    assert victim.exists() and _snapshot(outside) == before


def test_a_linked_library_folder_is_reported_and_never_repaired(
    tmp_path: Path, outside: Path
) -> None:
    """`.decoy/library` itself is a link: nothing under it is read as the library's own."""
    real = tmp_path / "elsewhere" / DECOY_DIR
    real.parent.mkdir()
    open_library(real, probe=_local).put(envelope(0))
    victim = _old(real / "library" / "tmp" / ".x.decoy-1.tmp")
    root = tmp_path / "proj2" / DECOY_DIR
    root.mkdir(parents=True)
    (root / "library").symlink_to(real / "library", target_is_directory=True)
    before = _snapshot(real)
    report = _fsck.check(root)
    assert ("path_linked", "library") in _findings(report)
    actions, _after = _fsck.repair(root, probe=_local)
    assert actions == ()
    assert victim.exists() and _snapshot(real) == before


def test_the_check_report_names_no_outside_path(root: Path, outside: Path) -> None:
    _old(outside / ".x.decoy-1.tmp")
    _link(root, "library/tmp", outside)
    report = _fsck.check(root)
    text = json.dumps([f.target for f in report.items])
    assert str(outside) not in text and "outside" not in text
