"""Every field of the engine's pipeline config can be written in the language.

The field lists come from the engine's JSON schema at test time, so a field the engine adds makes
a test here fail until the language accounts for it. `OPTIONS_ONLY` is the to-do list: config
blocks that can only be written through the `options { }` escape hatch. It may only shrink.
"""

from __future__ import annotations

import pytest
from decoy_engine import PipelineConfig

from decoy.lang import compile_text

_SCHEMA = PipelineConfig.model_json_schema()
_DEFS = _SCHEMA["$defs"]

# Top-level blocks with syntax of their own, and the syntax.
OWN_SYNTAX = {
    "version": "decoy 1",
    "name": "pipeline <name>",
    "global_settings": "seed, secret ref, unconfigured columns, settings { }",
    "sources": "mask <table> from ...",
    "targets": "... to ...",
    "tables": "mask { } and generate { }",
    "relationships": "child <- table.key orphans <policy>",
}
# Top-level blocks written only through `options { }`, with the milestone that gives each its
# syntax (docs/plans/2026-11-19-decoy-language-completion.md).
OPTIONS_ONLY = {
    "namespaces": 3,
    "pre_scan": 3,
    "post_scan": 3,
    "validators": 3,
    "quarantine": 3,
    "protected_quarantine": 3,
    "delivery": 3,
    "scan_baseline": 3,
    "subset": 4,
}
# Settings with a statement of their own; every other one is written in `settings { }`.
SETTING_STATEMENTS = {"seed", "mask_secret_ref", "unconfigured_column_policy"}
# Column fields with syntax of their own; every other one is written as a call option.
COLUMN_SYNTAX = {
    "name",
    "strategy",
    "provider",
    "namespace",
    "deterministic",
    "vault",
    "when",
    "coherent_with",
    "provider_config",
}

_PROGRAM = """decoy 1
pipeline {{
  seed 1
  {body}
  mask t from csv("a.csv") to csv("b.csv") {{ ssn : redact{option} }}
}}
"""


def _config(body: str = "", option: str = "") -> dict:
    return compile_text(_PROGRAM.format(body=body, option=option), check=False).config


def test_every_top_level_block_is_accounted_for() -> None:
    assert set(OWN_SYNTAX) | set(OPTIONS_ONLY) == set(_SCHEMA["properties"])
    assert not set(OWN_SYNTAX) & set(OPTIONS_ONLY)


def test_the_options_only_list_has_not_grown() -> None:
    assert len(OPTIONS_ONLY) <= 9


@pytest.mark.parametrize("block", sorted(OPTIONS_ONLY))
def test_a_block_without_syntax_is_written_through_options(block: str) -> None:
    assert _config(f"options {{ {block}: {{a: [1, x]}} }}")[block] == {"a": [1, "x"]}


@pytest.mark.parametrize("block", sorted(OWN_SYNTAX))
def test_a_block_with_syntax_is_refused_in_options(block: str) -> None:
    with pytest.raises(Exception, match="not written in `options`"):
        _config(f"options {{ {block}: 1 }}")


def test_every_setting_can_be_written() -> None:
    fields = set(_DEFS["GlobalSettings"]["properties"])
    assert SETTING_STATEMENTS <= fields
    for field in sorted(fields - SETTING_STATEMENTS):
        assert _config(f"settings {{ {field}: 7 }}")["global_settings"][field] == 7


def test_every_column_field_can_be_written() -> None:
    fields = set(_DEFS["ColumnConfig"]["properties"])
    assert COLUMN_SYNTAX <= fields
    for field in sorted(fields - COLUMN_SYNTAX):
        column = _config(option=f"({field}: 7)")["tables"][0]["columns"][0]
        assert column[field] == 7, field


def test_table_and_relationship_fields_are_the_ones_the_compiler_writes() -> None:
    assert set(_DEFS["TableConfig"]["properties"]) == {
        "name",
        "columns",
        "transforms",
        "row_count",
        "generate_columns",
        "unique_together",
    }
    assert set(_DEFS["RelationshipConfig"]["properties"]) == {
        "parent",
        "children",
        "orphan_policy",
        "namespace",
    }


def test_transform_kinds_are_the_ones_the_language_has_statements_for() -> None:
    ops = {
        definition["properties"]["op"]["const"]
        for definition in _DEFS.values()
        if "op" in definition.get("properties", {}) and "const" in definition["properties"]["op"]
    }
    assert ops == {"filter", "derive", "sort", "limit", "dedupe", "drop_column"}
