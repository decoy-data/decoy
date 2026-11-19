"""The language surface for settings, sources, targets and masking, and its error reports."""

from __future__ import annotations

import pytest

from decoy.lang import LangError, compile_text, render
from decoy.lang._lower import lower
from decoy.lang._parse import parse
from decoy.lang._validate import locate

_BASE = """decoy 1

pipeline demo {
  seed 42

  mask people from csv("in.csv") to parquet("out.parquet") {
    ssn : redact
  }
}
"""


def _config(text: str) -> dict:
    return compile_text(text).config


def _lowered(text: str) -> dict:
    """The config before the engine validates it, for options the engine would refuse."""
    return lower(parse(text))[0]


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
    source = _lowered(text)["sources"]["people"]
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
    [column] = _lowered(_with_rule(rule))["tables"][0]["columns"]
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
    rule = "seed, mask, 'First Name', 'keep' : redact\n    keep from, 'in'"
    names = [c["name"] for c in _config(_with_rule(rule))["tables"][0]["columns"]]
    assert names == ["seed", "mask", "First Name", "keep", "from", "in"]


def test_comments_are_ignored() -> None:
    assert _config(_BASE.replace("seed 42", "seed 42  # the seed\n  # a note")) == _config(_BASE)


@pytest.mark.parametrize(
    ("text", "code", "line"),
    [
        (_BASE.replace("decoy 1", "decoy 2"), "lang.version", 1),
        (_BASE.replace("ssn : redact", "ssn ; redact"), "lang.syntax", 7),
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
                "mask people",
                "mask people from csv('a.csv') to csv('b.csv') { keep x }\n  mask people",
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


def test_render_shows_the_position_the_code_and_the_hint() -> None:
    shown = render(_errors(_with_rule("ssn : redcat"))[0], "p.decoy")
    assert shown.splitlines() == [
        "p.decoy:7:11: error[lang.unknown_strategy]: `redcat` is not a strategy or a `let` name",
        "  hint: did you mean `redact`?",
    ]


def test_layout_is_free_spaces_and_line_breaks_only_separate_words() -> None:
    one_line = " ".join(_BASE.split())
    spread = _BASE.replace("ssn : redact", "ssn\n:\n\n      redact")
    assert _config(one_line) == _config(spread) == _config(_BASE)


def test_reserved_words_in_a_table_need_quotes_as_column_names() -> None:
    assert _errors(_with_rule("keep : redact"))[0].code == "lang.syntax"
    assert _errors(_with_rule("'' : redact"))[0].code == "lang.name_empty"
    assert _errors(_with_rule('"ssn" : redact'))[0].code == "lang.syntax"
    assert (
        _config(_with_rule("'keep', 'vaulted' : redact"))["tables"][0]["columns"][1]["name"]
        == "vaulted"
    )


def _columns(rule: str) -> list[dict]:
    return _config(_with_rule(rule))["tables"][0]["columns"]


def test_when_condition_becomes_one_line_of_canonical_text() -> None:
    rule = """ssn : fpe(charset: digits) in ids when country == 'US'
          and   age >= 1_8      # adults
          and state not in ["CA", 'NY'] or not (score < -1)
    email : redact when active == True"""
    first, second = _columns(rule)
    assert first["when"] == (
        "country == 'US' and age >= 18 and state not in [\"CA\", 'NY'] or not (score < -1)"
    )
    assert second == {"name": "email", "strategy": "redact", "when": "active == True"}


def test_a_condition_the_engine_refuses_is_reported_on_the_condition() -> None:
    text = _with_rule("ssn : redact when country + 1 == 2")
    [problem] = _errors(text)
    assert "when_outside_closed_grammar" in problem.message
    assert (problem.span.line, problem.span.column) == (
        7,
        text.splitlines()[6].index("country") + 1,
    )
    assert "compares one column" in problem.hint


def test_let_carries_its_condition() -> None:
    text = _BASE.replace("seed 42", "seed 42\n  let us = redact when country == 'US'").replace(
        "ssn : redact", "ssn : us"
    )
    assert _config(text)["tables"][0]["columns"][0]["when"] == "country == 'US'"


def test_map_values_nest() -> None:
    [column] = _columns("age : derived(expression: 'age * 12', bounds: {min: 0, 'max': 1500})")
    assert column["provider_config"]["bounds"] == {"min": 0, "max": 1500}
    assert _errors(_with_rule("age : derived(b: {a: 1, a: 2})"))[0].code == "lang.option_repeated"


def test_fixed_width_source_takes_its_layout_inline() -> None:
    layout = "{columns: [{name: ssn, start: 0, width: 9}, {name: st, start: 9, width: 2}]}"
    text = _BASE.replace('csv("in.csv")', f'fixed_width("in.txt", layout: {layout})')
    source = _config(text)["sources"]["people"]
    assert source["format"] == "fixed_width"
    assert source["layout"]["columns"][1] == {"name": "st", "start": 9, "width": 2}


def test_table_shaping_statements_become_transforms_in_written_order() -> None:
    rule = """where status != 'TEST' and age >= 18
    full_name = first_name + ' ' + last_name
    band = if(age >= 65, 'senior', 'adult')
    sort by signup desc, id
    sort by id
    limit 5_000
    dedupe on member_id, plan
    dedupe
    drop notes, internal
    ssn : redact"""
    table = _config(_with_rule(rule))["tables"][0]
    assert table["transforms"] == [
        {"op": "filter", "expression": "status != 'TEST' and age >= 18"},
        {"op": "derive", "column": "full_name", "expression": "first_name + ' ' + last_name"},
        {"op": "derive", "column": "band", "expression": "if(age >= 65, 'senior', 'adult')"},
        {"op": "sort", "by": ["signup", "id"], "ascending": [False, True]},
        {"op": "sort", "by": ["id"]},
        {"op": "limit", "n": 5000},
        {"op": "dedupe", "columns": ["member_id", "plan"]},
        {"op": "dedupe"},
        {"op": "drop_column", "columns": ["notes", "internal"]},
    ]
    assert table["columns"] == [{"name": "ssn", "strategy": "redact"}]


def test_a_table_without_shaping_has_no_transforms_key() -> None:
    assert "transforms" not in _config(_BASE)["tables"][0]


@pytest.mark.parametrize("rule", ["row_id = sequence(start: 1)", "row_id = faker(first_name)"])
def test_a_generator_in_a_masked_table_is_refused(rule: str) -> None:
    problem = _errors(_with_rule(f"{rule}\n    ssn : redact"))[0]
    assert (problem.code, problem.span.line) == ("lang.generator_in_masked_table", 7)
    assert "`generate` table" in problem.hint


@pytest.mark.parametrize("word", ["or", "limit", "keep", "drop"])
def test_a_language_word_as_a_column_name_gets_a_quoting_hint(word: str) -> None:
    problem = _errors(_with_rule(f"ssn : redact when a == 1\n    {word} : hash"))[0]
    assert problem.code == "lang.syntax"
    assert f"write '{word}'" in problem.hint
    assert _columns(f"ssn : redact when a == 1\n    '{word}' : redact")[1]["name"] == word


def test_a_missing_value_does_not_get_the_quoting_hint() -> None:
    assert "write '" not in _errors(_BASE.replace("seed 42", "seed"))[0].hint


def test_settings_block_takes_any_setting_by_its_engine_name() -> None:
    text = _BASE.replace(
        "seed 42",
        "seed 42\n  settings {\n    post_validation: true\n    on_pool_exhaustion: fail,\n"
        "    dp: {epsilon: 1.5}\n  }",
    )
    assert _config(text)["global_settings"] == {
        "seed": 42,
        "post_validation": True,
        "on_pool_exhaustion": "fail",
        "dp": {"epsilon": 1.5},
    }


def test_options_block_writes_top_level_config_after_the_targets() -> None:
    text = _BASE.replace("seed 42", "seed 42\n  options { subset: {allow_dangling: true} }")
    config = _lowered(text)
    assert config["subset"] == {"allow_dangling": True}
    assert list(config)[-2:] == ["targets", "subset"]


@pytest.mark.parametrize(
    ("block", "code", "line"),
    [
        ("settings { seed: 1 }", "lang.option_not_allowed", 5),
        ("settings { post_validation: true post_validation: false }", "lang.setting_repeated", 5),
        ("settings { on_pool_exhaustion: maybe }", "lang.config", 5),
        ("settings { no_such_setting: 1 }", "lang.config", 5),
        ("options { sources: {} }", "lang.option_not_allowed", 5),
        (
            "options { subset: {a: 1} subset: {a: 1} }",
            "lang.option_repeated",
            5,
        ),
        ("options { no_such_block: 1 }", "lang.config", 5),
    ],
)
def test_settings_and_options_errors(block: str, code: str, line: int) -> None:
    first = _errors(_BASE.replace("seed 42", f"seed 42\n  {block}"))[0]
    assert (first.code, first.span.line) == (code, line)
