"""AT-1 (map, C1): every concrete path in the CODEMAP "Where Things Go" section exists.

The section is the one place that says where a new file goes. A path that stops existing fails
here, so the map cannot drift from the tree. Row titles are not pinned: a renamed or dropped row
does not fail, but a row kept twice does. Path grammar lives in
``map_paths`` (vendored from the engine's LAYOUT E2 commit ``66d0f879``); the engine's own tests
cover each grammar case, so this file checks the CLI's map and the one CLI-specific wiring.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.sentry.layout import map_paths, section

ROOT = Path(__file__).resolve().parents[3]
# `Goes in`, `File naming`, `Tests`, `Sentries and registries`; column 0 is the kind.
LAYOUT_COLUMNS = (1, 2, 3, 4)
LAYOUT_HEADING = "## Where Things Go"
HEADER = ("Kind", "Goes in", "File naming", "Tests", "Sentries and registries")
# Paths the map marks `(target)`. A new or misspelled target is red. None is open since C3
# created the layer files.
TARGETS: frozenset[str] = frozenset()
_TARGET = re.compile(r"`([^`]+)` \(target\)")


def _layout_text() -> str:
    return section((ROOT / "CODEMAP.md").read_text(encoding="utf-8"), LAYOUT_HEADING)


def _table() -> list[list[str]]:
    lines = [ln for ln in _layout_text().splitlines() if ln.startswith("|")]
    return [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]


def test_the_codemap_layout_table_has_the_five_named_columns() -> None:
    rows = _table()
    assert tuple(rows[0]) == HEADER
    assert all(len(r) == len(HEADER) for r in rows), "a row has a different number of cells"


def test_the_codemap_layout_section_names_each_kind_once() -> None:
    kinds = [r[0] for r in _table()[2:]]
    assert len(kinds) == len(set(kinds)), "a kind appears twice"


def test_the_codemap_target_paths_are_the_approved_ones() -> None:
    found = set(_TARGET.findall(_layout_text()))
    assert found == TARGETS, f"unapproved or missing (target) paths: {found ^ TARGETS}"


def test_every_path_in_the_codemap_layout_section_exists() -> None:
    missing = map_paths(_layout_text(), ROOT, LAYOUT_COLUMNS)
    assert not missing, f"CODEMAP 'Where Things Go' names paths that do not exist: {missing}"


def test_a_missing_concrete_path_in_the_section_is_red() -> None:
    seeded = _layout_text() + "\n| Probe | `src/decoy/nope/` | - | - | - |\n"
    assert map_paths(seeded, ROOT, LAYOUT_COLUMNS) == ["src/decoy/nope/ -> src/decoy/nope"]


def test_a_target_path_with_a_real_parent_is_green() -> None:
    seeded = "| Probe | `src/decoy/cli/newpkg/` (target) | - | - | - |\n"
    assert map_paths(seeded, ROOT, LAYOUT_COLUMNS) == []
