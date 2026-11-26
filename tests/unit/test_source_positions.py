"""A5: dotted engine/Pydantic paths -> exact YAML marks, or no guessed region.

The oracle for every expected line/column is computed by plain string search over
the same text, independently of PyYAML's marks.
"""

from __future__ import annotations

import pytest
from tests.ci_support import CLEAN_PIPELINE

from decoy._source_positions import (
    DecoyPositionIndex,
    Position,
    YamlPositionIndex,
    nearest,
    segments,
    without_union_member,
)
from decoy.lang import _validate as lang_validate


def _pos(text: str, needle: str, occurrence: int = 1) -> tuple[int, int]:
    """1-based (line, column) of the Nth occurrence of `needle`, columns in code points."""
    idx = -1
    for _ in range(occurrence):
        idx = text.index(needle, idx + 1)
    before = text[:idx]
    line = before.count("\n") + 1
    col = idx - (before.rfind("\n") + 1) + 1
    return line, col


def _index(text: str) -> YamlPositionIndex:
    return YamlPositionIndex.from_bytes(text.encode("utf-8"))


def _assert_key(loc: Position | None, text: str, key: str, occurrence: int = 1) -> None:
    line, col = _pos(text, key, occurrence)
    assert loc is not None
    assert (loc.line, loc.column) == (line, col)
    # single-line key: the end is one-based and exclusive
    assert (loc.end_line, loc.end_column) == (line, col + len(key))


def test_block_style_exact_leaf_numeric_and_semantic_agree() -> None:
    idx = _index(CLEAN_PIPELINE)
    semantic = idx.locate("tables.customers.columns.email.provider")
    numeric = idx.locate("tables.0.columns.0.provider")
    _assert_key(semantic, CLEAN_PIPELINE, "provider")
    assert semantic == numeric


def test_mapping_key_paths_resolve_directly() -> None:
    idx = _index(CLEAN_PIPELINE)
    _assert_key(idx.locate("sources.customers.path"), CLEAN_PIPELINE, "path")
    _assert_key(idx.locate("targets.customers.path"), CLEAN_PIPELINE, "path", occurrence=2)
    _assert_key(idx.locate("global_settings.seed"), CLEAN_PIPELINE, "seed")


def test_list_entry_alias_marks_the_entry_start_only() -> None:
    idx = _index(CLEAN_PIPELINE)
    loc = idx.locate("tables.customers.columns.email")
    line, col = _pos(CLEAN_PIPELINE, "name: email")
    assert (loc.line, loc.column) == (line, col)
    assert loc.end_line is None and loc.end_column is None
    assert idx.locate("tables.0.columns.0") == loc


def test_moving_the_key_moves_the_region() -> None:
    moved = "# a\n# b\n" + CLEAN_PIPELINE
    a = _index(CLEAN_PIPELINE).locate("tables.customers.columns.email.provider")
    b = _index(moved).locate("tables.customers.columns.email.provider")
    assert b.line == a.line + 2 and b.column == a.column


def test_flow_style_and_quoted_keys() -> None:
    text = "root: {alpha: {\"beta key\": 1, 'gamma': [10, {delta: 2}]}}\n"
    idx = _index(text)
    _assert_key(idx.locate("root.alpha"), text, "alpha")
    loc = idx.locate("root.alpha.beta key")
    line, col = _pos(text, '"beta key"')
    assert (loc.line, loc.column) == (line, col)
    _assert_key(idx.locate("root.alpha.gamma.1.delta"), text, "delta")


def test_unicode_columns_count_code_points_not_bytes() -> None:
    text = 'k\u00e9y: \u00fcber\nflow: {"\u043a\u043b\u044e\u0447": 1, target: 2}\n'
    idx = _index(text)
    _assert_key(idx.locate("flow.target"), text, "target")
    _assert_key(idx.locate("k\u00e9y"), text, "k\u00e9y")


def test_crlf_line_endings_keep_one_based_lines() -> None:
    text = CLEAN_PIPELINE.replace("\n", "\r\n")
    loc = _index(text).locate("tables.customers.columns.email.provider")
    line, col = _pos(CLEAN_PIPELINE, "provider")
    assert (loc.line, loc.column) == (line, col)


def test_nearest_proved_parent_is_file_level_without_a_region() -> None:
    idx = _index(CLEAN_PIPELINE)
    loc = idx.locate("tables.customers.columns.email.cardinality_mode")
    assert loc == Position()
    assert loc.line is None


def test_bracket_notation_from_engine_paths_is_normalized() -> None:
    text = "nodes:\n  - id: a\n  - id: b\n    config:\n      path: x\n"
    idx = _index(text)
    _assert_key(idx.locate("nodes[1].config.path"), text, "path")


@pytest.mark.parametrize(
    "path",
    [
        None,
        "",
        "tables.*.columns",
        "tables.customers.columns.*.provider",
        "<snapshot_file=anything>",
        "tables.<unknown>.x",
        "totally.absent.path",
    ],
)
def test_wildcards_pseudo_paths_and_unknowns_produce_no_region(path) -> None:
    assert _index(CLEAN_PIPELINE).locate(path) is None


def test_duplicate_names_are_ambiguous_but_indexes_still_resolve() -> None:
    text = (
        "tables:\n"
        "  - name: dup\n"
        "    columns:\n"
        "      - name: a\n"
        "        provider: x\n"
        "  - name: dup\n"
        "    columns:\n"
        "      - name: a\n"
        "        provider: y\n"
    )
    idx = _index(text)
    assert idx.locate("tables.dup.columns.a.provider") is None
    assert idx.locate("tables.dup") is None
    _assert_key(idx.locate("tables.1.columns.0.provider"), text, "provider", occurrence=2)


def test_duplicate_mapping_keys_are_ambiguous() -> None:
    text = "a:\n  b: 1\na:\n  b: 2\n"
    assert _index(text).locate("a.b") is None


def test_alias_numeric_collision_is_ambiguous() -> None:
    text = 'items:\n  - name: "1"\n    v: 1\n  - name: two\n    v: 2\n'
    idx = _index(text)
    assert idx.locate("items.1") is None  # numeric 1 vs the entry NAMED "1"
    assert idx.locate("items.two") is not None


def test_yaml_aliases_never_yield_the_anchor_site_for_the_alias_path() -> None:
    text = "base: &b\n  provider: person_email\nuse: *b\n"
    idx = _index(text)
    _assert_key(idx.locate("base.provider"), text, "provider")
    loc = idx.locate("use.provider")
    # either no region or file-level; never the anchor's line
    assert loc is None or loc.line is None
    use = idx.locate("use")
    line, _ = _pos(text, "use")
    assert use is not None and use.line == line


def test_merge_key_children_have_no_guessed_region() -> None:
    text = "base: &b {provider: p}\nchild:\n  <<: *b\n  other: 1\n"
    loc = _index(text).locate("child.provider")
    assert loc is None or loc.line is None


def test_malformed_yaml_has_an_empty_index() -> None:
    idx = _index("a: [unterminated\n  b: : :\n")
    assert idx.locate("a") is None


def test_non_utf8_bytes_have_an_empty_index() -> None:
    assert YamlPositionIndex.from_bytes(b"\xff\xfe\x00bad").locate("a") is None


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tables.0.columns.2", ("tables", "0", "columns", "2")),
        ("tables[0].columns[2].provider", ("tables", "0", "columns", "2", "provider")),
        ("tables.customers.columns.email", ("tables", "customers", "columns", "email")),
        ("a", ("a",)),
        (".a.b.", ("a", "b")),
        (None, None),
        ("", None),
        ("tables.*.x", None),
        ("tables.<unknown>.x", None),
        ("a..b", None),
    ],
)
def test_segments_is_the_one_path_parser(path, expected) -> None:
    assert segments(path) == expected


def test_a_position_with_every_field_none_names_no_region() -> None:
    assert Position().line is None and Position() == Position(None, None, None, None)


def test_index_holds_marks_and_path_tokens_only() -> None:
    canary = "SCALAR_VALUE_CANARY_c19f02"
    idx = _index(f"a:\n  b: {canary}\n")
    assert canary not in repr(idx) and canary not in repr(vars(idx))


# -- `.decoy` positions (DecoyPositionIndex) and the shared lookup rules ---------------------------


class _Span:
    """Stands in for `decoy.lang.Span`: `_source_positions` never imports the language."""

    def __init__(self, line: int, column: int = 3) -> None:
        self.line, self.column = line, column
        self.end_line, self.end_column = line, column + 4


_YAML = (
    "name: demo\n"  # 1
    "sources:\n"  # 2
    "  - name: src\n"  # 3
    "    csv:\n"  # 4
    "      path: in.csv\n"  # 5
    "tables:\n"  # 6
    "  - name: customers\n"  # 7
    "    columns:\n"  # 8
    "      - name: email\n"  # 9
    "        provider: faker\n"  # 10
    "      - name: ssn\n"  # 11
    "        provider: redact\n"  # 12
    "  - name: orders\n"  # 13
    "    columns:\n"  # 14
    "      - name: total\n"  # 15
)


def _decoy_pair() -> tuple[dict, dict]:
    """The config of `_YAML`, and a source map that gives each construct its own line."""
    config = {
        "name": "demo",
        "sources": [{"name": "src", "csv": {"path": "in.csv"}}],
        "tables": [
            {
                "name": "customers",
                "columns": [
                    {"name": "email", "provider": "faker"},
                    {"name": "ssn", "provider": "redact"},
                ],
            },
            {"name": "orders", "columns": [{"name": "total"}]},
        ],
    }
    spans = {
        ("name",): _Span(1),
        ("sources", 0): _Span(3),
        ("sources", 0, "path"): _Span(5),
        ("tables", 0): _Span(7),
        ("tables", 0, "columns", 0): _Span(9),
        ("tables", 0, "columns", 0, "provider"): _Span(10),
        ("tables", 0, "columns", 1): _Span(11),
        ("tables", 0, "columns", 1, "provider"): _Span(12),
        ("tables", 1): _Span(13),
        ("tables", 1, "columns", 0): _Span(15),
    }
    return config, spans


# Numeric, bracket and semantic spellings, a union member, and two leaves that are not there.
_PATHS = [
    "name",
    "sources.0",
    "sources[0].path",
    "sources.src",
    "tables.0",
    "tables[0].columns[1].provider",
    "tables.customers.columns.email",
    "tables.customers.columns.email.provider",
    "tables.customers.columns.ssn.provider",
    "tables.orders.columns.total",
    "tables.1.columns.0",
    "tables.customers.columns.email.namespace",
    "tables.orders.generate",
]


def test_every_exact_yaml_region_has_a_decoy_position_with_a_line() -> None:
    config, spans = _decoy_pair()
    yaml_index, decoy_index = _index(_YAML), DecoyPositionIndex(config, spans)
    exact = [p for p in _PATHS if (hit := yaml_index.locate(p)) is not None and hit.line]
    assert len(exact) >= 9  # the walk saw the paths it claims to compare
    for path in exact:
        found = decoy_index.locate(path)
        assert found is not None and found.line is not None, path


def test_decoy_lines_follow_the_construct_the_path_names() -> None:
    config, spans = _decoy_pair()
    index = DecoyPositionIndex(config, spans)
    assert index.locate("tables[0].columns[1].provider").line == 12
    assert index.locate("tables.customers.columns.email").line == 9
    assert index.locate("tables.orders").line == 13
    assert index.locate("sources[0].csv.path").line == 5  # the union member is not a segment


def test_a_missing_leaf_takes_the_nearest_construct_where_yaml_stays_file_level() -> None:
    config, spans = _decoy_pair()
    assert _index(_YAML).locate("tables.customers.columns.email.namespace") == Position()
    hit = DecoyPositionIndex(config, spans).locate("tables.customers.columns.email.namespace")
    assert hit is not None and hit.line == 9


def test_a_position_carries_the_whole_span() -> None:
    config, spans = _decoy_pair()
    assert DecoyPositionIndex(config, spans).locate("tables.customers") == Position(7, 3, 7, 7)


def test_a_duplicate_table_name_never_picks_one_of_the_two() -> None:
    config, spans = _decoy_pair()
    config["tables"].append({"name": "customers", "columns": []})
    spans[("tables", 2)] = _Span(40)
    index = DecoyPositionIndex(config, spans)
    hit = index.locate("tables.customers.columns.email")
    assert hit is None or hit.line not in (9, 40)
    assert index.locate("tables[2]").line == 40


@pytest.mark.parametrize("path", [None, "", "tables.*.x", "tables.<unknown>.x", "a..b"])
def test_decoy_paths_that_name_no_place_have_no_position(path) -> None:
    config, spans = _decoy_pair()
    assert DecoyPositionIndex(config, spans).locate(path) is None


def test_a_path_outside_every_construct_is_never_guessed() -> None:
    config, spans = _decoy_pair()
    assert DecoyPositionIndex(config, spans).locate("nothing") is None


def test_the_shared_rules_drop_the_union_member_and_walk_up() -> None:
    spans = {("tables", 0): "t0", ("sources", 0, "path"): "p", ("sources", 0): "s0"}
    assert without_union_member(("sources", 0, "csv", "path")) == ("sources", 0, "path")
    assert without_union_member(("targets", 1, "parquet")) == ("targets", 1)
    assert without_union_member(("tables", 0, "columns", 1)) == ("tables", 0, "columns", 1)
    assert without_union_member(("sources", 0)) == ("sources", 0)
    assert nearest(("tables", 0, "columns", 5, "x"), spans) == "t0"
    assert nearest(("sources", 0, "csv", "path"), spans) == "p"
    assert nearest(("nothing",), spans) is None


def test_the_decoy_index_holds_no_value_from_the_config() -> None:
    canary = "SCALAR_VALUE_CANARY_77aa"
    config, spans = _decoy_pair()
    config["name"] = canary
    assert canary not in repr(DecoyPositionIndex(config, spans))


# -- one resolver for the gate and the compiler ----------------------------------------------


def _connector_pair() -> tuple[dict, dict]:
    """A target written over three lines: the connector, then two arguments on their own lines."""
    config = {
        "targets": {"customers": {"type": "csv", "path": "out.csv", "header": True}},
        "tables": [{"name": "customers"}],
    }
    spans = {
        ("targets", "customers"): _Span(20),
        ("targets", "customers", "path"): _Span(21),
        ("targets", "customers", "header"): _Span(22),
        ("tables", 0): _Span(18),
    }
    return config, spans


def test_an_ordinary_connector_path_keeps_its_argument_segment() -> None:
    """Mutation: `without_union_member` first, so `path` is dropped and the connector line wins."""
    config, spans = _connector_pair()
    index = DecoyPositionIndex(config, spans)
    assert index.locate("targets.customers.path").line == 21
    assert index.locate("targets.customers.header").line == 22
    assert index.locate("targets.customers.type").line == 20  # no entry of its own: the connector


def test_a_union_qualified_path_still_reaches_the_argument() -> None:
    config, spans = _connector_pair()
    index = DecoyPositionIndex(config, spans)
    assert index.locate("targets.customers.csv.path").line == 21
    assert index.locate("targets.customers.csv").line == 20


def test_nearest_takes_an_exact_entry_before_dropping_a_member() -> None:
    spans = {("targets", "t"): "connector", ("targets", "t", "path"): "argument"}
    assert nearest(("targets", "t", "path"), spans) == "argument"
    assert nearest(("targets", "t", "csv", "path"), spans) == "argument"
    assert nearest(("targets", "t", "csv", "nope"), spans) == "connector"


class _StubEngineError(lang_validate.PipelineConfigError):
    def __init__(self, locations: list[str]) -> None:
        super().__init__("stub")
        self.problems = [
            type("P", (), {"location": loc, "code": "x.y", "text": "problem"})()
            for loc in locations
        ]


@pytest.mark.parametrize(
    "path",
    [
        "tables.0",  # a number inside a list is an index
        "tables[0].name",
        "tables.customers",
        "targets.0.path",  # a number that is a mapping key stays text
        "targets.0",
        "targets.customers.path",
        "targets.customers.csv.path",
        "tables.7.columns.0",  # outside the list: the nearest construct
    ],
)
def test_the_compiler_and_the_gate_select_the_same_span(path: str, monkeypatch) -> None:
    config, spans = _connector_pair()
    config["targets"]["0"] = {"type": "csv", "path": "z.csv"}
    spans[("targets", "0")] = _Span(30)
    spans[("targets", "0", "path")] = _Span(31)

    def refuse(_config: object) -> None:
        raise _StubEngineError([path])

    monkeypatch.setattr(lang_validate, "parse_pipeline_config", refuse)
    with pytest.raises(lang_validate.LangError) as caught:
        lang_validate.validate(config, spans)
    (problem,) = caught.value.diagnostics
    gate = DecoyPositionIndex(config, spans).locate(path)
    compiler = problem.span
    assert (gate is None) == (compiler is None), path
    if gate is not None and compiler is not None:
        assert (gate.line, gate.column) == (compiler.line, compiler.column), path
