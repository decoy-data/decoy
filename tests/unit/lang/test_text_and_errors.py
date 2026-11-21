"""Quoted text, and what an error may and may not contain."""

from __future__ import annotations

import pytest

from decoy.lang import LangError, compile_text
from decoy.lang._lower import lower
from decoy.lang._parse import parse

_PROGRAM = """decoy 1
pipeline {{
  seed 1
  mask t from csv({path}, header: true) to csv("b.csv") {{
    x : {rule}
  }}
}}
"""


def _program(rule: str = "redact", path: str = '"a.csv"') -> str:
    return _PROGRAM.format(rule=rule, path=path)


def _lowered(text: str) -> dict:
    return lower(parse(text))[0]


def _errors(text: str) -> list:
    with pytest.raises(LangError) as caught:
        compile_text(text)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    return list(caught.value.diagnostics)


@pytest.mark.parametrize(
    ("written", "text"),
    [
        (r'"a\nb\tc"', "a\nb\tc"),
        (r'"q\"q \\ \/ \u00e9"', 'q"q \\ / \u00e9'),
        (r"'C:\temp\new.csv'", r"C:\temp\new.csv"),
        (r"'\d+ \N{x}'", r"\d+ \N{x}"),
        ('"it\'s"', "it's"),
    ],
)
def test_double_quotes_take_json_escapes_and_single_quotes_are_literal(
    written: str, text: str
) -> None:
    column = _lowered(_program(f"fpe(note: {written})"))["tables"][0]["columns"][0]
    assert column["provider_config"]["note"] == text


@pytest.mark.parametrize(
    "written", [r'"a\xZZ"', r'"\N{NOPE}"', r'"\d+"', r'"\u12"', r'"C:\temp\q"']
)
def test_an_unknown_escape_is_an_error_with_a_way_out(written: str) -> None:
    problem = _errors(_program(f"fpe(note: {written})"))[0]
    assert problem.code == "lang.string_escape"
    assert "single quotes" in problem.hint


def test_a_single_quoted_path_keeps_its_backslashes() -> None:
    source = _lowered(_program(path=r"'C:\temp\new.csv'"))["sources"]["t"]
    assert source["path"] == r"C:\temp\new.csv"


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        (_program("faker(x, k: [hunter2 hunter3])"), "hunter3"),
        (_program().replace("seed 1", "seed 1\n  secret ref(mysecretname)"), "mysecretname"),
        (_program().replace("seed 1", "seed 987654 55"), "987654"),
        (_program('fpe(k: {"John Smith": 1, "John Smith": 2})'), "John Smith"),
        (_program().replace("decoy 1", "decoy 987654"), "987654"),
        (_program(path='"private-path.csv" "second"'), "private-path"),
        (_program('fpe(note: "top-secret" 5)'), "top-secret"),
    ],
)
def test_no_error_quotes_a_value_from_the_program(text: str, secret: str) -> None:
    for problem in _errors(text):
        assert secret not in problem.message
        assert secret not in (problem.hint or "")


@pytest.mark.parametrize("version", ["1.0", "01", "1_", "2"])
def test_only_the_exact_version_is_read(version: str) -> None:
    assert _errors(_program().replace("decoy 1", f"decoy {version}"))[0].code == "lang.version"


@pytest.mark.parametrize(
    "deep",
    [
        "fpe(k: " + "[" * 3000 + "]" * 3000 + ")",
        "fpe(k: " + "{a: " * 3000 + "1" + "}" * 3000 + ")",
        "redact when " + "(" * 3000 + "a == 1" + ")" * 3000,
    ],
)
def test_deep_nesting_is_an_error_not_a_crash(deep: str) -> None:
    assert _errors(_program(deep))[0].code in ("lang.nesting", "lang.config")


def test_numbers_take_underscores_and_exponents() -> None:
    column = _lowered(_program("fpe(a: 1_000, b: 2.5e3, c: 1e-2, d: -3)"))["tables"][0]["columns"][
        0
    ]
    assert column["provider_config"] == {"a": 1000, "b": 2500.0, "c": 0.01, "d": -3}


@pytest.mark.parametrize(
    "text", ["", "   \n", "\ufeffdecoy 1", "decoy 1 pipeline { seed 1 }", "\x00"]
)
def test_odd_inputs_are_errors(text: str) -> None:
    assert _errors(text)
