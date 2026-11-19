"""`format_text`: the canonical layout, with every comment kept."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from decoy.lang import LangError, format_text
from decoy.lang._lower import lower
from decoy.lang._parse import parse

_TWINS = sorted((Path(__file__).parent / "twins").glob("*.decoy"))
_SOURCE = """# Nightly export
# owner: data team
decoy 1
pipeline nightly {   # the one pipeline
  seed 42  # fixed

  # identity columns first
  mask customers from csv("c.csv") to csv("out/c.csv") {  # main table
    customer_id : hash in ids   # the key
    # contact details
    email : faker(person_email)
    phone : faker(person_phone)

    # everything else
    keep tier, signup_date
    # nothing after this
  }
  let h = hash in ids
  delivery(strict) # safe mode
  # end of pipeline
}
# trailing note
"""
_FORMATTED = """# Nightly export
# owner: data team
decoy 1

pipeline nightly {
  # the one pipeline
  seed 42  # fixed

  let h = hash in ids

  delivery(strict)  # safe mode

  # identity columns first
  mask customers from csv("c.csv") to csv("out/c.csv") {  # main table
    customer_id : hash in ids  # the key
    # contact details
    email : faker(person_email)
    phone : faker(person_phone)

    # everything else
    keep tier, signup_date
    # nothing after this
  }

  # end of pipeline
}
# trailing note
"""


def test_comments_stay_with_their_statements_and_one_blank_line_is_kept() -> None:
    assert format_text(_SOURCE) == _FORMATTED
    assert format_text(_FORMATTED) == _FORMATTED


@pytest.mark.parametrize("twin", _TWINS, ids=lambda path: path.stem)
def test_a_file_already_in_the_layout_is_unchanged(twin: Path) -> None:
    text = twin.read_text(encoding="utf-8")
    assert format_text(text) == text


def test_a_hash_inside_text_is_not_a_comment() -> None:
    text = (
        'decoy 1\npipeline { seed 1 mask t from csv("a#b.csv") to csv("c.csv") { x : redact } }\n'
    )
    assert '"a#b.csv"' in format_text(text)
    assert "#" not in format_text(text).replace('"a#b.csv"', "")


def test_text_that_does_not_parse_is_an_error_and_nothing_is_returned() -> None:
    with pytest.raises(LangError):
        format_text("decoy 1\npipeline { seed }\n")


def _with_comments(lines: list[str], picks: list[tuple[int, bool]]) -> tuple[str, list[str]]:
    """The lines with a numbered comment beside or above the picked ones."""
    out = list(lines)
    comments = []
    for number, (index, beside) in enumerate(sorted(set(picks), reverse=True)):
        comment = f"# note {number}"
        comments.append(comment)
        if beside:
            out[index] = f"{out[index]}  {comment}"
        else:
            out.insert(index, comment)
    return "\n".join(out) + "\n", comments


@settings(max_examples=120, deadline=None, derandomize=True)
@given(st.data())
def test_comments_anywhere_are_all_kept_and_the_program_is_unchanged(data: st.DataObject) -> None:
    twin = data.draw(st.sampled_from(_TWINS))
    lines = twin.read_text(encoding="utf-8").splitlines()
    picks = data.draw(
        st.lists(st.tuples(st.integers(0, len(lines) - 1), st.booleans()), max_size=8)
    )
    text, comments = _with_comments(lines, [(i, b and bool(lines[i].strip())) for i, b in picks])
    formatted = format_text(text)
    assert all(formatted.count(comment) == 1 for comment in comments)
    assert lower(parse(formatted))[0] == lower(parse(text))[0]
    assert format_text(formatted) == formatted
