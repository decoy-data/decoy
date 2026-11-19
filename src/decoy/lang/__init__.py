"""The Decoy language: a short, readable form of a pipeline that compiles to the pipeline config.

    compiled = compile_text(source)   # parse, lower, validate with the engine
    compiled.config                   # the dict `yaml.safe_load` gives for the same pipeline
    emit_yaml(compiled.config)        # that config as YAML text

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

from decoy.lang._connectors import SourceMap
from decoy.lang._errors import Diagnostic, LangError, Span, render
from decoy.lang._lower import lower
from decoy.lang._parse import parse
from decoy.lang._validate import validate

__all__ = [
    "Compiled",
    "Diagnostic",
    "LangError",
    "Span",
    "compile_text",
    "emit_yaml",
    "render",
]


@dataclass(frozen=True)
class Compiled:
    config: dict[str, Any]
    source_map: SourceMap


def compile_text(text: str) -> Compiled:
    """Compile a `.decoy` program: parse, lower, then the engine's own validation.

    Raises `LangError` with every problem found."""
    config, spans = lower(parse(text))
    validate(config, spans)
    return Compiled(config, spans)


def emit_yaml(config: dict[str, Any]) -> str:
    """The compiled config as YAML, keys in the order the compiler wrote them."""
    return yaml.safe_dump(config, sort_keys=False, default_flow_style=False)
