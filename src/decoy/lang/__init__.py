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

from decoy.lang._ast import Table
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
    "Span",
    "compile_text",
    "convert_config",
    "emit_yaml",
    "format_text",
    "render",
]


@dataclass(frozen=True)
class Compiled:
    config: dict[str, Any]
    source_map: SourceMap


def compile_text(text: str) -> Compiled:
    """Compile a `.decoy` program: parse, lower, then the engine's own validation.

    Raises `LangError` with every problem found. A rule that still ends with `?` is a problem
    too, reported last, so no caller is handed a config for a pipeline nobody has checked."""
    try:
        program = parse(text)
        config, spans = lower(program)
    except RecursionError:
        too_deep = LangError([diagnostic(NESTING)])
    else:
        validate(config, spans)
        marked = [
            diagnostic(UNREVIEWED, s.span, "check the rule, then remove the `?`")
            for table in program.tables
            if isinstance(table, Table)
            for s in table.statements
            if getattr(s, "unreviewed", False)
        ]
        if marked:
            raise LangError(marked)
        return Compiled(config, spans)
    raise too_deep


def emit_yaml(config: dict[str, Any]) -> str:
    """The compiled config as YAML, keys in the order the compiler wrote them."""
    try:
        return yaml.safe_dump(config, sort_keys=False, default_flow_style=False)
    except RecursionError:
        too_deep = LangError([diagnostic(NESTING)])
    raise too_deep
