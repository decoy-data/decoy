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


def test_the_review_mark_is_kept() -> None:
    text = 'decoy 1\npipeline { seed 1 mask t from csv("a.csv") to csv("b.csv") { x : redact?  keep y ? } }\n'
    formatted = format_text(text)
    assert "    x : redact ?\n    keep y ?\n" in formatted
    assert format_text(formatted) == formatted


_HEAD = "decoy 1\npipeline {\n seed 1\n"
_TABLE = ' mask t from csv("a.csv") to csv("b.csv") {{\n{body}\n }}\n}}\n'


def _formatted(body: str, before: str = "") -> str:
    text = _HEAD + before + _TABLE.format(body=body)
    out = format_text(text)
    assert format_text(out) == out
    return out


def test_a_comment_inside_a_statement_stays_with_that_statement() -> None:
    assert "    keep a, b, c  # not pii\n    ssn : redact\n" in _formatted(
        " keep a,\n b, # not pii\n c\n ssn : redact"
    )
    assert "fpe(charset: digits) in n  # prod charset\n" in _formatted(
        " ssn : fpe(\n # prod charset\n charset: digits) in n\n email : redact"
    )


def test_a_comment_after_a_closing_brace_goes_to_that_block_s_opening_line() -> None:
    text = (
        _HEAD
        + ' mask t from csv("a.csv") to csv("b.csv") { a : redact } # t done\n'
        + " let h = hash in n\n"
        + ' mask u from csv("c.csv") to csv("d.csv") { b : redact } # u done\n}\n'
    )
    out = format_text(text)
    assert 'mask t from csv("a.csv") to csv("b.csv") {  # t done\n' in out
    assert 'mask u from csv("c.csv") to csv("d.csv") {  # u done\n' in out
    assert format_text(out) == out


def test_comments_in_settings_and_beside_a_budget_stay_there() -> None:
    before = (
        " settings {\n post_validation: true\n # more to come\n }\n"
        " subset {\n budget(max_total_rows: 10) # agreed with ops\n start t sample 1% by a\n }\n"
    )
    out = _formatted(" a : redact", before)
    assert "    post_validation: true\n    # more to come\n  }\n" in out
    assert "    budget(max_total_rows: 10)  # agreed with ops\n" in out


@pytest.mark.parametrize("separator", ["\x0c", "\x1c", "\x85", "\u2028"])
def test_only_a_newline_ends_a_line(separator: str) -> None:
    body = f" a : redact # x{separator}y\n b : redact\n c : redact\n\n d : redact\n e : redact"
    assert "    c : redact\n\n    d : redact\n" in _formatted(body)


def test_windows_line_endings_come_out_as_newlines() -> None:
    text = (_HEAD + _TABLE.format(body=" a : redact # note")).replace("\n", "\r\n")
    assert "\r" not in format_text(text)
    assert "    a : redact  # note\n" in format_text(text)


@pytest.mark.parametrize(
    "deep",
    [
        " x : faker(p, k: " + "[" * 600 + "]" * 600 + ")",
        " where " + "(" * 400 + "a == 1" + ")" * 400,
    ],
)
def test_deep_nesting_is_an_error_not_a_crash(deep: str) -> None:
    with pytest.raises(LangError) as caught:
        format_text(_HEAD + _TABLE.format(body=deep + "\n x : redact"))
    assert caught.value.diagnostics[0].code == "lang.nesting"


@pytest.mark.parametrize("dropped", [" ?", " deterministic"])
def test_a_printer_that_drops_something_is_caught_before_the_text_is_returned(
    dropped: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from decoy.lang import _print

    real = _print._treatment
    monkeypatch.setattr(
        _print, "_treatment", lambda treatment: real(treatment).replace(dropped, "")
    )
    real_row = _print._table_row
    monkeypatch.setattr(
        _print,
        "_table_row",
        lambda statement: (
            tuple(part.replace(dropped, "") for part in row)
            if isinstance(row := real_row(statement), tuple)
            else row.replace(dropped, "")
        ),
    )
    with pytest.raises(LangError) as caught:
        format_text(_HEAD + _TABLE.format(body=" x : faker(a) in n deterministic ?\n keep y ?"))
    assert caught.value.diagnostics[0].code == "lang.format"


def test_a_lost_comment_is_caught_before_the_text_is_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from decoy.lang import _format

    monkeypatch.setattr(_format, "_notes", lambda *_: _format.Notes())
    with pytest.raises(LangError) as caught:
        format_text(_HEAD + _TABLE.format(body=" x : redact # keep me"))
    assert caught.value.diagnostics[0].code == "lang.format"


def test_formatting_from_several_threads_at_once() -> None:
    from concurrent.futures import ThreadPoolExecutor

    tables = "".join(
        f' mask t{i} from csv("a{i}.csv") to csv("b{i}.csv") {{ # table {i}\n x : redact # col {i}\n }}\n'
        for i in range(60)
    )
    text = _HEAD + tables + "}\n"
    expected = format_text(text)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(format_text, [text] * 16))
    assert results == [expected] * 16
