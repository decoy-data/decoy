"""Property: a valid pipeline config converts to a program that compiles back to the same model.

The generator builds masked tables (rules with options of every value type, option keys that are
words of the language, conditions, shaping, one foreign key), a generated table, settings, a
subset seed and three checks. It does not build coherent groups, composite keys or a column with
both a link and a rule; those have enumerated cases in `test_convert.py`. Expressions are
generated already spaced as the compiler writes them, so the comparison is exact; respacing has
its own test there. Hypothesis runs derandomized, so a failure reproduces from the test alone.
"""

from __future__ import annotations

import copy

from decoy_engine import parse_pipeline_config
from decoy_engine.config import PipelineConfigError
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from decoy.lang import compile_text, convert_config
from decoy.lang._convert import typed
from decoy.lang._parse import parse
from decoy.lang._print import print_program

# Plain words, words of the language, and names that need quoting.
_NAMES = st.sampled_from(
    [
        "id",
        "email",
        "total",
        "keep",
        "in",
        "when",
        "where",
        "mask",
        "seed",
        "true",
        "First Name",
        "amount_2",
        "desc",
        "x",
        "y",
        "z",
        "Zip-Code",
        "order",
        "limit",
        "null",
        "tier",
    ]
)
_WORDS = st.one_of(_NAMES, st.text('abc XYZ_-./\\"é\n', min_size=1, max_size=8))
_SCALARS = st.one_of(
    st.booleans(),
    st.integers(-(10**9), 10**9),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    _WORDS,
)
_VALUES = st.recursive(
    _SCALARS,
    lambda inner: st.one_of(
        st.lists(inner, max_size=3), st.dictionaries(_WORDS, inner, max_size=3)
    ),
    max_leaves=6,
)
# Equal to Python and different to the engine: adjacent columns must not be merged over these.
_LOOKALIKES = st.sampled_from([1, True, 1.0, "1", "true", [1], [True]])
_KEYS = st.sampled_from(["note", "seed", "true", "if", "unique", "in", "Odd Key"])
_WHEN = st.sampled_from(["x == 1", "x == 1 and y != 'a'", "x in ['a', 'b']", "not (x < 2)"])
_SHAPING = [
    {"op": "filter", "expression": "x > 1 and y < 9"},
    {"op": "derive", "column": "derived_total", "expression": "x * 2"},
    {"op": "sort", "by": ["x", "y"], "ascending": [True, False]},
    {"op": "sort", "by": ["x"]},
    {"op": "limit", "n": 500},
    {"op": "dedupe"},
    {"op": "dedupe", "columns": ["x"]},
    {"op": "drop_column", "columns": ["never_masked"]},
]


@st.composite
def _rule(draw: st.DrawFn) -> dict:
    kind = draw(st.sampled_from(["redact", "passthrough", "hash", "faker", "fpe", "truncate"]))
    rule: dict = {"strategy": kind}
    if kind in ("hash", "fpe"):
        rule["namespace"] = draw(st.sampled_from(["ids", "other"]))
    if kind == "faker":
        rule["provider"] = draw(st.sampled_from(["person_name", "person_email"]))
        if draw(st.booleans()):
            rule["deterministic"] = True
            rule["namespace"] = "people"
    if kind == "fpe":
        rule["provider_config"] = {"charset": draw(st.sampled_from(["digits", "ALPHANUM"]))}
    if kind == "truncate":
        rule["provider_config"] = {
            "length": draw(st.integers(1, 2)),
            draw(_KEYS): draw(st.one_of(_LOOKALIKES, _VALUES)),
        }
    if kind != "passthrough" and draw(st.booleans()):
        rule["when"] = draw(_WHEN)
    return rule


def _source(draw: st.DrawFn) -> dict:
    if draw(st.booleans()):
        return {"type": "file", "format": "parquet", "path": draw(_WORDS)}
    return {
        "type": "file",
        "format": "csv",
        "path": draw(_WORDS),
        "has_header": True,
        "delimiter": draw(st.sampled_from([",", "|", ";"])),
    }


def _generated(draw: st.DrawFn) -> dict:
    return {
        "name": "generated rows",
        "row_count": draw(st.integers(0, 50)),
        "generate_columns": [
            {"name": "id", "type": "sequence", "start": draw(st.integers(0, 9)), "unique": True},
            {
                "name": "kind",
                "type": "categorical",
                "categories": ["a b", "c"],
                "weights": [0.25, 0.75],
            },
            {"name": "label", "type": "derived", "expression": "concat(kind, '-', id)"},
            {"name": "flag", "type": "constant", "value": draw(_LOOKALIKES)},
        ],
    }


@st.composite
def _configs(draw: st.DrawFn) -> dict:
    names = draw(st.lists(_NAMES, min_size=1, max_size=3, unique=True))
    config: dict = {"version": 2, "global_settings": {"seed": draw(st.integers(0, 2**31))}}
    if draw(st.booleans()):
        config["global_settings"]["post_validation"] = draw(st.booleans())
    config["sources"], config["tables"], config["targets"] = {}, [], {}
    for name in names:
        columns = draw(st.lists(_NAMES, min_size=1, max_size=5, unique=True))
        table: dict = {"name": name, "columns": [{"name": c, **draw(_rule())} for c in columns]}
        shaping = draw(st.lists(st.sampled_from(_SHAPING), max_size=3))
        if shaping:
            table["transforms"] = shaping
        config["tables"].append(table)
        config["sources"][name] = _source(draw)
        config["targets"][name] = {"type": "file", "format": "csv", "path": draw(_WORDS)}
    if len(names) > 1 and draw(st.booleans()):
        parent, child = config["tables"][0], config["tables"][1]
        parent["columns"][0].update({"strategy": "hash", "namespace": "ids"})
        parent["columns"][0].pop("when", None)
        child["columns"][0] = {"name": child["columns"][0]["name"], "strategy": "from_parent"}
        config["relationships"] = [
            {
                "parent": {"table": parent["name"], "columns": [parent["columns"][0]["name"]]},
                "children": [{"table": child["name"], "columns": [child["columns"][0]["name"]]}],
                "orphan_policy": draw(st.sampled_from(["preserve", "remap", "warn", "fail"])),
                "namespace": "ids",
            }
        ]
    if draw(st.booleans()):
        config["tables"].append(_generated(draw))
        config["targets"]["generated rows"] = {
            "type": "file",
            "format": "parquet",
            "path": "g.parquet",
        }
    if draw(st.booleans()):
        first = config["tables"][0]
        seed = {
            "table": first["name"],
            "mode": "sample",
            "key_columns": [first["columns"][0]["name"]],
            "fraction": draw(st.sampled_from([0.01, 0.125, 0.333, 1.0])),
        }
        config["subset"] = {"seeds": [seed]}
    if draw(st.booleans()):
        config["delivery"] = {"mode": draw(st.just("strict"))}
    if draw(st.booleans()):
        config["pre_scan"] = {"detectors": ["regex"]}
    if draw(st.booleans()):
        config["validators"] = [
            {"name": "leak_check", "params": {"min_rows": draw(st.integers(1, 99))}}
        ]
    return config


def _model(config: dict) -> dict:
    return parse_pipeline_config(copy.deepcopy(config)).model_dump()


_SETTINGS = settings(
    max_examples=200, deadline=None, derandomize=True, suppress_health_check=[HealthCheck.too_slow]
)


@_SETTINGS
@given(_configs())
def test_a_valid_config_converts_and_compiles_back_to_the_same_model(config: dict) -> None:
    try:
        wanted = _model(config)
    except PipelineConfigError:
        assume(False)
    compiled = compile_text(convert_config(config)).config
    assert typed(_model(compiled)) == typed(wanted)


@_SETTINGS
@given(_configs())
def test_printing_is_a_fixed_point(config: dict) -> None:
    try:
        _model(config)
    except PipelineConfigError:
        assume(False)
    text = convert_config(config)
    assert print_program(parse(text)) == text
