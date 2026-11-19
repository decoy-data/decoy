"""Pipeline config to `.decoy` text: the inverse of lowering.

`convert_config` builds the syntax tree a program for this config would parse to, prints it, and
then proves the result: the text is compiled and the engine's model of the compiled config must
equal the engine's model of the input. A config the language cannot write faithfully is refused
with `ConvertError`; no approximation is returned, because a converted pipeline that masks
differently is a data-safety defect. This is the round-trip discipline of a decompiler or of
`gofmt -r`: the output is only trusted because it is checked against the input.

Everything here reads the same tables lowering uses (`SHAPES`, `PREDICATES`, `RENAMES`,
`CONNECTORS`, the syntax tables, the engine's generator catalog), so the two directions cannot
drift apart without the round-trip tests failing.
"""

from __future__ import annotations

import copy
import math
from decimal import Decimal
from typing import Any

from decoy_engine import parse_pipeline_config
from decoy_engine.config import PipelineConfigError

from decoy.lang import _ast as nodes
from decoy.lang._connectors import CONNECTORS, FORMATS, RENAMES
from decoy.lang._errors import LangError, Span
from decoy.lang._expressions import canonical_expression
from decoy.lang._generate import generators
from decoy.lang._links import CHILD_STRATEGY
from decoy.lang._lower import (
    BLOCK_SYNTAX,
    COLUMN_SYNTAX,
    CONFIG_VERSION,
    KEEP_STRATEGY,
    SETTING_STATEMENTS,
    SETTING_SYNTAX,
    column_fields,
    lower,
)
from decoy.lang._parse import parse
from decoy.lang._print import print_program
from decoy.lang._safety import SHAPES
from decoy.lang._subset import PREDICATES
from decoy.lang._validate import validate

NOWHERE = Span(0, 0, 0, 0)
_SPELLING = {engine: written for written, engine in PREDICATES.items()}
_OPTION_NAME = {engine: written for written, engine in RENAMES.items()}
_STATEMENT = {field: word for word, (field, _) in SETTING_STATEMENTS.items()}


class ConvertError(Exception):
    """A config that cannot be written as a `.decoy` program. `path` names the config location
    and `message` holds no value from the config."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}" if path else message)
        self.path = path
        self.message = message


def _name(text: str) -> nodes.Name:
    return nodes.Name(str(text), NOWHERE)


def _names(items: list[str]) -> tuple[nodes.Name, ...]:
    return tuple(_name(item) for item in items)


def _value(item: Any, path: str) -> nodes.Value:
    if isinstance(item, dict):
        if not all(isinstance(key, str) for key in item):
            raise ConvertError(path, "a map key that is not text cannot be written")
        return nodes.Value({k: _value(v, f"{path}.{k}") for k, v in item.items()}, NOWHERE)
    if isinstance(item, (list, tuple)):
        return nodes.Value(tuple(_value(v, f"{path}[{i}]") for i, v in enumerate(item)), NOWHERE)
    if item is None or (isinstance(item, float) and not math.isfinite(item)):
        raise ConvertError(path, "a null or non-finite value cannot be written")
    if not isinstance(item, (str, int, float, bool)):
        raise ConvertError(path, "this kind of value cannot be written")
    return nodes.Value(item, NOWHERE)


def _options(items: dict[str, Any], path: str) -> tuple[nodes.Option, ...]:
    return tuple(
        nodes.Option(_name(key), _value(item, f"{path}.{key}")) for key, item in items.items()
    )


def _call(word: str, positional: list[Any], options: dict[str, Any], path: str) -> nodes.Call:
    values = tuple(_value(item, path) for item in positional)
    return nodes.Call(
        _name(word), values, _options(options, path), bool(values or options), NOWHERE
    )


def _expression(text: Any, path: str) -> nodes.Expression:
    if not isinstance(text, str):
        raise ConvertError(path, "an expression must be text")
    try:
        return nodes.Expression(canonical_expression(text), NOWHERE)
    except LangError:
        failure = ConvertError(path, "this expression cannot be written in the language")
    raise failure


def _connector(entry: dict[str, Any], *, is_source: bool, path: str) -> nodes.Call:
    """`csv("in.csv")` for a source or target entry."""
    rest = dict(entry)
    kind, declared = rest.pop("type", None), rest.pop("format", None)
    for word, connector in CONNECTORS.items():
        if connector.type != kind or connector.format not in (None, declared):
            continue
        if not all(key in rest for key in connector.positional):
            continue
        positional = [rest.pop(key) for key in connector.positional]
        if is_source:
            for key, default in connector.source_defaults.items():
                if rest.get(key) == default:
                    del rest[key]
        options = {_OPTION_NAME.get(key, key): item for key, item in rest.items()}
        located = str(positional[-1]).lower()
        if connector.format is None and FORMATS.get(located[located.rfind(".") :]) != declared:
            options["format"] = declared
        return _call(word, positional, options, path)
    raise ConvertError(path, "this kind of source or target has no connector in the language")


def _treatment(column: dict[str, Any], path: str) -> nodes.Treatment:
    rest = {k: v for k, v in column.items() if k not in ("name", "coherent_with") and v is not None}
    strategy = rest.pop("strategy")
    provider = rest.pop("provider", None)
    namespace = rest.pop("namespace", None)
    deterministic, vaulted = rest.pop("deterministic", False), rest.pop("vault", False)
    when = rest.pop("when", None)
    provider_config = rest.pop("provider_config", {})
    clash = sorted(set(provider_config) & (column_fields() | set(COLUMN_SYNTAX)))
    if clash:
        raise ConvertError(
            f"{path}.provider_config.{clash[0]}",
            "a provider option with the name of a column setting cannot be written",
        )
    call = _call(
        strategy, [] if provider is None else [provider], {**rest, **provider_config}, path
    )
    return nodes.Treatment(
        call,
        _name(namespace) if namespace is not None else None,
        bool(deterministic),
        bool(vaulted),
        _expression(when, f"{path}.when") if when else None,
        NOWHERE,
    )


def _shaping(op: dict[str, Any], path: str) -> nodes.Shaping:
    kind = op["op"]
    if kind == "filter":
        return nodes.Where(_expression(op["expression"], f"{path}.expression"), NOWHERE)
    if kind == "derive":
        expression = _expression(op["expression"], f"{path}.expression")
        return nodes.Define(_name(op["column"]), expression, NOWHERE)
    if kind == "limit":
        return nodes.Limit(_value(op["n"], f"{path}.n"), NOWHERE)
    if kind == "drop_column":
        return nodes.Drop(_names(op["columns"]), NOWHERE)
    if kind == "dedupe":
        return nodes.Dedupe(_names(op.get("columns") or []), NOWHERE)
    ascending = op.get("ascending", True)
    if isinstance(ascending, bool):
        ascending = [ascending] * len(op["by"])
    keys = zip(op["by"], ascending, strict=True)
    return nodes.Sort(tuple(nodes.SortKey(_name(c), bool(up)) for c, up in keys), NOWHERE)


def _mask_table(table: dict[str, Any], index: int, config: dict[str, Any]) -> nodes.Table:
    name, path = table["name"], f"tables[{index}]"
    if name not in config.get("sources", {}) or name not in config.get("targets", {}):
        raise ConvertError(path, "a masked table needs both a source and a target")
    statements: list[Any] = [
        _shaping(op, f"{path}.transforms[{i}]") for i, op in enumerate(table.get("transforms", []))
    ]
    links = _links_of(name, config)
    columns = table.get("columns", [])
    grouped: set[str] = set()
    for position, column in enumerate(columns):
        column_path = f"{path}.columns[{position}]"
        column_name = column["name"]
        if column_name in grouped:
            continue
        rule = {k: v for k, v in column.items() if k != "name"}
        previous = statements[-1] if statements else None
        if column.get("coherent_with"):
            members = [column_name, *column["coherent_with"]]
            grouped.update(members)
            treatment = _treatment(column, column_path)
            statements.append(nodes.Mask(_names(members), treatment, NOWHERE, coherent=True))
        elif rule == {"strategy": CHILD_STRATEGY}:
            pass  # the link below is its whole statement
        elif rule == {"strategy": KEEP_STRATEGY}:
            if isinstance(previous, nodes.Keep):
                statements[-1] = nodes.Keep((*previous.columns, _name(column_name)), NOWHERE)
            else:
                statements.append(nodes.Keep((_name(column_name),), NOWHERE))
        else:
            treatment = _treatment(column, column_path)
            same = (
                isinstance(previous, nodes.Mask)
                and not previous.coherent
                and previous.treatment == treatment
            )
            if same:
                merged = (*previous.columns, _name(column_name))
                statements[-1] = nodes.Mask(merged, treatment, NOWHERE)
            else:
                statements.append(nodes.Mask((_name(column_name),), treatment, NOWHERE))
        statements.extend(link for first, link in links if first == column_name)
    return nodes.Table(
        _name(name),
        _connector(config["sources"][name], is_source=True, path=f"sources.{name}"),
        _connector(config["targets"][name], is_source=False, path=f"targets.{name}"),
        tuple(statements),
        NOWHERE,
    )


def _links_of(table: str, config: dict[str, Any]) -> list[tuple[str, nodes.Link]]:
    """Each foreign key whose child is `table`, with the child column it is written after."""
    found = []
    parents = {t["name"]: {c["name"]: c for c in t.get("columns", [])} for t in config["tables"]}
    for relationship in config.get("relationships", []):
        parent = relationship["parent"]
        for child in relationship["children"]:
            if child["table"] != table:
                continue
            namespace = relationship.get("namespace")
            inherited = parents.get(parent["table"], {}).get(parent["columns"][0], {})
            link = nodes.Link(
                _names(child["columns"]),
                _name(parent["table"]),
                _names(parent["columns"]),
                # Written only when it is not the one the link would take from the parent key.
                _name(namespace) if namespace and namespace != inherited.get("namespace") else None,
                _name(relationship["orphan_policy"]),
                NOWHERE,
            )
            found.append((child["columns"][-1], link))
    return found


def _generate_table(table: dict[str, Any], index: int, config: dict[str, Any]) -> nodes.Generate:
    name, path = table["name"], f"tables[{index}]"
    if name not in config.get("targets", {}) or table.get("transforms"):
        raise ConvertError(path, "a generated table needs a target and takes no transforms")
    statements: list[Any] = []
    for position, column in enumerate(table["generate_columns"]):
        column_path = f"{path}.generate_columns[{position}]"
        rest = {k: v for k, v in column.items() if k not in ("name", "type") and v is not None}
        kind, column_name = column["type"], _name(column["name"])
        if kind == "reference" and set(rest) == {"reference_table", "reference_column"}:
            statements.append(
                nodes.GenLink(
                    column_name,
                    _name(rest["reference_table"]),
                    _name(rest["reference_column"]),
                    NOWHERE,
                )
            )
            continue
        if kind == "derived" and set(rest) == {"expression"}:
            expression = _expression(rest["expression"], f"{column_path}.expression")
            statements.append(nodes.GenColumn(column_name, None, expression, NOWHERE))
            continue
        positional: list[Any] = []
        categories = rest.get("categories")
        weighted = (
            kind == "categorical"
            and isinstance(categories, list)
            and isinstance(rest.get("weights"), list)
            and len(categories) == len(rest["weights"])
            and all(isinstance(c, str) for c in categories)
            and len(set(categories)) == len(categories)
        )
        if weighted:
            positional.append(dict(zip(rest.pop("categories"), rest.pop("weights"), strict=True)))
        else:
            for key in generators().get(kind, ()):
                if key not in rest:
                    break
                positional.append(rest.pop(key))
        call = _call(kind, positional, rest, column_path)
        call = nodes.Call(call.name, call.positional, call.options, True, NOWHERE)
        statements.append(nodes.GenColumn(column_name, call, None, NOWHERE))
    statements.extend(
        nodes.Unique(_names(pair), NOWHERE) for pair in table.get("unique_together", [])
    )
    return nodes.Generate(
        _name(name),
        _value(table["row_count"], f"{path}.row_count"),
        _connector(config["targets"][name], is_source=False, path=f"targets.{name}"),
        tuple(statements),
        NOWHERE,
    )


def _blocks(config: dict[str, Any]) -> tuple[nodes.Block, ...]:
    blocks = []
    for kind, shape in SHAPES.items():
        if shape.key not in config:
            continue
        rest = dict(config[shape.key])
        for key, fixed in shape.fixed.items():
            if rest.pop(key, None) != fixed:
                raise ConvertError(
                    f"{shape.key}.{key}", "this setting has one value in the language"
                )
        positional: list[Any] = []
        if shape.variadic is not None:
            positional = list(rest.pop(shape.variadic, []))
        else:
            for key in shape.positional:
                if key not in rest:
                    break
                positional.append(rest.pop(key))
        call = _call(kind, positional, rest, shape.key)
        blocks.append(nodes.Block(kind, None, call.positional, (), call.options, NOWHERE))
    for index, entry in enumerate(config.get("validators", [])):
        refs = tuple(
            nodes.Ref(_name(table), _name(column), NOWHERE)
            for table, columns in entry.get("columns", {}).items()
            for column in columns
        )
        options = _options(entry.get("params", {}), f"validators[{index}].params")
        blocks.append(nodes.Block("expect", _name(entry["name"]), (), refs, options, NOWHERE))
    for name, entry in config.get("namespaces", {}).items():
        declared = [item.split(".", 1) for item in entry.get("declared_by", [])]
        if not declared or any(len(parts) != 2 for parts in declared):
            raise ConvertError(
                f"namespaces.{name}", "a namespace is declared for `table.column` names"
            )
        refs = tuple(nodes.Ref(_name(table), _name(column), NOWHERE) for table, column in declared)
        blocks.append(nodes.Block("namespace", _name(name), (), refs, (), NOWHERE))
    return tuple(blocks)


def _edge_end(text: str) -> tuple[nodes.Name, tuple[nodes.Name, ...]]:
    table, _, columns = text.partition(".")
    return _name(table), _names(columns.split(","))


def _subset(subset: dict[str, Any]) -> nodes.Subset:
    seeds = []
    for index, seed in enumerate(subset["seeds"]):
        path = f"subset.seeds[{index}]"
        keys, conditions, amount, unit = None, [], None, None
        if seed["mode"] == "sample" and seed.get("fraction") is not None:
            percent = Decimal(repr(float(seed["fraction"]))) * 100
            whole = percent == percent.to_integral_value()
            amount, unit = _value(int(percent) if whole else float(percent), path), "%"
        elif seed["mode"] == "sample":
            amount, unit = _value(seed.get("count"), path), "rows"
        elif seed["mode"] == "keys":
            single = len(seed["key_columns"]) == 1
            rows = [row[0] if single and len(row) == 1 else row for row in seed["keys"]]
            keys = _value(rows, f"{path}.keys")
        for position, predicate in enumerate(seed.get("predicates", [])):
            operand = predicate.get("value")
            takes_value = not predicate["op"].startswith("is_")
            if takes_value == (operand is None):
                raise ConvertError(f"{path}.predicates[{position}]", "this test cannot be written")
            conditions.append(
                nodes.Condition(
                    _name(predicate["column"]),
                    _SPELLING[predicate["op"]],
                    _value(operand, path) if takes_value else None,
                    NOWHERE,
                )
            )
        seeds.append(
            nodes.Seed(
                _name(seed["table"]),
                seed["mode"],
                _names(seed.get("key_columns", [])),
                amount,
                unit,
                tuple(conditions),
                keys,
                NOWHERE,
            )
        )
    follows = []
    for edge, direction in subset.get("edge_directions", {}).items():
        parent, arrow, child = edge.partition(" -> ")
        if not arrow or "." not in parent or "." not in child:
            raise ConvertError("subset.edge_directions", "an edge is `parent.key -> child.key`")
        follows.append(
            nodes.Follow(*_edge_end(parent), *_edge_end(child), _name(direction), NOWHERE)
        )
    return nodes.Subset(
        tuple(seeds),
        tuple(follows),
        _options(subset.get("budget", {}), "subset.budget"),
        bool(subset.get("allow_dangling", False)),
        NOWHERE,
    )


def _program(config: dict[str, Any]) -> nodes.Program:
    if config.get("version") != CONFIG_VERSION:
        raise ConvertError("version", f"only config version {CONFIG_VERSION} can be converted")
    settings = dict(config["global_settings"])
    statements = tuple(
        nodes.Setting(_STATEMENT[key], _value(settings.pop(key), f"global_settings.{key}"), NOWHERE)
        for key in SETTING_SYNTAX
        if settings.get(key) is not None
    )
    tables = [
        _generate_table(table, index, config)
        if table.get("generate_columns")
        else _mask_table(table, index, config)
        for index, table in enumerate(config["tables"])
    ]
    known = {table["name"] for table in config["tables"]}
    for block in ("sources", "targets"):
        stray = sorted(set(config.get(block, {})) - known)
        if stray:
            raise ConvertError(
                f"{block}.{stray[0]}", "this entry is for a table that is not declared"
            )
    leftover = {key: item for key, item in config.items() if key not in BLOCK_SYNTAX}
    return nodes.Program(
        _name(config["name"]) if config.get("name") else None,
        statements,
        (),
        tuple(tables),
        NOWHERE,
        _options({k: v for k, v in settings.items() if v is not None}, "global_settings"),
        _options(leftover, ""),
        _blocks(config),
        (_subset(config["subset"]),) if config.get("subset") else (),
    )


def _normalized(config: dict[str, Any]) -> dict[str, Any]:
    """The config with the spellings the engine treats as equal made equal, for comparison:
    expressions spaced as the compiler writes them, and a sort direction as one entry per key."""
    out = copy.deepcopy(config)
    for table in out.get("tables", []):
        for op in table.get("transforms", []):
            if isinstance(op.get("expression"), str):
                op["expression"] = canonical_expression(op["expression"])
            if op.get("op") == "sort":
                ascending = op.pop("ascending", True)
                if isinstance(ascending, bool):
                    ascending = [ascending] * len(op.get("by", []))
                if not all(ascending):
                    op["ascending"] = ascending
        for column in table.get("columns", []):
            if column.get("when"):
                column["when"] = canonical_expression(column["when"])
        for column in table.get("generate_columns", []):
            if column.get("type") == "derived" and isinstance(column.get("expression"), str):
                column["expression"] = canonical_expression(column["expression"])
    return out


def _model(config: dict[str, Any], path: str) -> dict[str, Any]:
    try:
        return parse_pipeline_config(copy.deepcopy(config)).model_dump()
    except PipelineConfigError:
        failure = ConvertError(path, "the config does not validate")
    raise failure


def convert_config(config: dict[str, Any]) -> str:
    """The `.decoy` program for a pipeline config, checked to compile back to the same pipeline."""
    wanted = _model(config, "")
    try:
        text = print_program(_program(config))
        compiled, spans = lower(parse(text))
        validate(compiled, spans)
        wanted = _model(_normalized(config), "")
    except (LangError, RecursionError):
        failure = ConvertError("", "the language cannot write this config")
    else:
        if _model(_normalized(compiled), "") == wanted:
            return text
        failure = ConvertError("", "the program for this config would not compile back to it")
    raise failure
