"""AT-S7b: every `"<name>/vN"` tag in `src/decoy` is a frozen format with a map row.

A new tag literal fails the build until `docs/release/frozen-surfaces.md` has a row for it, and a
row whose tag has left the source is stale and fails too. The scan is an AST walk over Python
files, so a tag in a comment or docstring is not a literal, plus a line scan of the shipped data
files. Known limit S7B-KL-1: tags built with f-strings or concatenation are not scanned.
"""

from __future__ import annotations

import pytest
from tests.sentry.release import _tags as t

# Known members the real scan must find, so a walk that returns nothing cannot pass.
KNOWN = {"decoy-ci/v1", "scan-set/v1", "decoy-project/v1"}
FLOOR = 7


def test_the_scan_finds_the_known_tags() -> None:
    found = set(t.source_tags())
    assert KNOWN <= found
    assert len(found) >= FLOOR


def test_every_tag_is_a_frozen_format_with_a_row() -> None:
    missing = t.unclassified(set(t.source_tags()), t.frozen_tags())
    assert missing == set(), f"add a frozen-surfaces row for: {sorted(missing)}"


def test_no_row_names_a_tag_the_source_lost() -> None:
    stale = t.frozen_tags() - set(t.source_tags())
    assert stale == set(), f"no tag in src/decoy for: {sorted(stale)}"


# Seeds: each must be reported, or the census misses that surface.
def test_seed_a_new_tag_literal_is_found() -> None:
    assert t.literals('x = "x.tag/v1"\n') == {"x.tag/v1"}
    assert t.literals("x = b'x.tag/v1'\n") == {"x.tag/v1"}
    assert t.unclassified({"x.tag/v1"}, set()) == {"x.tag/v1"}


@pytest.mark.parametrize("text", ['"""the x.tag/v1 doc"""\n', "# x.tag/v1\n", 'x = "a x.tag/v1"\n'])
def test_seed_prose_is_not_a_python_tag(text: str) -> None:
    assert t.literals(text) == set()


def test_seed_a_data_file_tag_is_found() -> None:
    assert t.data_tags("kind: y.tag/v1\n") == {"y.tag/v1"}
    assert t.data_tags('{"schema": "y.tag/v1"}\n') == {"y.tag/v1"}
    assert t.data_tags("url: https://example.test/api/v1/x\n") == set()
    assert t.data_tags("path: a/v1/b\n") == set()


def test_seed_a_shipped_data_file_tag_reaches_the_census(tmp_path) -> None:
    (tmp_path / "t.yaml").write_text("kind: y.tag/v1\n", encoding="utf-8")
    (tmp_path / "t.py").write_text('x = "x.tag/v1"\n', encoding="utf-8")
    assert set(t.source_tags(tmp_path)) == {"x.tag/v1", "y.tag/v1"}


def test_seed_a_dropped_map_row_leaves_a_tag_unclassified() -> None:
    kept = "\n".join(
        ln
        for ln in t.MAP.read_text(encoding="utf-8").splitlines()
        if not (ln.startswith("|") and "`scan-set/v1`" in ln.split("|")[1])
    )
    missing = t.unclassified(set(t.source_tags()), t.map_tags(kept))
    assert missing == {"scan-set/v1"}


def test_the_map_reader_reads_the_surface_cell_only() -> None:
    row = "| `a/v1` format | `b/v1` | `c/v1` | tests/x.py |\n"
    assert t.map_tags(row) == {"a/v1"}
