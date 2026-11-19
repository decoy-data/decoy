"""`convert_config`: a pipeline config to `.decoy` text that compiles back to the same pipeline."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from decoy.lang import ConvertError, compile_text, convert_config
from decoy.templates import get_template, template_names

_TWINS = Path(__file__).parent / "twins"
_FILE = {"type": "file", "format": "parquet", "path": "t.parquet"}


def _config(columns: list[dict], **top: object) -> dict:
    return {
        "version": 2,
        "global_settings": {"seed": 7},
        "sources": {"t": dict(_FILE)},
        "tables": [{"name": "t", "columns": columns}],
        "targets": {"t": {"type": "file", "format": "csv", "path": "out.csv"}},
        **top,
    }


_ID = {"name": "id", "strategy": "hash", "namespace": "ids"}


@pytest.mark.parametrize("name", sorted(template_names()))
def test_each_twin_is_the_converter_output_for_its_template(name: str) -> None:
    converted = convert_config(yaml.safe_load(get_template(name).body))
    assert (_TWINS / f"{name}.decoy").read_text(encoding="utf-8") == converted


def test_adjacent_columns_with_one_rule_share_a_line() -> None:
    columns = [
        {"name": "a", "strategy": "redact"},
        {"name": "b", "strategy": "redact"},
        {"name": "c", "strategy": "passthrough"},
        {"name": "d", "strategy": "passthrough"},
        {"name": "e", "strategy": "redact"},
    ]
    text = convert_config(_config(columns))
    assert "    a, b : redact\n    keep c, d\n    e : redact\n" in text


@pytest.mark.parametrize(
    "top",
    [
        {"name": "nightly"},
        {
            "global_settings": {
                "seed": 3,
                "post_validation": True,
                "dp": {"epsilon": 1.5, "delta": 1e-06},
            }
        },
        {
            "global_settings": {
                "seed": 3,
                "mask_secret_ref": "env:KEY",
                "unconfigured_column_policy": "error",
            }
        },
        {
            "sources": {
                "t": {"type": "file", "format": "csv", "path": "a b.csv", "has_header": True}
            }
        },
        {
            "sources": {
                "t": {
                    "type": "s3",
                    "format": "parquet",
                    "bucket": "b",
                    "key": "k/x.parquet",
                    "credentials_ref": "ro",
                }
            }
        },
        {"sources": {"t": {"type": "s3", "format": "csv", "bucket": "b", "key": "k/x.dat"}}},
        {
            "targets": {
                "t": {"type": "gcs", "format": "parquet", "bucket": "b", "object": "o.parquet"}
            }
        },
        {"pre_scan": {"detectors": ["regex", "ner"]}},
        {"post_scan": {"integrity": True, "distribution": {"tolerance_pct": 2.5}}},
        {
            "validators": [
                {"name": "leak_check", "columns": {"t": ["id"]}, "params": {"min_rows": 5}},
                {"name": "fk_intact"},
            ]
        },
        {"quarantine": {"enabled": True, "output_path": "q.jsonl", "triggers": ["format_error"]}},
        {"scan_baseline": {"path": "b.json", "schema": "scan-set/v1"}},
        {"delivery": {"mode": "best_effort"}},
        {"namespaces": {"ids": {"declared_by": ["t.id"]}}},
        {
            "subset": {
                "seeds": [
                    {"table": "t", "mode": "sample", "key_columns": ["id"], "fraction": 0.125}
                ]
            }
        },
        {
            "subset": {
                "seeds": [{"table": "t", "mode": "sample", "key_columns": ["id"], "count": 9}],
                "budget": {"max_total_rows": 50},
                "allow_dangling": True,
            }
        },
        {
            "subset": {
                "seeds": [
                    {
                        "table": "t",
                        "mode": "filter",
                        "predicates": [
                            {"column": "id", "op": "ge", "value": 3},
                            {"column": "id", "op": "is_not_null"},
                            {"column": "id", "op": "in", "value": ["a", "b"]},
                        ],
                    }
                ]
            }
        },
        {
            "subset": {
                "seeds": [{"table": "t", "mode": "keys", "key_columns": ["id"], "keys": [[1], [2]]}]
            }
        },
    ],
)
def test_pipeline_level_blocks_round_trip(top: dict) -> None:
    config = _config([dict(_ID)], **top)
    assert compile_text(convert_config(config)).config == config


@pytest.mark.parametrize(
    "column",
    [
        {
            "name": "x",
            "strategy": "faker",
            "provider": "person_name",
            "deterministic": True,
            "namespace": "n",
        },
        {
            "name": "x",
            "strategy": "faker",
            "provider": "person_name",
            "vault": True,
            "namespace": "n",
        },
        {
            "name": "x",
            "strategy": "fpe",
            "namespace": "n",
            "provider_config": {"charset": "digits", "validate_luhn": True},
        },
        {"name": "x", "strategy": "redact", "when": "id == 'a' and id != 'b'"},
        {"name": "x", "strategy": "faker", "provider": "person_name", "cardinality_mode": "unique"},
        {
            "name": "x",
            "strategy": "derived",
            "provider_config": {"expression": "id * 2", "bounds": {"min": 0, "max": 9}},
        },
        {"name": "First Name", "strategy": "redact"},
        {"name": "keep", "strategy": "redact"},
        {
            "name": "x",
            "strategy": "truncate",
            "provider_config": {"length": 3, "note": "true", "tag": "in", "ratio": 0.000001},
        },
    ],
)
def test_column_rules_round_trip(column: dict) -> None:
    config = _config([dict(_ID), column])
    assert compile_text(convert_config(config)).config == config


def test_transforms_round_trip_and_expressions_are_respaced() -> None:
    transforms = [
        {"op": "filter", "expression": "id>3 and  id<9"},
        {"op": "derive", "column": "twice", "expression": "id*2"},
        {"op": "sort", "by": ["id", "twice"], "ascending": [True, False]},
        {"op": "sort", "by": ["id"], "ascending": False},
        {"op": "limit", "n": 10},
        {"op": "dedupe", "columns": ["id"]},
        {"op": "dedupe"},
        {"op": "drop_column", "columns": ["junk"]},
    ]
    config = _config([dict(_ID)])
    config["tables"][0]["transforms"] = transforms
    compiled = compile_text(convert_config(config)).config["tables"][0]["transforms"]
    assert compiled[0] == {"op": "filter", "expression": "id > 3 and id < 9"}
    assert compiled[1]["expression"] == "id * 2"
    assert compiled[3] == {"op": "sort", "by": ["id"], "ascending": [False]}
    assert compiled[2:3] + compiled[4:] == transforms[2:3] + transforms[4:]


def _related(child_column: dict, **relationship: object) -> dict:
    config = _config([dict(_ID)])
    config["sources"]["c"] = dict(_FILE, path="c.parquet")
    config["targets"]["c"] = {"type": "file", "format": "csv", "path": "c.csv"}
    config["tables"].append(
        {"name": "c", "columns": [child_column, {"name": "n", "strategy": "redact"}]}
    )
    config["relationships"] = [
        {
            "parent": {"table": "t", "columns": ["id"]},
            "children": [{"table": "c", "columns": ["tid"]}],
            "orphan_policy": "remap",
            "namespace": "ids",
            **relationship,
        }
    ]
    return config


@pytest.mark.parametrize(
    "config",
    [
        _related({"name": "tid", "strategy": "from_parent"}),
        _related({"name": "tid", "strategy": "from_parent"}, namespace="other"),
        _related({"name": "tid", "strategy": "hash", "namespace": "ids"}),
        _related({"name": "tid", "strategy": "passthrough"}),
    ],
    ids=["from_parent", "own-namespace", "own-rule", "kept"],
)
def test_relationships_round_trip(config: dict) -> None:
    assert compile_text(convert_config(config)).config == config


def test_a_coherent_group_round_trips() -> None:
    names = ["first_name", "last_name", "email"]
    columns = [
        {
            "name": name,
            "strategy": "faker",
            "provider": "composite_name_email",
            "coherent_with": [other for other in names if other != name],
        }
        for name in names
    ]
    config = _config([dict(_ID), *columns])
    text = convert_config(config)
    assert "{first_name, last_name, email} : faker(composite_name_email)" in text
    assert compile_text(text).config == config


def test_generated_tables_round_trip() -> None:
    config = {
        "version": 2,
        "global_settings": {"seed": 1},
        "sources": {},
        "tables": [
            {
                "name": "p",
                "row_count": 10,
                "generate_columns": [
                    {"name": "id", "type": "sequence", "start": 1, "step": 2},
                    {
                        "name": "tier",
                        "type": "categorical",
                        "categories": ["a b", "c"],
                        "weights": [0.5, 0.5],
                    },
                    {"name": "code", "type": "categorical", "categories": [1, 2]},
                    {"name": "label", "type": "derived", "expression": "concat(tier, '-', id)"},
                    {
                        "name": "fee",
                        "type": "faker",
                        "faker_type": "random_int",
                        "faker_kwargs": {"min": 1, "max": 9},
                    },
                ],
            },
            {
                "name": "c",
                "row_count": 20,
                "generate_columns": [
                    {
                        "name": "a",
                        "type": "reference",
                        "reference_table": "p",
                        "reference_column": "id",
                    },
                    {
                        "name": "b",
                        "type": "reference",
                        "reference_table": "p",
                        "reference_column": "id",
                    },
                    {
                        "name": "s",
                        "type": "reference",
                        "reference_table": "p",
                        "reference_column": "id",
                        "distribution": "sequential",
                    },
                ],
                "unique_together": [["a", "b"]],
            },
        ],
        "targets": {
            name: {"type": "file", "format": "csv", "path": f"{name}.csv"} for name in "pc"
        },
    }
    assert compile_text(convert_config(config)).config == config


def _broken(change) -> dict:
    config = copy.deepcopy(_config([dict(_ID), {"name": "x", "strategy": "redact"}]))
    change(config)
    return config


@pytest.mark.parametrize(
    ("change", "path", "message"),
    [
        (lambda c: c["tables"][0]["columns"].clear(), "", "does not validate"),
        (
            lambda c: c["tables"][0]["columns"][1].update(strategy="no_such_strategy"),
            "",
            "cannot write",
        ),
        (
            lambda c: c["tables"][0]["columns"][1].update(provider_config={"x": None}),
            "tables[0].columns[1].x",
            "null",
        ),
        (
            lambda c: c["tables"][0]["columns"][1].update(provider_config={"scale": 2}),
            "tables[0].columns[1].provider_config.scale",
            "column setting",
        ),
        (
            lambda c: c["tables"][0].update(
                transforms=[{"op": "filter", "expression": "id ** 2 > 4"}]
            ),
            "tables[0].transforms[0].expression",
            "expression",
        ),
        (
            lambda c: c.update(quarantine={"enabled": False, "output_path": "q"}),
            "quarantine.enabled",
            "one value",
        ),
        (
            lambda c: c.update(namespaces={"ids": {"declared_by": []}}),
            "namespaces.ids",
            "declared for",
        ),
        (
            lambda c: c["sources"].update(
                extra={"type": "file", "format": "parquet", "path": "e.parquet"}
            ),
            "sources.extra",
            "not declared",
        ),
    ],
)
def test_configs_that_cannot_be_written_are_refused(change, path: str, message: str) -> None:
    with pytest.raises(ConvertError) as caught:
        convert_config(_broken(change))
    assert caught.value.path == path
    assert message in caught.value.message


def test_a_program_that_would_mean_something_else_is_refused() -> None:
    # No namespace on the relationship: a link would add the parent key's, changing the pipeline.
    config = _related({"name": "tid", "strategy": "from_parent"})
    del config["relationships"][0]["namespace"]
    with pytest.raises(ConvertError, match="would not compile back"):
        convert_config(config)


def test_a_refusal_names_no_value_from_the_config() -> None:
    config = _broken(
        lambda c: c["tables"][0].update(transforms=[{"op": "filter", "expression": "SECRET ** 2"}])
    )
    config["sources"]["t"]["path"] = "private-path.parquet"
    with pytest.raises(ConvertError) as caught:
        convert_config(config)
    assert "SECRET" not in str(caught.value)
    assert "private-path" not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
