"""`generate` blocks: generator calls, expressions, references and unique rules."""

from __future__ import annotations

import pytest

from decoy.lang import LangError, compile_text

_PIPELINE = """decoy 1

pipeline {
  seed 42

  generate patients rows 1_000 to csv("patients.csv") {
    patient_id = sequence(100000, step: 1)
    first_name = faker(first_name)
    plan       = categorical({Basic: 0.3, Standard: 0.4, "Self-pay": 0.3})
    dept       = categorical(["A", "B"], weights: [0.5, 0.5])
    label      = concat(first_name, ' ', plan)
    fee        = faker(random_int, faker_kwargs: {min: 50, max: 5000})
    flag       = constant(-1)
  }

  generate visits rows 3000 to parquet("visits.parquet") {
    visit_id = sequence(1)
    patient_id <- patients.patient_id
    doctor_id  = reference(patients, patient_id)
    nurse_id   = reference(patients, patient_id, distribution: sequential)
    unique (patient_id, doctor_id)
  }
}
"""


def _tables(text: str = _PIPELINE) -> list[dict]:
    return compile_text(text).config["tables"]


def _errors(text: str) -> list:
    with pytest.raises(LangError) as caught:
        compile_text(text)
    return list(caught.value.diagnostics)


def test_a_generate_block_is_a_table_with_a_row_count_and_no_source() -> None:
    config = compile_text(_PIPELINE).config
    assert config["sources"] == {}
    assert [(t["name"], t["row_count"]) for t in config["tables"]] == [
        ("patients", 1000),
        ("visits", 3000),
    ]
    assert config["targets"]["visits"] == {
        "type": "file",
        "format": "parquet",
        "path": "visits.parquet",
    }


def test_plain_values_fill_the_required_options_in_catalog_order() -> None:
    columns = {c["name"]: c for c in _tables()[0]["generate_columns"]}
    assert columns["patient_id"] == {
        "name": "patient_id",
        "type": "sequence",
        "start": 100000,
        "step": 1,
    }
    assert columns["first_name"] == {
        "name": "first_name",
        "type": "faker",
        "faker_type": "first_name",
    }
    assert columns["fee"]["faker_kwargs"] == {"min": 50, "max": 5000}
    assert columns["flag"] == {"name": "flag", "type": "constant", "value": -1}


def test_categorical_takes_a_weight_map_or_a_list() -> None:
    columns = {c["name"]: c for c in _tables()[0]["generate_columns"]}
    assert columns["plan"] == {
        "name": "plan",
        "type": "categorical",
        "categories": ["Basic", "Standard", "Self-pay"],
        "weights": [0.3, 0.4, 0.3],
    }
    assert columns["dept"]["categories"] == ["A", "B"]


def test_an_expression_is_a_derived_column() -> None:
    columns = {c["name"]: c for c in _tables()[0]["generate_columns"]}
    assert columns["label"] == {
        "name": "label",
        "type": "derived",
        "expression": "concat(first_name, ' ', plan)",
    }


def test_the_arrow_and_the_call_both_give_a_reference_column() -> None:
    visits = _tables()[1]
    columns = {c["name"]: c for c in visits["generate_columns"]}
    assert columns["patient_id"] == {
        "name": "patient_id",
        "type": "reference",
        "reference_table": "patients",
        "reference_column": "patient_id",
    }
    assert columns["doctor_id"]["reference_column"] == "patient_id"
    assert columns["nurse_id"]["distribution"] == "sequential"
    assert visits["unique_together"] == [["patient_id", "doctor_id"]]
    assert "unique_together" not in _tables()[0]


def test_masked_and_generated_tables_mix_in_one_pipeline() -> None:
    text = _PIPELINE.replace(
        "generate visits",
        'mask people from csv("in.csv", header: true) to csv("out.csv") { ssn : redact }\n  generate visits',
    )
    config = compile_text(text).config
    assert [t["name"] for t in config["tables"]] == ["patients", "people", "visits"]
    assert list(config["sources"]) == ["people"]


@pytest.mark.parametrize(
    ("old", "new", "code", "line"),
    [
        ("sequence(1)", "sequnce(start: 1)", "lang.unknown_generator", 17),
        ("sequence(1)", "sequence(1, 2)", "lang.generator_arguments", 17),
        ("constant(-1)", "constant(a + 1, x: 2)", "lang.generator_argument", 13),
        ("constant(-1)", "a + {x: 1}", "lang.generator_argument", 13),
        ("constant(-1)", "constant(1, value: 2)", "lang.option_repeated", 13),
        ("constant(-1)", "constant(1, type: x)", "lang.option_not_allowed", 13),
        ("flag       = constant(-1)", "fee = constant(-1)", "lang.column_repeated", 13),
        ("sequence(1)", "sequence(1, bogus: 2)", "lang.config", 17),
        ("unique (patient_id, doctor_id)", "unique (visit_id, doctor_id)", "lang.config", 21),
    ],
)
def test_generate_errors(old: str, new: str, code: str, line: int) -> None:
    assert old in _PIPELINE
    first = _errors(_PIPELINE.replace(old, new))[0]
    assert (first.code, first.span.line) == (code, line)


def test_unknown_generator_suggests_the_nearest_name() -> None:
    problem = _errors(_PIPELINE.replace("sequence(1)", "sequnce(start: 1)"))[0]
    assert problem.hint == "did you mean `sequence`?"


@pytest.mark.parametrize(
    ("written", "code"),
    [
        ("fakr(first_name)", "lang.unknown_generator"),
        ("sequence", "lang.generator_argument"),
        ("sequence(1 + 1)", "lang.generator_argument"),
        ("faker(first_name) + 1", "lang.generator_argument"),
    ],
)
def test_a_generator_written_wrongly_is_not_taken_for_an_expression(
    written: str, code: str
) -> None:
    assert _errors(_PIPELINE.replace("constant(-1)", written))[0].code == code


@pytest.mark.parametrize(
    "written", ["concat(first_name, plan)", "first_name", "if(fee > 1, 'a', 'b')"]
)
def test_an_expression_function_is_still_an_expression(written: str) -> None:
    columns = {
        c["name"]: c
        for c in _tables(_PIPELINE.replace("constant(-1)", written))[0]["generate_columns"]
    }
    assert columns["flag"] == {"name": "flag", "type": "derived", "expression": written}
