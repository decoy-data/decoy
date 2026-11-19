"""The language surface for settings, sources, targets and masking, and its error reports."""

from __future__ import annotations

import pytest

from decoy.lang import LangError, compile_text, locate, render

_BASE = """decoy 1

pipeline demo {
  seed 42

  table people from csv("in.csv") to parquet("out.parquet") {
    ssn : redact
  }
}
"""


def _config(text: str, *, check: bool = True) -> dict:
    return compile_text(text, check=check).config


def _errors(text: str) -> list:
    with pytest.raises(LangError) as caught:
        compile_text(text)
    return list(caught.value.diagnostics)


def _with_rule(rule: str) -> str:
    return _BASE.replace("ssn : redact", rule)


def test_pipeline_name_and_settings() -> None:
    text = _BASE.replace(
        "seed 42", 'seed 4_200\n  secret ref("mask-key")\n  unconfigured columns error'
    )
    config = _config(text)
    assert config["name"] == "demo"
    assert config["global_settings"] == {
        "seed": 4200,
        "mask_secret_ref": "mask-key",
        "unconfigured_column_policy": "error",
    }


def test_pipeline_name_is_optional() -> None:
    assert "name" not in _config(_BASE.replace("pipeline demo", "pipeline"))


def test_csv_source_has_a_header_by_default_and_targets_do_not_carry_it() -> None:
    config = _config(_BASE)
    assert config["sources"]["people"] == {
        "type": "file",
        "format": "csv",
        "path": "in.csv",
        "has_header": True,
    }
    assert config["targets"]["people"] == {
        "type": "file",
        "format": "parquet",
        "path": "out.parquet",
    }


def test_source_options_are_renamed_and_passed_through() -> None:
    text = _BASE.replace('csv("in.csv")', 'csv("in.csv", header: false, delimiter: "|")')
    source = _config(text, check=False)["sources"]["people"]
    assert source["has_header"] is False
    assert source["delimiter"] == "|"


def test_cloud_sources_read_the_format_from_the_name() -> None:
    text = _BASE.replace(
        'csv("in.csv")', 's3("landing", "members/2026.parquet", credentials: "ro")'
    ).replace('parquet("out.parquet")', 'gcs("out", "members.dat", format: csv)')
    config = _config(text)
    assert config["sources"]["people"] == {
        "type": "s3",
        "bucket": "landing",
        "key": "members/2026.parquet",
        "credentials_ref": "ro",
        "format": "parquet",
    }
    assert config["targets"]["people"]["format"] == "csv"


def test_strategy_options_split_between_the_column_and_provider_config() -> None:
    rule = "ssn : faker(person_name, cardinality_mode: unique, locale: en_GB) in ids deterministic vaulted"
    [column] = _config(_with_rule(rule))["tables"][0]["columns"]
    assert column == {
        "name": "ssn",
        "strategy": "faker",
        "provider": "person_name",
        "namespace": "ids",
        "deterministic": True,
        "vault": True,
        "cardinality_mode": "unique",
        "provider_config": {"locale": "en_GB"},
    }


def test_values_numbers_strings_lists_and_booleans() -> None:
    rule = "ssn : fpe(a: -3, b: 1.5, c: 'x y', d: [one, \"two\", 3], e: true, f: false) in n"
    [column] = _config(_with_rule(rule), check=False)["tables"][0]["columns"]
    assert column["provider_config"] == {
        "a": -3,
        "b": 1.5,
        "c": "x y",
        "d": ["one", "two", 3],
        "e": True,
        "f": False,
    }


def test_keep_several_columns_and_let_reuse() -> None:
    text = _BASE.replace("seed 42", "seed 42\n  let ids = hash in id_space").replace(
        "ssn : redact", "a, b : ids\n    keep c, d"
    )
    columns = _config(text)["tables"][0]["columns"]
    assert columns == [
        {"name": "a", "strategy": "hash", "namespace": "id_space"},
        {"name": "b", "strategy": "hash", "namespace": "id_space"},
        {"name": "c", "strategy": "passthrough"},
        {"name": "d", "strategy": "passthrough"},
    ]


def test_keywords_and_spaced_names_work_as_column_names() -> None:
    rule = "seed, table, `First Name`, `keep` : redact\n    keep from, `in`"
    names = [c["name"] for c in _config(_with_rule(rule))["tables"][0]["columns"]]
    assert names == ["seed", "table", "First Name", "keep", "from", "in"]


def test_comments_are_ignored() -> None:
    assert _config(_BASE.replace("seed 42", "seed 42  # the seed\n  # a note")) == _config(_BASE)


@pytest.mark.parametrize(
    ("text", "code", "line"),
    [
        (_BASE.replace("decoy 1", "decoy 2"), "lang.version", 1),
        (_BASE.replace("ssn : redact", "ssn = redact"), "lang.syntax", 7),
        (_BASE.replace("  seed 42\n", ""), "lang.seed_missing", 3),
        (_BASE.replace("seed 42", "seed 42\n  seed 43"), "lang.setting_repeated", 5),
        (_with_rule("ssn : redcat"), "lang.unknown_strategy", 7),
        (_with_rule("ssn : redact\n    keep ssn"), "lang.column_repeated", 8),
        (_with_rule("ssn : faker(a, b)"), "lang.strategy_arguments", 7),
        (_with_rule("ssn : fpe(namespace: x)"), "lang.option_not_allowed", 7),
        (_with_rule("ssn : fpe(a: 1, a: 2)"), "lang.option_repeated", 7),
        (_with_rule("ssn : fpe(a: 1, digits)"), "lang.positional_after_option", 7),
        (_BASE.replace("seed 42", "seed 42\n  let redact = hash"), "lang.let_shadows_strategy", 5),
        (
            _BASE.replace("seed 42", "seed 42\n  let x = hash\n  let x = hash"),
            "lang.let_repeated",
            6,
        ),
        (
            _BASE.replace("seed 42", "seed 42\n  let x = hash").replace(": redact", ": x in y"),
            "lang.let_modified",
            8,
        ),
        (_BASE.replace('csv("in.csv")', 'ftp("in.csv")'), "lang.unknown_connector", 6),
        (_BASE.replace('csv("in.csv")', 'csv("a", "b")'), "lang.connector_arguments", 6),
        (_BASE.replace('csv("in.csv")', 's3("b", "k")'), "lang.format_unknown", 6),
        (_BASE.replace('csv("in.csv")', 'csv("in.csv", path: "x")'), "lang.option_not_allowed", 6),
        (
            _BASE.replace(
                "table people",
                "table people from csv('a.csv') to csv('b.csv') { keep x }\n  table people",
            ),
            "lang.table_repeated",
            7,
        ),
    ],
)
def test_compile_errors_carry_a_code_and_a_line(text: str, code: str, line: int) -> None:
    first = _errors(text)[0]
    assert (first.code, first.span.line) == (code, line)


def test_unknown_strategy_suggests_the_nearest_name() -> None:
    assert _errors(_with_rule("ssn : redcat"))[0].hint == "did you mean `redact`?"


def test_every_problem_in_a_table_is_reported_together() -> None:
    codes = [d.code for d in _errors(_with_rule("a : nope\n    b : nah"))]
    assert codes == ["lang.unknown_strategy", "lang.unknown_strategy"]


def test_engine_refusals_point_at_the_source_line() -> None:
    text = _BASE.replace('csv("in.csv")', 'csv("in.csv", bogus: 1)')
    [problem] = _errors(text)
    assert problem.code == "lang.config"
    assert (problem.span.line, problem.span.column) == (6, text.splitlines()[5].index("1)") + 1)

    [problem] = _errors(_with_rule("ssn : faker(person_name, cardinality_mode: sometimes)"))
    assert problem.span.line == 7


def test_locate_falls_back_to_the_nearest_enclosing_construct() -> None:
    compiled = compile_text(_BASE)
    assert (
        locate(("tables", 0, "columns", 0, "provider_config", "x"), compiled.source_map).line == 7
    )
    assert locate(("tables", 0, "unknown"), compiled.source_map).line == 6
    assert locate(("nothing",), compiled.source_map).line == 3


def test_render_shows_the_line_a_caret_and_the_hint() -> None:
    text = _with_rule("ssn : redcat")
    shown = render(_errors(text)[0], text, "p.decoy")
    assert shown.splitlines() == [
        "p.decoy:7:11: error[lang.unknown_strategy]: `redcat` is not a strategy or a `let` name",
        "      ssn : redcat",
        "            ^^^^^^",
        "  hint: did you mean `redact`?",
    ]
    assert render(_errors(text)[0]).count("\n") == 1  # no source: position and hint only


def test_layout_is_free_spaces_and_line_breaks_only_separate_words() -> None:
    one_line = " ".join(_BASE.split())
    spread = _BASE.replace("ssn : redact", "ssn\n:\n\n      redact")
    assert _config(one_line) == _config(spread) == _config(_BASE)


def test_reserved_words_in_a_table_need_backticks_as_column_names() -> None:
    assert _errors(_with_rule("keep : redact"))[0].code == "lang.syntax"
    assert (
        _config(_with_rule("`keep`, `vaulted` : redact"))["tables"][0]["columns"][1]["name"]
        == "vaulted"
    )
