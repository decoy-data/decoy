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
from functools import lru_cache
from typing import Any

from decoy_engine import PipelineConfig, strategy_catalog

from decoy.lang import _ast as nodes
from decoy.lang._ast import plain
from decoy.lang._codes import (
    COLUMN_REPEATED,
    GENERATOR_IN_MASKED_TABLE_CALL,
    GROUP_TOO_SMALL,
    LET_MODIFIED,
    LET_REPEATED,
    LET_SHADOWS_STRATEGY,
    OPTION_NOT_AS_OPTION,
    OPTION_NOT_IN_OPTIONS,
    OPTION_NOT_IN_SETTINGS,
    OPTION_REPEATED,
    SEED_MISSING,
    SETTING_REPEATED,
    STRATEGY_ARGUMENTS,
    TABLE_REPEATED,
    UNKNOWN_STRATEGY,
)
from decoy.lang._connectors import lower_connector
from decoy.lang._errors import Diagnostic, LangError, SourceMap, diagnostic, fail
from decoy.lang._expressions import leading_call
from decoy.lang._generate import generators, lower_generate
from decoy.lang._links import CHILD_STRATEGY, relationships
from decoy.lang._safety import SAFETY_SYNTAX, lower_blocks
from decoy.lang._subset import SUBSET_SYNTAX, lower_subsets

CONFIG_VERSION = 2
KEEP_STRATEGY = "passthrough"
# Column fields the language writes with its own syntax, never as a call option.
COLUMN_SYNTAX = {
    "name": "the column name before `:`",
    "strategy": "the name of the call",
    "namespace": "`in <namespace>` after the call",
    "deterministic": "the word `deterministic` after the call",
    "vault": "the word `vaulted` after the call",
    "when": "`when <condition>` after the call",
    "provider_config": "plain `key: value` options",
    "coherent_with": "a `{a, b} : rule` group",
}
# Settings and config blocks the language writes with its own syntax, never in the generic blocks.
BLOCK_SYNTAX = {
    "version": "the `decoy 1` line; the config version is set by the compiler",
    "name": "`pipeline <name> { ... }`",
    "global_settings": "`seed`, `secret ref` and the `settings { }` block",
    "sources": "`mask <table> from ...`",
    "targets": "`mask <table> from ... to ...` or `generate <table> ... to ...`",
    "tables": "`mask` and `generate` blocks",
    "relationships": "`child <- table.key orphans <policy>`",
    **SAFETY_SYNTAX,
    **SUBSET_SYNTAX,
}
# The settings with a statement of their own: the statement's word, the engine field it sets and
# how it is written. Every other setting goes in `settings { }`.
SETTING_STATEMENTS = {
    "seed": ("seed", "`seed <number>`"),
    "secret": ("mask_secret_ref", '`secret ref("...")`'),
    "unconfigured": ("unconfigured_column_policy", "`unconfigured columns warn` or `error`"),
}
SETTING_SYNTAX = {field: written for field, written in SETTING_STATEMENTS.values()}


@lru_cache(maxsize=1)
def _strategies() -> frozenset[str]:
    return frozenset(info.name for info in strategy_catalog())


@lru_cache(maxsize=1)
def column_fields() -> frozenset[str]:
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
        key = SETTING_STATEMENTS[setting.kind][0]
        if key in settings:
            problems.append(diagnostic(SETTING_REPEATED, setting.span, setting=setting.kind))
        settings[key] = plain(setting.value)
        spans[("global_settings", key)] = setting.span
    for option in program.extra_settings:
        key = option.key.text
        if key in SETTING_SYNTAX:
            problems.append(
                diagnostic(
                    OPTION_NOT_IN_SETTINGS, option.key.span, f"use {SETTING_SYNTAX[key]}", key=key
                )
            )
        elif key in settings:
            problems.append(diagnostic(SETTING_REPEATED, option.key.span, setting=key))
        settings[key] = plain(option.value)
        spans[("global_settings", key)] = option.value.span
    if "seed" not in settings:
        problems.append(diagnostic(SEED_MISSING, program.span, "add `seed 42`"))
    config["global_settings"] = settings
    spans[("global_settings",)] = program.span

    lets = _lets(program, problems)
    config["sources"], config["tables"], config["targets"] = {}, [], {}
    links: list[tuple[str, nodes.Link]] = []
    seen_tables: set[str] = set()
    for table in program.tables:
        if table.name.text in seen_tables:
            problems.append(diagnostic(TABLE_REPEATED, table.name.span, table=table.name.text))
            continue
        seen_tables.add(table.name.text)
        try:
            if isinstance(table, nodes.Generate):
                lower_generate(table, config, spans)
            else:
                _table(table, lets, config, spans, links)
        except LangError as error:
            problems.extend(error.diagnostics)
    if links:
        targets = config.pop("targets")
        declared = [table.name.text for table in program.tables]
        config["relationships"] = relationships(links, config["tables"], declared, spans, problems)
        config["targets"] = targets
    lower_subsets(program.subsets, config, spans, problems)
    lower_blocks(program.blocks, config, spans, problems)
    for option in program.options:
        key = option.key.text
        if key in BLOCK_SYNTAX:
            problems.append(
                diagnostic(
                    OPTION_NOT_IN_OPTIONS, option.key.span, f"use {BLOCK_SYNTAX[key]}", key=key
                )
            )
        elif key in config:
            problems.append(diagnostic(OPTION_REPEATED, option.key.span, key=key))
        else:
            config[key] = plain(option.value)
            spans[(key,)] = option.value.span
    if problems:
        raise LangError(problems)
    return config, spans


def _lets(program: nodes.Program, problems: list[Diagnostic]) -> dict[str, nodes.Treatment]:
    lets: dict[str, nodes.Treatment] = {}
    for let in program.lets:
        name = let.name.text
        if name in _strategies():
            problems.append(diagnostic(LET_SHADOWS_STRATEGY, let.name.span, name=name))
        elif name in lets:
            problems.append(diagnostic(LET_REPEATED, let.name.span, name=name))
        else:
            # Resolved here, so a `let` that names an earlier `let` means that one's strategy.
            try:
                lets[name] = _resolve(let.treatment, lets)
            except LangError as error:
                problems.extend(error.diagnostics)
    return lets


def _table(
    table: nodes.Table,
    lets: dict[str, nodes.Treatment],
    config: dict[str, Any],
    spans: SourceMap,
    links: list[tuple[str, nodes.Link]],
) -> None:
    name = table.name.text
    index = len(config["tables"])
    source = lower_connector(table.source, is_source=True, path=("sources", name), spans=spans)
    target = lower_connector(table.target, is_source=False, path=("targets", name), spans=spans)
    columns: list[dict[str, Any]] = []
    seen: dict[str, nodes.Name] = {}
    linked: dict[str, nodes.Name] = {}
    position: dict[str, int] = {}  # where a linked column's entry sits, until its rule arrives
    problems: list[Diagnostic] = []
    transforms: list[dict[str, Any]] = []
    for statement in table.statements:
        if isinstance(statement, nodes.Shaping):
            step = ("tables", index, "transforms", len(transforms))
            spans[step] = statement.span
            try:
                transforms.append(_shaping(statement, step, spans))
            except LangError as error:
                problems.extend(error.diagnostics)
            continue
        is_link = isinstance(statement, nodes.Link)
        for column in statement.columns:
            # A key column may have a link and a rule of its own; anything else is said once.
            earlier = linked if is_link else seen
            if column.text in earlier:
                first = earlier[column.text].span
                problems.append(
                    diagnostic(
                        COLUMN_REPEATED,
                        column.span,
                        column=column.text,
                        what="link" if is_link else "rule",
                        line=first.line,
                    )
                )
                continue
            earlier[column.text] = column
            if is_link and column.text in seen:
                continue  # its own rule is the column entry; the link adds the relationship
            place = position.get(column.text, len(columns)) if not is_link else len(columns)
            path = ("tables", index, "columns", place)
            spans[path] = statement.span
            spans[(*path, "name")] = column.span
            try:
                if isinstance(statement, nodes.Keep):
                    entry = {"name": column.text, "strategy": KEEP_STRATEGY}
                elif isinstance(statement, nodes.Link):
                    entry = {"name": column.text, "strategy": CHILD_STRATEGY}
                    position[column.text] = place
                else:
                    entry = _column(column, statement.treatment, lets, path, spans)
                    if statement.coherent:
                        others = [c.text for c in statement.columns if c.text != column.text]
                        entry["coherent_with"] = others
            except LangError as error:
                problems.extend(error.diagnostics)
                continue
            if place < len(columns):
                columns[place] = entry  # the rule takes the place its link held
            else:
                columns.append(entry)
        if isinstance(statement, nodes.Link):
            links.append((name, statement))
        elif isinstance(statement, nodes.Mask) and statement.coherent:
            if len(statement.columns) < 2:
                problems.append(diagnostic(GROUP_TOO_SMALL, statement.span))
    if problems:
        raise LangError(problems)
    spans[("tables", index)] = table.span
    spans[("tables", index, "name")] = table.name.span
    config["sources"][name] = source
    shaped = {"transforms": transforms} if transforms else {}
    config["tables"].append({"name": name, **shaped, "columns": columns})
    config["targets"][name] = target


def _shaping(statement: nodes.Shaping, step: tuple[Any, ...], spans: SourceMap) -> dict[str, Any]:
    """A table-shaping statement as the engine's transform."""
    if isinstance(statement, nodes.Where):
        spans[(*step, "expression")] = statement.expression.span
        return {"op": "filter", "expression": statement.expression.text}
    if isinstance(statement, nodes.Define):
        called = leading_call(statement.expression.text)
        if called in generators():
            raise fail(
                GENERATOR_IN_MASKED_TABLE_CALL,
                statement.expression.span,
                "generators belong in a `generate` table",
                called=called,
            )
        spans[(*step, "column")] = statement.name.span
        spans[(*step, "expression")] = statement.expression.span
        return {
            "op": "derive",
            "column": statement.name.text,
            "expression": statement.expression.text,
        }
    if isinstance(statement, nodes.Sort):
        out: dict[str, Any] = {"op": "sort", "by": [key.column.text for key in statement.keys]}
        # The engine sorts ascending unless told otherwise, so only a descending key is stated.
        if not all(key.ascending for key in statement.keys):
            out["ascending"] = [key.ascending for key in statement.keys]
        return out
    if isinstance(statement, nodes.Limit):
        spans[(*step, "n")] = statement.count.span
        return {"op": "limit", "n": plain(statement.count)}
    columns = [column.text for column in statement.columns]
    if isinstance(statement, nodes.Drop):
        return {"op": "drop_column", "columns": columns}
    return {"op": "dedupe", "columns": columns} if columns else {"op": "dedupe"}


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
                LET_MODIFIED,
                used.span,
                "put options and settings on the `let` line, or write the strategy in full",
                name=name.text,
            )
        return lets[name.text]
    close = difflib.get_close_matches(name.text, sorted(_strategies() | set(lets)), n=1)
    raise fail(
        UNKNOWN_STRATEGY,
        name.span,
        f"did you mean `{close[0]}`?" if close else None,
        name=name.text,
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
            STRATEGY_ARGUMENTS,
            call.positional[1].span,
            "write the other values as `key: value` options",
            strategy=call.name.text,
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
        if key in COLUMN_SYNTAX:
            raise fail(OPTION_NOT_AS_OPTION, option.key.span, f"use {COLUMN_SYNTAX[key]}", key=key)
        if key in out:
            raise fail(OPTION_REPEATED, option.key.span, key=key)
        if key in column_fields():
            out[key] = plain(option.value)
            spans[(*path, key)] = option.value.span
        else:
            provider_config[key] = plain(option.value)
            spans[(*path, "provider_config", key)] = option.value.span
    if provider_config:
        out["provider_config"] = provider_config
    return out
