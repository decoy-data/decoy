"""`subset { }`: seeds, followed links, budget."""

from __future__ import annotations

import pytest
from decoy_engine import PipelineConfig

from decoy.lang import LangError, compile_text
from decoy.lang._subset import PREDICATES

_TABLES = "\n".join(
    f'  mask {name} from csv("{name}.csv", header: true) to csv("out/{name}.csv") {{ id : hash in ids }}'
    for name in ("customers", "orders", "vips", "pairs", "big")
)
_PIPELINE = (
    """decoy 1

pipeline {
  seed 42

  subset {
    start customers sample 2% by customer_id
    start orders where total > 1000, status == 'open', closed_at is null, region in [east, west]
    start vips keys customer_id in [101, 102]
    start pairs keys a, b in [[1, 2], [3, 4]]
    start big sample 500 rows by id, part
    follow customers.customer_id -> orders.customer_id downward
    follow pairs.(a, b) -> big.(a, b) none
    budget(max_total_rows: 2_000_000, max_table_seed_multiple: 10)
    allow dangling
  }

"""
    + _TABLES
    + "\n}\n"
)


def _subset(text: str = _PIPELINE) -> dict:
    return compile_text(text).config["subset"]


def _errors(text: str) -> list:
    with pytest.raises(LangError) as caught:
        compile_text(text)
    return list(caught.value.diagnostics)


def test_a_sample_is_a_share_or_a_row_count_by_key() -> None:
    seeds = _subset()["seeds"]
    assert seeds[0] == {
        "table": "customers",
        "mode": "sample",
        "key_columns": ["customer_id"],
        "fraction": 0.02,
    }
    assert seeds[4] == {
        "table": "big",
        "mode": "sample",
        "key_columns": ["id", "part"],
        "count": 500,
    }


@pytest.mark.parametrize(
    ("written", "fraction"), [("33.3%", 0.333), ("0.1%", 0.001), ("100%", 1.0)]
)
def test_a_percentage_becomes_the_exact_decimal_fraction(written: str, fraction: float) -> None:
    assert _subset(_PIPELINE.replace("2%", written))["seeds"][0]["fraction"] == fraction


def test_a_filter_is_one_predicate_per_test() -> None:
    assert _subset()["seeds"][1] == {
        "table": "orders",
        "mode": "filter",
        "predicates": [
            {"column": "total", "op": "gt", "value": 1000},
            {"column": "status", "op": "eq", "value": "open"},
            {"column": "closed_at", "op": "is_null"},
            {"column": "region", "op": "in", "value": ["east", "west"]},
        ],
    }


def test_keys_are_rows_and_one_key_column_takes_plain_values() -> None:
    seeds = _subset()["seeds"]
    assert seeds[2]["keys"] == [[101], [102]]
    assert seeds[3] == {
        "table": "pairs",
        "mode": "keys",
        "key_columns": ["a", "b"],
        "keys": [[1, 2], [3, 4]],
    }


def test_follow_budget_and_dangling() -> None:
    subset = _subset()
    assert subset["edge_directions"] == {
        "customers.customer_id -> orders.customer_id": "downward",
        "pairs.a,b -> big.a,b": "none",
    }
    assert subset["budget"] == {"max_total_rows": 2000000, "max_table_seed_multiple": 10}
    assert subset["allow_dangling"] is True


def test_only_what_is_written_is_emitted() -> None:
    text = "\n".join(line for line in _PIPELINE.splitlines() if "follow" not in line)
    text = text.replace("    allow dangling\n", "").replace(
        "    budget(max_total_rows: 2_000_000, max_table_seed_multiple: 10)\n", ""
    )
    assert list(_subset(text)) == ["seeds"]


def test_every_engine_predicate_has_a_spelling() -> None:
    schema = PipelineConfig.model_json_schema()["$defs"]["SubsetPredicateConfig"]
    assert set(PREDICATES.values()) == set(schema["properties"]["op"]["enum"])


@pytest.mark.parametrize(
    ("old", "new", "code", "line"),
    [
        ("sample 2%", "sample 200%", "lang.config", 7),
        ("500 rows", "2.5 rows", "lang.sample_rows", 11),
        ("total > 1000", "total + 1000", "lang.subset_condition", 8),
        ("downward", "sideways", "lang.config", 6),
        ("budget(max_total_rows: 2_000_000,", "budget(5,", "lang.block_arguments", 14),
        ("max_table_seed_multiple", "bogus", "lang.config", 14),
        (
            "    allow dangling\n",
            "    allow dangling\n  }\n  subset {\n",
            "lang.block_repeated",
            17,
        ),
        (
            "start vips keys customer_id in [101, 102]",
            "start nobody keys id in [1]",
            "lang.config",
            3,
        ),
        ("    allow dangling\n", "    budget(max_total_rows: 1)\n", "lang.block_repeated", 15),
        (
            "follow pairs.(a, b) -> big.(a, b) none",
            "follow customers.customer_id -> orders.customer_id upward",
            "lang.block_repeated",
            13,
        ),
    ],
)
def test_subset_errors(old: str, new: str, code: str, line: int) -> None:
    assert old in _PIPELINE
    first = _errors(_PIPELINE.replace(old, new))[0]
    assert (first.code, first.span.line) == (code, line)
