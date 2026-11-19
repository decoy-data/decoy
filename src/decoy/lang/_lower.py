"""Syntax tree to the pipeline config the engine validates.

The output is a plain dict in the `PipelineConfig` shape, the same value `yaml.safe_load` gives for
a hand-written pipeline, so everything after this point is the existing path. Lowering is a pure
function of the program: the same text always gives the same dict in the same key order.

Strategy names and column fields are read from the engine (`strategy_catalog()` and the config
JSON schema), so the compiler holds no list of its own. The design follows PRQL and HCL: a
readable front-end over an existing data model, with the compiled form always available.

A source map (config path to source span) is built alongside, so that a refusal from the engine's
validation can be reported on the line that caused it.
"""

from __future__ import annotations

import difflib
import re
from functools import lru_cache
from typing import Any

from decoy_engine import PipelineConfig, strategy_catalog
from decoy_engine.config import generate_option_catalog

from decoy.lang import _ast as nodes
from decoy.lang._connectors import SourceMap, lower_connector, plain
from decoy.lang._errors import Diagnostic, LangError, fail

CONFIG_VERSION = 2
KEEP_STRATEGY = "passthrough"
# Column fields the language writes with its own syntax, never as a call option.
_OWN_SYNTAX = {
    "name": "the column name before `:`",
    "strategy": "the name of the call",
    "namespace": "`in <namespace>` after the call",
    "deterministic": "the word `deterministic` after the call",
    "vault": "the word `vaulted` after the call",
    "when": "`when <condition>` after the call",
    "provider_config": "plain `key: value` options",
}
_CALL = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\(")
_SETTING_FIELDS = {
    "seed": "seed",
    "secret": "mask_secret_ref",
    "unconfigured": "unconfigured_column_policy",
}


@lru_cache(maxsize=1)
def _strategies() -> frozenset[str]:
    return frozenset(info.name for info in strategy_catalog())


@lru_cache(maxsize=1)
def _generators() -> frozenset[str]:
    return frozenset(generate_option_catalog())


@lru_cache(maxsize=1)
def _column_fields() -> frozenset[str]:
    schema = PipelineConfig.model_json_schema()
    return frozenset(schema["$defs"]["ColumnConfig"]["properties"])


def lower(program: nodes.Program) -> tuple[dict[str, Any], SourceMap]:
    spans: SourceMap = {(): program.span}
    problems: list[Diagnostic] = []
    config: dict[str, Any] = {"version": CONFIG_VERSION}
    if program.name is not None:
        config["name"] = program.name.text
        spans[("name",)] = program.name.span

    settings: dict[str, Any] = {}
    for setting in program.settings:
        key = _SETTING_FIELDS[setting.kind]
        if key in settings:
            problems.append(
                Diagnostic("lang.setting_repeated", f"`{setting.kind}` is set twice", setting.span)
            )
        settings[key] = plain(setting.value)
        spans[("global_settings", key)] = setting.span
    if "seed" not in settings:
        problems.append(
            Diagnostic(
                "lang.seed_missing", "the pipeline has no seed", program.span, "add `seed 42`"
            )
        )
    config["global_settings"] = settings
    spans[("global_settings",)] = program.span

    lets = _lets(program, problems)
    config["sources"], config["tables"], config["targets"] = {}, [], {}
    seen_tables: set[str] = set()
    for table in program.tables:
        if table.name.text in seen_tables:
            problems.append(
                Diagnostic(
                    "lang.table_repeated",
                    f"table `{table.name.text}` is declared twice",
                    table.name.span,
                )
            )
            continue
        seen_tables.add(table.name.text)
        try:
            _table(table, lets, config, spans)
        except LangError as error:
            problems.extend(error.diagnostics)
    if problems:
        raise LangError(problems)
    return config, spans


def _lets(program: nodes.Program, problems: list[Diagnostic]) -> dict[str, nodes.Treatment]:
    lets: dict[str, nodes.Treatment] = {}
    for let in program.lets:
        name = let.name.text
        if name in _strategies():
            problems.append(
                Diagnostic(
                    "lang.let_shadows_strategy",
                    f"`{name}` is a strategy and cannot be reused as a `let` name",
                    let.name.span,
                )
            )
        elif name in lets:
            problems.append(
                Diagnostic("lang.let_repeated", f"`{name}` is defined twice", let.name.span)
            )
        else:
            lets[name] = let.treatment
    return lets


def _table(
    table: nodes.Table,
    lets: dict[str, nodes.Treatment],
    config: dict[str, Any],
    spans: SourceMap,
) -> None:
    name = table.name.text
    index = len(config["tables"])
    source = lower_connector(table.source, is_source=True, path=("sources", name), spans=spans)
    target = lower_connector(table.target, is_source=False, path=("targets", name), spans=spans)
    columns: list[dict[str, Any]] = []
    seen: dict[str, nodes.Name] = {}
    problems: list[Diagnostic] = []
    transforms: list[dict[str, Any]] = []
    for statement in table.statements:
        if isinstance(statement, nodes.Transform):
            step = ("tables", index, "transforms", len(transforms))
            spans[step] = statement.span
            transforms.append({"op": statement.op})
            for key, value, span in statement.fields:
                transforms[-1][key] = value
                spans[(*step, key)] = span
                called = _CALL.match(value) if key == "expression" else None
                if statement.op == "derive" and called and called[1] in _generators():
                    problems.append(
                        Diagnostic(
                            "lang.generator_in_masked_table",
                            f"`{called[1]}` is a generator; a masked table can only define a "
                            "column from an expression",
                            span,
                            "generators belong in a `generate` table",
                        )
                    )
            continue
        for column in statement.columns:
            if column.text in seen:
                first = seen[column.text].span
                problems.append(
                    Diagnostic(
                        "lang.column_repeated",
                        f"column `{column.text}` already has a rule on line {first.line}",
                        column.span,
                    )
                )
                continue
            seen[column.text] = column
            path = ("tables", index, "columns", len(columns))
            spans[path] = statement.span
            spans[(*path, "name")] = column.span
            try:
                if isinstance(statement, nodes.Keep):
                    columns.append({"name": column.text, "strategy": KEEP_STRATEGY})
                else:
                    columns.append(_column(column, statement.treatment, lets, path, spans))
            except LangError as error:
                problems.extend(error.diagnostics)
    if problems:
        raise LangError(problems)
    spans[("tables", index)] = table.span
    spans[("tables", index, "name")] = table.name.span
    config["sources"][name] = source
    shaped = {"transforms": transforms} if transforms else {}
    config["tables"].append({"name": name, **shaped, "columns": columns})
    config["targets"][name] = target


def _resolve(used: nodes.Treatment, lets: dict[str, nodes.Treatment]) -> nodes.Treatment:
    """The treatment a column rule names: itself, or the `let` it refers to."""
    name = used.call.name
    if name.text in _strategies():
        return used
    if name.text in lets:
        if (
            used.call.has_parens
            or used.namespace
            or used.deterministic
            or used.vaulted
            or used.when
        ):
            raise fail(
                "lang.let_modified",
                f"`{name.text}` is a `let` name and is used as it is",
                used.span,
                "put options and settings on the `let` line, or write the strategy in full",
            )
        return lets[name.text]
    close = difflib.get_close_matches(name.text, sorted(_strategies() | set(lets)), n=1)
    raise fail(
        "lang.unknown_strategy",
        f"`{name.text}` is not a strategy or a `let` name",
        name.span,
        f"did you mean `{close[0]}`?" if close else None,
    )


def _column(
    column: nodes.Name,
    used: nodes.Treatment,
    lets: dict[str, nodes.Treatment],
    path: tuple[Any, ...],
    spans: SourceMap,
) -> dict[str, Any]:
    treatment = _resolve(used, lets)
    call = treatment.call
    out: dict[str, Any] = {"name": column.text, "strategy": call.name.text}
    spans[(*path, "strategy")] = call.name.span
    if len(call.positional) > 1:
        raise fail(
            "lang.strategy_arguments",
            f"`{call.name.text}` takes at most one plain value, the provider",
            call.positional[1].span,
            "write the other values as `key: value` options",
        )
    if call.positional:
        out["provider"] = plain(call.positional[0])
        spans[(*path, "provider")] = call.positional[0].span
    if treatment.namespace is not None:
        out["namespace"] = treatment.namespace.text
        spans[(*path, "namespace")] = treatment.namespace.span
    if treatment.deterministic:
        out["deterministic"] = True
    if treatment.vaulted:
        out["vault"] = True
    if treatment.when is not None:
        out["when"] = treatment.when.text
        spans[(*path, "when")] = treatment.when.span
    provider_config: dict[str, Any] = {}
    for option in call.options:
        key = option.key.text
        if key in _OWN_SYNTAX:
            raise fail(
                "lang.option_not_allowed",
                f"`{key}` is not written as an option",
                option.key.span,
                f"use {_OWN_SYNTAX[key]}",
            )
        if key in out:
            raise fail("lang.option_repeated", f"`{key}` is given twice", option.key.span)
        if key in _column_fields():
            out[key] = plain(option.value)
            spans[(*path, key)] = option.value.span
        else:
            provider_config[key] = plain(option.value)
            spans[(*path, "provider_config", key)] = option.value.span
    if provider_config:
        out["provider_config"] = provider_config
    return out
