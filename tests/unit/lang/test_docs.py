"""Every complete program in the language guides compiles."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from decoy.lang import compile_text

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
