"""Every field of the engine's pipeline config can be written in the language.

The field lists come from the engine's JSON schema and the syntax tables from the compiler, so
nothing is restated here. A field the engine adds shows up as one more block that only
`options { }` can write, and the ratchet below fails until the language accounts for it.
"""

from __future__ import annotations

import pytest
from decoy_engine import PipelineConfig

from decoy.lang import LangError
from decoy.lang._lower import BLOCK_SYNTAX, COLUMN_SYNTAX, SETTING_SYNTAX, lower
from decoy.lang._parse import parse

_SCHEMA = PipelineConfig.model_json_schema()
_DEFS = _SCHEMA["$defs"]
# Top-level blocks with no syntax of their own yet: the to-do list, written through `options`.
_OPTIONS_ONLY = sorted(set(_SCHEMA["properties"]) - set(BLOCK_SYNTAX))
# May only go down. Each block that gains syntax lowers it by one.
OPTIONS_ONLY_CEILING = 2

_PROGRAM = """decoy 1
pipeline {{
  seed 1
  {body}
  mask t from csv("a.csv") to csv("b.csv") {{ ssn : redact{option} }}
}}
"""


def _lowered(body: str = "", option: str = "") -> dict:
    return lower(parse(_PROGRAM.format(body=body, option=option)))[0]


def test_the_compiler_names_only_real_config_blocks() -> None:
    assert set(BLOCK_SYNTAX) <= set(_SCHEMA["properties"])
    assert set(SETTING_SYNTAX) <= set(_DEFS["GlobalSettings"]["properties"])
    assert set(COLUMN_SYNTAX) <= set(_DEFS["ColumnConfig"]["properties"])


def test_the_options_only_list_has_not_grown() -> None:
    assert len(_OPTIONS_ONLY) <= OPTIONS_ONLY_CEILING, _OPTIONS_ONLY


@pytest.mark.parametrize("block", _OPTIONS_ONLY)
def test_a_block_without_syntax_is_written_through_options(block: str) -> None:
    assert _lowered(f"options {{ {block}: {{a: [1, x]}} }}")[block] == {"a": [1, "x"]}


@pytest.mark.parametrize("block", sorted(BLOCK_SYNTAX))
def test_a_block_with_syntax_is_refused_in_options(block: str) -> None:
    with pytest.raises(LangError, match="not written in `options`"):
        _lowered(f"options {{ {block}: 1 }}")


def test_every_setting_can_be_written() -> None:
    for field in sorted(set(_DEFS["GlobalSettings"]["properties"]) - set(SETTING_SYNTAX)):
        assert _lowered(f"settings {{ {field}: 7 }}")["global_settings"][field] == 7


def test_every_column_field_can_be_written() -> None:
    # `provider` is the call's plain value and also accepted as an option.
    for field in sorted(set(_DEFS["ColumnConfig"]["properties"]) - set(COLUMN_SYNTAX)):
        column = _lowered(option=f"({field}: 7)")["tables"][0]["columns"][0]
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
