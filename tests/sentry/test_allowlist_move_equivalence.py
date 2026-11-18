"""Temporary proof that moving each allowlist into its baseline JSON changed no value.

``allowlist-before.json`` is the decoded in-code allowlist of every moved sentry, taken before the
move. ``load_allowlist`` must return the same object afterwards. Deleted in C-G2, after which
``scripts/dev/ratchet_check.py`` against the merge base carries the guarantee.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.sentry._ratchet import load_allowlist

SNAPSHOT = json.loads((Path(__file__).parent / "allowlist-before.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("sentry_id", sorted(SNAPSHOT))
def test_loaded_allowlist_equals_the_snapshot_taken_before_the_move(sentry_id: str) -> None:
    assert load_allowlist(sentry_id) == SNAPSHOT[sentry_id]
