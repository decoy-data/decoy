"""Foreign keys (`<-`) and coherent groups (`{a, b} : rule`)."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from decoy_engine import run_pipeline

from decoy.lang import LangError, compile_text

_PIPELINE = """decoy 1

pipeline shop {
  seed 7

  mask customers from csv("customers.csv") to csv("out/customers.csv") {
    customer_id : hash in customer_identity
    {first_name, last_name, email} : faker(composite_name_email)
  }

  mask orders from csv("orders.csv") to csv("out/orders.csv") {
    order_id : hash in order_identity
    customer_id <- customers.customer_id orphans preserve
    keep total
  }

  mask lines from csv("lines.csv") to csv("out/lines.csv") {
    order_id <- orders.order_id orphans fail
    customer_id <- orders.customer_id orphans preserve
    keep sku
  }

  mask refunds from csv("refunds.csv") to csv("out/refunds.csv") {
    customer_id <- customers.customer_id orphans preserve
    keep amount
  }
}
"""


def _errors(text: str) -> list:
    with pytest.raises(LangError) as caught:
        compile_text(text)
    return list(caught.value.diagnostics)


def test_a_link_declares_the_child_column_and_one_relationship() -> None:
    config = compile_text(_PIPELINE).config
    orders = config["tables"][1]["columns"]
    assert orders[1] == {"name": "customer_id", "strategy": "from_parent"}
    assert config["relationships"][0] == {
        "parent": {"table": "customers", "columns": ["customer_id"]},
        "children": [
            {"table": "orders", "columns": ["customer_id"]},
            {"table": "refunds", "columns": ["customer_id"]},
        ],
        "orphan_policy": "preserve",
        "namespace": "customer_identity",
    }


def test_a_chain_of_links_takes_its_namespace_from_the_first_parent() -> None:
    relationships = compile_text(_PIPELINE).config["relationships"]
    chained = relationships[2]
    assert chained["parent"] == {"table": "orders", "columns": ["customer_id"]}
    assert chained["namespace"] == "customer_identity"
    assert [r["orphan_policy"] for r in relationships] == ["preserve", "fail", "preserve"]


def test_relationships_sit_between_tables_and_targets() -> None:
    assert list(compile_text(_PIPELINE).config) == [
        "version",
        "name",
        "global_settings",
        "sources",
        "tables",
        "relationships",
        "targets",
    ]


def test_a_pipeline_without_links_has_no_relationships_key() -> None:
    text = (
        _PIPELINE.replace("customer_id <- customers.customer_id orphans preserve", "")
        .replace("order_id <- orders.order_id orphans fail", "")
        .replace("customer_id <- orders.customer_id orphans preserve", "")
    )
    assert "relationships" not in compile_text(text).config


def test_composite_key_and_a_namespace_on_the_link() -> None:
    text = _PIPELINE.replace(
        "order_id <- orders.order_id orphans fail\n    customer_id <- orders.customer_id orphans preserve",
        "order_id, customer_id <- orders.(order_id, customer_id) in order_lines orphans fail",
    )
    relationship = compile_text(text).config["relationships"][1]
    assert relationship == {
        "parent": {"table": "orders", "columns": ["order_id", "customer_id"]},
        "children": [{"table": "lines", "columns": ["order_id", "customer_id"]}],
        "orphan_policy": "fail",
        "namespace": "order_lines",
    }


def test_a_coherent_group_names_the_other_columns_on_each_member() -> None:
    columns = compile_text(_PIPELINE).config["tables"][0]["columns"]
    assert columns[1:] == [
        {
            "name": name,
            "strategy": "faker",
            "provider": "composite_name_email",
            "coherent_with": [
                other for other in ("first_name", "last_name", "email") if other != name
            ],
        }
        for name in ("first_name", "last_name", "email")
    ]


@pytest.mark.parametrize(
    ("old", "new", "code", "line"),
    [
        (
            "customers.customer_id orphans preserve\n    keep total",
            "custmers.customer_id orphans preserve\n    keep total",
            "lang.link_unknown_table",
            13,
        ),
        (
            "orders.order_id orphans fail",
            "orders.missing orphans fail",
            "lang.link_unknown_column",
            18,
        ),
        ("orders.order_id orphans fail", "orders.order_id", "lang.orphans_missing", 18),
        (
            "orders.order_id orphans fail",
            "orders.(order_id, total) orphans fail",
            "lang.link_arity",
            18,
        ),
        ("hash in order_identity", "redact", "lang.link_needs_namespace", 18),
        ("orders.order_id orphans fail", "orders.order_id orphans sometimes", "lang.config", 18),
        (
            "keep sku",
            "keep sku\n    order_id <- orders.order_id orphans fail",
            "lang.column_repeated",
            21,
        ),
        (
            "{first_name, last_name, email} : faker(composite_name_email)",
            "{email} : faker(composite_name_email)\n    keep first_name, last_name",
            "lang.group_too_small",
            8,
        ),
    ],
)
def test_link_and_group_errors(old: str, new: str, code: str, line: int) -> None:
    assert old in _PIPELINE
    first = _errors(_PIPELINE.replace(old, new))[0]
    assert (first.code, first.span.line) == (code, line)


def test_a_failed_link_is_reported_once_not_again_by_the_links_below_it() -> None:
    text = _PIPELINE.replace(
        "customers.customer_id orphans preserve\n    keep total",
        "custmers.customer_id orphans preserve\n    keep total",
    )
    assert [d.code for d in _errors(text)] == ["lang.link_unknown_table"]


def test_missing_orphans_hint_lists_the_four_policies() -> None:
    hint = _errors(_PIPELINE.replace("orders.order_id orphans fail", "orders.order_id"))[0].hint
    assert all(word in hint for word in ("preserve", "remap", "warn", "fail"))


def test_compiled_links_keep_the_join_when_the_engine_runs_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DECOY_LANG_TEST_KEY", "k" * 64)
    parent = pa.table({"id": ["a", "b", "c"], "region": ["x", "y", "z"]})
    child = pa.table({"parent_id": ["a", "b", "b", "q"], "amount": ["1", "2", "3", "4"]})
    pq.write_table(parent, tmp_path / "parent.parquet")
    pq.write_table(child, tmp_path / "child.parquet")
    text = f"""decoy 1
pipeline {{
  seed 7
  secret ref("env:DECOY_LANG_TEST_KEY")
  mask parent from parquet("{tmp_path}/parent.parquet") to parquet("{tmp_path}/parent.out.parquet") {{
    id : hash in ids
    keep region
  }}
  mask child from parquet("{tmp_path}/child.parquet") to parquet("{tmp_path}/child.out.parquet") {{
    parent_id <- parent.id orphans preserve
    keep amount
  }}
}}
"""
    config = compile_text(text).config
    result = run_pipeline(config, {"parent": parent, "child": child}, engine_version="0.0.0")
    masked_parent = result.outputs["parent"]["id"].to_pylist()
    masked_child = result.outputs["child"]["parent_id"].to_pylist()
    assert set(masked_parent).isdisjoint({"a", "b", "c"})
    assert masked_child[:3] == [masked_parent[0], masked_parent[1], masked_parent[1]]
    assert masked_child[3] == "q"  # an orphan under `orphans preserve` keeps its value


def test_a_key_column_may_have_a_link_and_a_rule_of_its_own() -> None:
    rule_first = _PIPELINE.replace(
        "customer_id <- customers.customer_id orphans preserve\n    keep total",
        "customer_id : hash in customer_identity\n"
        "    customer_id <- customers.customer_id orphans preserve\n    keep total",
    )
    link_first = _PIPELINE.replace(
        "customer_id <- customers.customer_id orphans preserve\n    keep total",
        "customer_id <- customers.customer_id orphans preserve\n    keep total\n"
        "    customer_id : hash in customer_identity",
    )
    for text in (rule_first, link_first):
        config = compile_text(text).config
        assert config["tables"][1]["columns"][1] == {
            "name": "customer_id",
            "strategy": "hash",
            "namespace": "customer_identity",
        }
        assert config["relationships"] == compile_text(_PIPELINE).config["relationships"]


def test_a_masked_table_can_follow_a_generated_key() -> None:
    text = """decoy 1
pipeline {
  seed 1
  generate g rows 5 to csv("g.csv") { id = sequence(1) }
  mask t from csv("a.csv") to csv("b.csv") {
    gid <- g.id in gids orphans preserve
    x : redact
  }
}
"""
    assert compile_text(text).config["relationships"][0]["parent"] == {
        "table": "g",
        "columns": ["id"],
    }
    assert _errors(text.replace(" in gids", ""))[0].code == "lang.link_needs_namespace"


def test_a_chained_composite_link_takes_the_namespace_of_its_own_key_column() -> None:
    text = """decoy 1
pipeline {
  seed 1
  mask p from csv("p.csv") to csv("p2.csv") { x : hash in nsx  y : hash in nsy }
  mask c from csv("c.csv") to csv("c2.csv") { a, b <- p.(x, y) orphans preserve }
  mask g from csv("g.csv") to csv("g2.csv") { k <- c.b orphans preserve }
}
"""
    relationships = compile_text(text).config["relationships"]
    assert [r["namespace"] for r in relationships] == ["nsx", "nsy"]


def test_link_problems_are_reported_beside_other_problems() -> None:
    text = _PIPELINE.replace(
        "customers.customer_id orphans preserve\n    keep total", "nope.x\n    total : nostrategy"
    )
    codes = {d.code for d in _errors(text)}
    assert {"lang.unknown_strategy", "lang.link_unknown_table", "lang.orphans_missing"} <= codes
