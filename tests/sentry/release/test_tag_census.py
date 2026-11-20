"""AT-S7b: every `"<name>/vN"` literal in `src/decoy` is classified.

A new tag literal fails the build until it is a frozen format (a row in
`docs/release/frozen-surfaces.md`), a derivation label or an internal tag with a reason. The
three classes stay disjoint, and a map row or table entry with no literal in the source is stale
and fails too. The scan is an AST walk, so a tag in a comment or docstring is not a literal.
Known limit S7B-KL-1: f-string tags and tags outside Python files are not scanned.
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


def test_every_tag_literal_is_classified() -> None:
    frozen, labels, internal = t.classes()
    missing = t.unclassified(set(t.source_tags()), frozen, labels, internal)
    assert missing == set(), f"classify these tags (map row or INTERNAL_TAGS): {sorted(missing)}"


def test_the_three_classes_are_disjoint() -> None:
    assert t.overlaps(*t.classes()) == set()


def test_no_class_names_a_tag_the_source_lost() -> None:
    frozen, labels, internal = t.classes()
    stale = (frozen | labels | internal) - set(t.source_tags())
    assert stale == set(), f"no literal in src/decoy for: {sorted(stale)}"


def test_every_internal_tag_has_an_owner_and_a_reason() -> None:
    for tag, (owner, reason) in t.INTERNAL_TAGS.items():
        assert reason.strip(), tag
        assert owner in t.source_tags().get(tag, []), f"{tag} is not literal in {owner}"


def test_every_derivation_label_names_its_owner() -> None:
    for tag, owner in t.DERIVATION_LABELS.items():
        assert owner in t.source_tags().get(tag, []), f"{tag} is not literal in {owner}"


# Seeds: each must be reported, or the census misses that surface.
def test_seed_a_new_tag_literal_is_found() -> None:
    assert t.literals('x = "x.tag/v1"\n') == {"x.tag/v1"}
    assert t.literals("x = b'x.tag/v1'\n") == {"x.tag/v1"}
    assert t.unclassified({"x.tag/v1"}, set(), set(), set()) == {"x.tag/v1"}


@pytest.mark.parametrize("text", ['"""the x.tag/v1 doc"""\n', "# x.tag/v1\n", 'x = "a x.tag/v1"\n'])
def test_seed_prose_is_not_a_tag(text: str) -> None:
    assert t.literals(text) == set()


def test_seed_a_dropped_map_row_leaves_a_tag_unclassified() -> None:
    kept = "\n".join(
        ln
        for ln in t.MAP.read_text(encoding="utf-8").splitlines()
        if not (ln.startswith("|") and "`scan-set/v1`" in ln.split("|")[1])
    )
    labels, internal = set(t.DERIVATION_LABELS), set(t.INTERNAL_TAGS)
    missing = t.unclassified(set(t.source_tags()), t.map_tags(kept), labels, internal)
    assert missing == {"scan-set/v1"}


def test_seed_a_class_overlap_is_found() -> None:
    assert t.overlaps({"a/v1"}, {"a/v1"}, set()) == {"a/v1"}
    assert t.overlaps({"a/v1"}, set(), {"a/v1"}) == {"a/v1"}


def test_the_map_reader_reads_the_surface_cell_only() -> None:
    row = "| `a/v1` format | `b/v1` | `c/v1` | tests/x.py |\n"
    assert t.map_tags(row) == {"a/v1"}
