"""One object name-to-id rule (review round 1 on #210, DESIGN 7).

`_paths.object_entries` is the one walk of `objects/` and `_paths.id_from_name` the one rule from
a fan folder and file name to a record id; the index, fsck and the store's prefix lookup all
use them, so they agree on what counts as a stored record (a linked object counts for none).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tests.unit.library._helpers import ROOT, envelope, object_path

from decoy.cli.io import DECOY_DIR
from decoy.cli.library import _fsck, _index, _paths, open_library

PACKAGE = ROOT / "src" / "decoy" / "cli" / "library"


def _local(_p: Path) -> None:
    return None


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / DECOY_DIR


@pytest.mark.skipif(os.name != "posix", reason="symlinks without privilege")
def test_a_linked_object_counts_as_a_record_for_no_reader(root: Path, tmp_path: Path) -> None:
    library = open_library(root, probe=_local)
    kept = library.put(envelope(0)).id
    planted = envelope(1)
    outside = tmp_path / "outside.json"
    path = object_path(root, planted.id)
    path.parent.mkdir(exist_ok=True)
    library.put(planted)
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    objects = root / "library" / "objects"
    assert _index.object_ids(root, objects) == {kept}
    report = _fsck.check(root)
    assert report.objects == 1
    assert library.resolve(planted.id[:16]) == ()
    assert library.resolve(kept[:16]) == (kept,)


def test_the_name_rule_round_trips() -> None:
    digest = envelope(3).id.removeprefix("sha256:")
    path = _paths.object_path(Path("objects"), digest)
    assert path.parent.name == digest[:2]
    assert _paths.id_from_name(path.parent.name, path.name) == f"sha256:{digest}"
    assert _paths.id_from_name("zz", path.name) is None
    assert _paths.id_from_name(path.parent.name, path.name[:-1]) is None


def test_the_object_suffix_and_the_id_spelling_live_in_paths_only() -> None:
    sources = {p.name: p.read_text(encoding="utf-8") for p in PACKAGE.glob("*.py")}
    assert "_paths.py" in sources
    suffix = {n for n, t in sources.items() if '".json"' in t}
    built = {n for n, t in sources.items() if 'f"sha256:{' in t or 'f"{ID_PREFIX}{' in t}
    assert suffix == {"_paths.py"}
    assert built <= {"_paths.py"}
