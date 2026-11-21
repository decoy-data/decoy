"""`print_program`: text the grammar reads back as the same program, and a fixed point."""

from __future__ import annotations

from pathlib import Path

import pytest

from decoy.lang import LangError
from decoy.lang._grammar import KEYWORD_TERMINALS
from decoy.lang._lower import COLUMN_SYNTAX, SETTING_STATEMENTS, lower
from decoy.lang._parse import parse
from decoy.lang._print import _SETTINGS, number, print_program, value

_TWINS = sorted((Path(__file__).parent / "twins").glob("*.decoy"))
_WORDS = sorted(word.lower() for word in KEYWORD_TERMINALS)
_PROGRAM = """decoy 1
pipeline {{
  seed 1
  expect leak_check(t.a{expect})
  mask t from csv("a.csv", header: true{connector}) to csv("b.csv") {{
    a : hash(k: 1{mask}) in ids
  }}
  generate g rows 2 to csv("g.csv") {{
    b = constant(1{generate})
  }}
}}
"""


def _reprinted(text: str) -> str:
    printed = print_program(parse(text))
    assert print_program(parse(printed)) == printed
    assert lower(parse(printed))[0] == lower(parse(text))[0]
    return printed


@pytest.mark.parametrize("twin", _TWINS, ids=lambda path: path.stem)
def test_a_twin_is_already_in_the_canonical_layout(twin: Path) -> None:
    text = twin.read_text(encoding="utf-8")
    assert print_program(parse(text)) == text


@pytest.mark.parametrize("word", _WORDS)
def test_a_word_of_the_language_as_an_option_key_reads_back(word: str) -> None:
    key = f"'{word}'"
    for place in ("expect", "connector", "mask", "generate"):
        if place == "mask" and word in COLUMN_SYNTAX:
            continue  # written with its own syntax, so refused as an option
        slots = dict.fromkeys(("expect", "connector", "mask", "generate"), "")
        slots[place] = f", {key}: 5"
        printed = _reprinted(_PROGRAM.format(**slots))
        assert f"{word}: 5" in printed or f"'{word}': 5" in printed


@pytest.mark.parametrize(
    "written",
    ["'First Name'", "'a.b'", "keep_all", "'keep'", "'in'", "'1st'", "'null'", "'mask'"],
)
def test_names_that_need_quotes_keep_them(written: str) -> None:
    text = _PROGRAM.format(expect="", connector="", mask="", generate="").replace(
        "a : hash(k: 1) in ids", f"{written} : redact"
    )
    assert f"    {written} : redact" in _reprinted(text.replace("t.a", "t.zz"))


@pytest.mark.parametrize(
    ("item", "written"),
    [
        (5, "5"),
        (-3, "-3"),
        (2.0, "2.0"),
        (1e-06, "0.000001"),
        (1e22, "10000000000000000000000.0"),
        (10**30, "1000000000000000000000000000000"),
        (True, "true"),
        ("digits", "digits"),
        ("true", '"true"'),
        ("in", '"in"'),
        ("1", '"1"'),
        ("", '""'),
        ("a b", '"a b"'),
        ('q"\\\n', '"q\\"\\\\\\n"'),
        ([], "[]"),
        ({}, "{}"),
        ({"a b": [1, "x"], "if": True}, '{"a b": [1, x], "if": true}'),
    ],
)
def test_values_are_written_so_they_read_back_with_the_same_type(
    item: object, written: str
) -> None:
    assert value(item) == written
    text = _PROGRAM.format(expect="", connector="", mask=f", v: {written}", generate="")
    column = lower(parse(text))[0]["tables"][0]["columns"][0]
    assert column["provider_config"]["v"] == item
    assert type(column["provider_config"]["v"]) is type(item)


@pytest.mark.parametrize("item", [float("inf"), float("-inf"), float("nan")])
def test_a_number_that_is_not_finite_is_refused(item: float) -> None:
    with pytest.raises(LangError):
        number(item)


def test_sections_come_in_a_set_order_with_rules_aligned() -> None:
    text = """decoy 1
pipeline p {
  mask t from csv("a.csv", header: true) to csv("b.csv") { long_column_name : redact  b : hash in ids
    keep c  where b > 1  d <- t.b orphans fail }
  options { protected_quarantine: {max_rows: 1} }
  delivery(strict)
  let h = hash in ids
  settings { post_validation: true }
  seed 9
}
"""
    assert (
        _reprinted(text)
        == """decoy 1

pipeline p {
  seed 9

  settings {
    post_validation: true
  }

  let h = hash in ids

  delivery(strict)

  mask t from csv("a.csv", header: true) to csv("b.csv") {
    long_column_name : redact
    b                : hash in ids
    keep c
    where b > 1
    d <- t.b orphans fail
  }

  options {
    protected_quarantine: {max_rows: 1}
  }
}
"""
    )


def test_every_setting_statement_has_a_printed_form() -> None:
    assert set(_SETTINGS) == set(SETTING_STATEMENTS)


def test_an_empty_name_is_refused_with_its_own_message() -> None:
    from decoy.lang._print import name

    with pytest.raises(LangError) as caught:
        name("")
    assert "empty" in caught.value.diagnostics[0].message
