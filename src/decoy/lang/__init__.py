"""The Decoy language: a short, readable form of a pipeline that compiles to the pipeline config.

    compiled = compile_text(source)   # parse, lower, validate with the engine
    compiled.config                   # the dict `yaml.safe_load` gives for the same pipeline
    emit_yaml(compiled.config)        # that config as YAML text
    convert_config(config)            # the other way: a config as `.decoy` text, checked
    format_text(source)               # the program in the canonical layout, comments kept

Built so far: pipeline settings, sources and targets, masking with `when` conditions, table
shaping (`where`, `name = expression`, `sort by`, `limit`, `dedupe`, `drop`), foreign keys (`<-`),
coherent groups (`{a, b} : rule`), generated tables (`generate name rows N`), checks and safety
statements (`scan`, `expect`, `quarantine`, `baseline`, `delivery`, `namespace`), `subset { }`, `settings { }` for
any pipeline setting and `options { }` for config blocks without syntax of their own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from decoy.lang._ast import Program, Table
from decoy.lang._codes import CODES, NESTING, UNREVIEWED
from decoy.lang._convert import ConvertError, convert_config
from decoy.lang._errors import Diagnostic, LangError, SourceMap, Span, diagnostic, render
from decoy.lang._format import format_text
from decoy.lang._lower import lower
from decoy.lang._parse import parse
from decoy.lang._validate import validate

__all__ = [
    "CODES",
    "Compiled",
    "ConvertError",
    "Diagnostic",
    "LangError",
    "Lowered",
    "Span",
    "compile_text",
    "convert_config",
    "emit_yaml",
    "format_text",
    "lower_text",
    "render",
]


@dataclass(frozen=True)
class Compiled:
    config: dict[str, Any]
    source_map: SourceMap


@dataclass(frozen=True)
class Lowered:
    """A program that parsed and lowered: its config, where each part came from, and one
    `lang.unreviewed` diagnostic for each rule that still ends with `?`. The config is not yet
    checked by the engine."""

    config: dict[str, Any]
    source_map: SourceMap
    unreviewed: tuple[Diagnostic, ...]


def _marks(program: Program) -> tuple[Diagnostic, ...]:
    return tuple(
        diagnostic(UNREVIEWED, s.span, "check the rule, then remove the `?`")
        for table in program.tables
        if isinstance(table, Table)
        for s in table.statements
        if getattr(s, "unreviewed", False)
    )


def lower_text(text: str) -> Lowered:
    """Parse and lower a `.decoy` program, with no engine validation.

    A parse failure raises its syntax problems. A lowering failure raises the lowering problems
    followed by the marks: the program parsed, so the marks are known and a caller sees every
    problem at once. Success returns the marks as data, so the caller decides what they mean."""
    try:
        program = parse(text)
        try:
            config, spans = lower(program)
        except LangError as failure:
            lowering = failure
        else:
            return Lowered(config, spans, _marks(program))
    except RecursionError:
        too_deep = LangError([diagnostic(NESTING)])
    else:
        # Raised outside the handler so the lowering error is not attached as context.
        raise LangError([*lowering.diagnostics, *_marks(program)])
    raise too_deep


def compile_text(text: str) -> Compiled:
    """Compile a `.decoy` program: parse, lower, then the engine's own validation.

    Raises `LangError` with every problem found. A rule that still ends with `?` is a problem
    too, reported last, so no caller is handed a config for a pipeline nobody has checked."""
    lowered = lower_text(text)
    validate(lowered.config, lowered.source_map)
    if lowered.unreviewed:
        raise LangError(list(lowered.unreviewed))
    return Compiled(lowered.config, lowered.source_map)


def emit_yaml(config: dict[str, Any]) -> str:
    """The compiled config as YAML, keys in the order the compiler wrote them."""
    try:
        return yaml.safe_dump(config, sort_keys=False, default_flow_style=False)
    except RecursionError:
        too_deep = LangError([diagnostic(NESTING)])
    raise too_deep
