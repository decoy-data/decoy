"""The Decoy language: a short, readable form of a pipeline that compiles to the pipeline config.

    compiled = compile_text(source)   # parse, lower, validate with the engine
    compiled.config                   # the dict `yaml.safe_load` gives for the same pipeline
    emit_yaml(compiled.config)        # that config as YAML text

Version 1 covers pipeline settings, sources and targets, and masking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from decoy.lang._check import locate, validate
from decoy.lang._connectors import SourceMap
from decoy.lang._errors import Diagnostic, LangError, Span, render
from decoy.lang._lower import lower
from decoy.lang._parse import parse

__all__ = [
    "Compiled",
    "Diagnostic",
    "LangError",
    "Span",
    "compile_text",
    "emit_yaml",
    "locate",
    "render",
]


@dataclass(frozen=True)
class Compiled:
    config: dict[str, Any]
    source_map: SourceMap


def compile_text(text: str, *, check: bool = True) -> Compiled:
    """Compile a `.decoy` program. Raises `LangError` with every problem found.

    `check=False` skips the engine's validation and returns the config as lowered.
    """
    config, spans = lower(parse(text))
    if check:
        validate(config, spans)
    return Compiled(config, spans)


def emit_yaml(config: dict[str, Any]) -> str:
    """The compiled config as YAML, keys in the order the compiler wrote them."""
    return yaml.safe_dump(config, sort_keys=False, default_flow_style=False)
