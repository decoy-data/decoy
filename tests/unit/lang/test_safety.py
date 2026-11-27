"""Checks and safety statements: scans, `expect`, quarantine, baseline, delivery, namespaces."""

from __future__ import annotations

import pytest

from decoy.lang import LangError, compile_text

_PIPELINE = """decoy 1

pipeline {
  seed 42

  scan before(regex, ner)
  scan after(regex, ner, integrity: true, ner_findings: fail, distribution: {tolerance_pct: 5.0})
  expect leak_check(orders.card_number, orders.email, people.email, max_identical_ratio: 0.02)
  expect fk_intact
  quarantine("out/bad.jsonl", triggers: [validation_fail, format_error])
  baseline("scans/base.json", on_drift: warn)
  delivery(strict)
  namespace ids for people.id, orders.person_id

  mask people from csv("a.csv", header: true) to csv("b.csv") {
    id : hash in ids
    email : redact
  }
  mask orders from csv("o.csv", header: true) to csv("p.csv") {
    person_id : hash in ids
    keep card_number, email
  }
}
"""


def _config(text: str = _PIPELINE) -> dict:
    return compile_text(text).config


def _errors(text: str) -> list:
    with pytest.raises(LangError) as caught:
        compile_text(text)
    return list(caught.value.diagnostics)


def test_scans_take_their_detectors_as_plain_values() -> None:
    config = _config()
    assert config["pre_scan"] == {"detectors": ["regex", "ner"]}
    assert config["post_scan"] == {
        "detectors": ["regex", "ner"],
        "integrity": True,
        "ner_findings": "fail",
        "distribution": {"tolerance_pct": 5.0},
    }


def test_a_bare_scan_uses_the_engine_defaults() -> None:
    text = _PIPELINE.replace("scan before(regex, ner)", "scan before")
    assert _config(text)["pre_scan"] == {}


def test_expect_groups_columns_by_table_and_puts_settings_in_params() -> None:
    assert _config()["validators"] == [
        {
            "name": "leak_check",
            "columns": {"orders": ["card_number", "email"], "people": ["email"]},
            "params": {"max_identical_ratio": 0.02},
        },
        {"name": "fk_intact"},
    ]


def test_quarantine_is_enabled_by_being_written() -> None:
    assert _config()["quarantine"] == {
        "enabled": True,
        "output_path": "out/bad.jsonl",
        "triggers": ["validation_fail", "format_error"],
    }


def test_baseline_delivery_and_namespace() -> None:
    config = _config()
    assert config["scan_baseline"] == {
        "schema": "scan-set/v1",
        "path": "scans/base.json",
        "on_drift": "warn",
    }
    assert config["delivery"] == {"mode": "strict"}
    assert config["namespaces"] == {"ids": {"declared_by": ["people.id", "orders.person_id"]}}


def test_a_pipeline_without_these_statements_has_none_of_the_blocks() -> None:
    config = _config("\n".join(_PIPELINE.splitlines()[:5] + _PIPELINE.splitlines()[14:]))
    assert list(config) == ["version", "global_settings", "sources", "tables", "targets"]


@pytest.mark.parametrize(
    ("old", "new", "code", "line"),
    [
        ("scan before(regex, ner)", "scan before(regex)\n  scan before", "lang.block_repeated", 7),
        ("scan before(regex, ner)", "scan before(people.id)", "lang.reference_not_allowed", 6),
        ("delivery(strict)", "delivery(strict, x)", "lang.block_arguments", 12),
        ("delivery(strict)", "delivery(sometimes)", "lang.config", 12),
        ("expect fk_intact", "expect luhn(5)", "lang.expect_argument", 9),
        ("expect fk_intact", "expect luhn(orders.email, a: 1, a: 2)", "lang.option_repeated", 9),
        ("on_drift: warn", "on_drift: warn, schema: x", "lang.option_repeated", 11),
        ("on_drift: warn", "on_drift: fail", "lang.config", 11),
        ("integrity: true, ", "integrity: true, bogus: 1, ", "lang.config", 7),
        (
            "namespace ids for people.id, orders.person_id",
            "namespace ids for people.id\n  namespace ids for orders.person_id",
            "lang.block_repeated",
            14,
        ),
        (
            "delivery(strict)",
            "options { delivery: {mode: strict} }",
            "lang.option_not_allowed",
            12,
        ),
    ],
)
def test_safety_errors(old: str, new: str, code: str, line: int) -> None:
    assert old in _PIPELINE
    first = _errors(_PIPELINE.replace(old, new))[0]
    assert (first.code, first.span.line) == (code, line)
