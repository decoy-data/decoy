"""`convert_config`: a pipeline config to `.decoy` text that compiles back to the same pipeline."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from decoy_engine import parse_pipeline_config

from decoy.lang import ConvertError, compile_text, convert_config
from decoy.lang._convert import typed
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
            "is not a strategy",
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
    with pytest.raises(ConvertError, match="would not compile back") as caught:
        convert_config(config)
    assert caught.value.path == "relationships"


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


def _same_pipeline(config: dict) -> str:
    """Convert, compile, and compare with the engine's types kept apart."""
    text = convert_config(config)
    compiled = compile_text(text).config
    wanted = parse_pipeline_config(copy.deepcopy(config)).model_dump()
    assert typed(parse_pipeline_config(copy.deepcopy(compiled)).model_dump()) == typed(wanted)
    return text


def test_columns_whose_rules_differ_only_in_a_value_type_are_not_merged() -> None:
    columns = [
        {"name": name, "strategy": "truncate", "provider_config": {"length": 3, "x": item}}
        for name, item in (("a", 1), ("b", True), ("c", 1.0), ("d", "1"), ("e", [1]), ("f", [True]))
    ]
    text = _same_pipeline(_config(columns))
    assert text.count("truncate(") == 6


@pytest.mark.parametrize("key", ["seed", "true", "if", "unique", "First Name", "in"])
def test_an_option_key_that_is_a_word_of_the_language_round_trips(key: str) -> None:
    column = {"name": "x", "strategy": "truncate", "provider_config": {"length": 3, key: 5}}
    _same_pipeline(_config([dict(_ID), column]))


def test_a_generated_column_with_unique_round_trips() -> None:
    config = {
        "version": 2,
        "global_settings": {"seed": 1},
        "sources": {},
        "tables": [
            {
                "name": "p",
                "row_count": 5,
                "generate_columns": [
                    {"name": "id", "type": "sequence", "start": 1, "unique": True},
                    {"name": "email", "type": "faker", "faker_type": "email", "unique": True},
                ],
            }
        ],
        "targets": {"p": {"type": "file", "format": "csv", "path": "p.csv"}},
    }
    assert "unique: true" in _same_pipeline(config)


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.update(quarantine=None),
        lambda c: c.update(scan_baseline=None, protected_quarantine=None),
        lambda c: c["global_settings"].update(seed="42"),
        lambda c: c["tables"][0].update(transforms=[{"op": "limit", "n": "5"}]),
        lambda c: c["sources"]["t"].update(layout=None),
    ],
    ids=["null-block", "null-blocks", "seed-as-text", "limit-as-text", "null-field"],
)
def test_what_the_engine_accepts_and_normalises_converts(change) -> None:
    _same_pipeline(_broken(change))


def test_the_engine_s_full_dump_of_a_config_converts() -> None:
    config = _config([dict(_ID), {"name": "x", "strategy": "redact"}])
    dumped = parse_pipeline_config(copy.deepcopy(config)).model_dump(by_alias=True)
    _same_pipeline(dumped)


def test_a_sort_with_the_wrong_number_of_directions_is_refused_not_crashed() -> None:
    config = _broken(
        lambda c: c["tables"][0].update(
            transforms=[{"op": "sort", "by": ["id", "x"], "ascending": [True]}]
        )
    )
    with pytest.raises(ConvertError):
        convert_config(config)


def test_a_refusal_never_names_a_map_key_from_the_config() -> None:
    config = _broken(
        lambda c: c["tables"][0]["columns"][1].update(
            provider_config={"people": {"Jane Roe 555-1234": float("inf")}}
        )
    )
    with pytest.raises(ConvertError) as caught:
        convert_config(config)
    assert "Jane" not in str(caught.value)


_REPO = Path(__file__).resolve().parents[3]
# Valid pipeline files the converter is right to refuse, and why.
_REFUSED = {
    "tests/fixtures/qa_first_user/pipeline_no_namespace.yaml": "a relationship with no namespace; a link would add one",
}


def _pipeline_files() -> list[Path]:
    found = []
    for folder in ("examples", "src/decoy/templates", "packaging_tools/smoke", "tests/fixtures"):
        for path in sorted((_REPO / folder).rglob("*.y*ml")):
            try:
                config = yaml.safe_load(path.read_text(encoding="utf-8"))
                parse_pipeline_config(copy.deepcopy(config))
            except Exception:
                continue
            found.append(path)
    return found


def test_every_valid_pipeline_file_in_the_repository_converts_or_is_a_listed_refusal() -> None:
    files = _pipeline_files()
    assert len(files) >= 15
    refused = set()
    for path in files:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        try:
            _same_pipeline(config)
        except ConvertError:
            refused.add(path.relative_to(_REPO).as_posix())
    assert refused == set(_REFUSED)


def test_zero_and_negative_zero_are_not_merged() -> None:
    columns = [
        {"name": name, "strategy": "truncate", "provider_config": {"length": 3, "x": item}}
        for name, item in (("a", 0.0), ("b", -0.0))
    ]
    assert convert_config(_config(columns)).count("truncate(") == 2


def _with_expression(kind: str, text: str) -> dict:
    """A config that holds `text` as a filter, a derive or a generated derived column."""
    if kind == "filter":
        return _broken(
            lambda c: c["tables"][0].update(transforms=[{"op": "filter", "expression": text}])
        )
    if kind == "derive":
        return _broken(
            lambda c: c["tables"][0].update(
                transforms=[{"op": "derive", "column": "z", "expression": text}]
            )
        )
    config = _config([])
    config["sources"] = {}
    config["tables"] = [
        {
            "name": "t",
            "row_count": 5,
            "generate_columns": [
                {"name": "n", "type": "sequence", "start": 1, "step": 1},
                {"name": "d", "type": "derived", "expression": text},
            ],
        }
    ]
    return config


@pytest.mark.parametrize("kind", ["filter", "derive", "generated"])
@pytest.mark.parametrize(
    "text", ["1 == 1 # or drop everything", "n > 1_000"], ids=["comment", "number-underscore"]
)
def test_an_expression_the_writer_would_change_is_refused(kind: str, text: str) -> None:
    # The equivalence proof runs both sides through the writer, so it cannot see a `#` comment
    # or a `_` the writer drops. The writer itself must refuse.
    with pytest.raises(ConvertError) as caught:
        convert_config(_with_expression(kind, text))
    assert "comment or a number" in caught.value.message
    assert caught.value.__context__ is None


def test_an_expression_that_differs_only_in_spacing_still_converts() -> None:
    text = convert_config(_with_expression("filter", "x>1  and   y=='a  b'"))
    assert "x > 1 and y == 'a  b'" in text or "'a  b'" in text


def test_an_unexpected_failure_is_a_value_free_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(config: dict) -> None:
        raise KeyError("SECRET-value")

    monkeypatch.setattr("decoy.lang._convert._program", explode)
    with pytest.raises(ConvertError) as caught:
        convert_config(_config([dict(_ID)]))
    assert "SECRET" not in str(caught.value)
    assert caught.value.__context__ is None and caught.value.__cause__ is None


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s["seeds"][0].update(mode="bogus"),
        lambda s: s["seeds"][0]["predicates"][0].update(op="bogus"),
    ],
    ids=["mode", "op"],
)
def test_an_unknown_subset_op_or_mode_is_refused_not_a_key_error(change) -> None:
    from decoy.lang._convert import _subset

    subset = {
        "seeds": [
            {
                "table": "t",
                "mode": "filter",
                "predicates": [{"column": "a", "op": "eq", "value": 1}],
            }
        ]
    }
    change(subset)
    with pytest.raises(ConvertError):
        _subset(subset)
