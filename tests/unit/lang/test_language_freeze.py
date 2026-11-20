"""The language is a frozen 1.0 surface: grammar, `lang.*` codes and supported versions.

Rule (docs/release/frozen-surfaces.md): a program that compiles under `version 1` compiles to the
same config in every 1.x release; a new construct may only take a place where today's grammar
gives a syntax error; a code is never renamed, removed or reused. The twins and the round-trip
tests pin what programs mean; this file pins the three things a program cannot show.
"""

from __future__ import annotations

import json

from tests.unit.lang.surface import FIXTURE, surface

_HOW = "run `python -m tests.unit.lang.surface`, review the diff, and record the change in CHANGELOG.md"


def _frozen() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_the_grammar_text_is_the_frozen_one() -> None:
    assert surface()["grammar_sha256"] == _frozen()["grammar_sha256"], (
        f"the grammar changed; if the change only adds a construct where a syntax error was, {_HOW}"
    )


def test_no_code_is_removed_or_renamed() -> None:
    now, frozen = set(surface()["codes"]), set(_frozen()["codes"])
    assert frozen - now == set(), "a `lang.*` code was removed or renamed"


def test_a_new_code_is_recorded_in_the_fixture() -> None:
    assert set(surface()["codes"]) == set(_frozen()["codes"]), f"a code was added: {_HOW}"


def test_supported_versions_only_grow() -> None:
    assert set(_frozen()["supported_versions"]) <= set(surface()["supported_versions"])
    assert "1" in surface()["supported_versions"]


def test_a_renamed_code_is_seen() -> None:
    renamed = (set(surface()["codes"]) - {"lang.unreviewed"}) | {"lang.reviewed"}
    assert set(_frozen()["codes"]) - renamed == {"lang.unreviewed"}
