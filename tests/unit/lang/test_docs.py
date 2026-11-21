"""Every complete program in the language guides compiles."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from decoy.lang import CODES, LangError, compile_text

_GUIDES = Path(__file__).resolve().parents[3] / "docs" / "guides" / "decoy-language"
_BLOCK = re.compile(r"```decoy\n(.*?)```", re.DOTALL)
_PROGRAMS = [
    (path.name, index, block)
    for path in sorted(_GUIDES.glob("*.md"))
    for index, block in enumerate(_BLOCK.findall(path.read_text(encoding="utf-8")))
]


def test_the_guides_hold_programs() -> None:
    assert len(_PROGRAMS) >= 5


@pytest.mark.parametrize(("page", "index", "program"), _PROGRAMS, ids=lambda item: str(item)[:24])
def test_a_program_in_a_guide_compiles(page: str, index: int, program: str) -> None:
    assert compile_text(program).config["version"] == 2


def test_the_error_page_lists_every_code_in_the_registry() -> None:
    # The registry is the one list of codes (`tests/unit/lang/test_codes.py` keeps the source
    # to it), so the page is checked against it and not against a scan of the source.
    listed = set(re.findall(r"`(lang\.[a-z_]+)`", (_GUIDES / "07-errors.md").read_text("utf-8")))
    assert set(CODES) - listed == set()
    assert listed - set(CODES) == set()


# A snippet that is not a whole program: the lines of a pipeline, or of one masked table.
_WRAP = {
    "decoy-pipeline": "decoy 1\npipeline {{\n  seed 1\n{body}\n}}\n",
    "decoy-mask": (
        'decoy 1\npipeline {{\n  seed 1\n  mask t from csv("a.csv", header: true) to csv("b.csv") {{\n{body}\n  }}\n}}\n'
    ),
}
_SNIPPET = re.compile(r"```(decoy-pipeline|decoy-mask)\n(.*?)```", re.DOTALL)
_SNIPPETS = [
    (path.name, index, _WRAP[kind].format(body=body))
    for path in sorted(_GUIDES.glob("*.md"))
    for index, (kind, body) in enumerate(_SNIPPET.findall(path.read_text(encoding="utf-8")))
]


def test_the_guides_hold_snippets() -> None:
    assert len(_SNIPPETS) >= 6


@pytest.mark.parametrize(("page", "index", "program"), _SNIPPETS, ids=lambda item: str(item)[:24])
def test_a_snippet_in_a_guide_is_valid_once_wrapped(page: str, index: int, program: str) -> None:
    # The review mark is shown on purpose in one snippet; it is the only problem allowed.
    try:
        compile_text(program)
    except LangError as error:
        assert {problem.code for problem in error.diagnostics} == {"lang.unreviewed"}
