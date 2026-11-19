"""Engine validation of a compiled config, reported on source lines.

The engine's `parse_pipeline_config` stays the only validator, and its problems are value-free:
codes, locations and text that never quote the config. This module runs it and translates each
problem's location into the source span recorded during lowering, the way Elm and Rust report a
type error on the expression that caused it rather than on the generated code.
"""

from __future__ import annotations

import re
from typing import Any

from decoy_engine import parse_pipeline_config
from decoy_engine.config import PipelineConfigError

from decoy.lang._errors import Diagnostic, LangError, SourceMap, Span

_WHEN_HINT = (
    "a condition compares one column with a value (`country == 'US'`) or tests a list "
    "(`state in ['CA', 'NY']`), joined with `and`, `or`, `not`; inside a condition, true and false "
    "are written `True` and `False`"
)
_STEP = re.compile(r"\[(\d+)\]|([^.\[\]]+)")


def path_of(location: str) -> tuple[Any, ...]:
    """An engine problem location (`tables[0].columns[2].namespace`) as a config path."""
    return tuple(int(index) if index else key for index, key in _STEP.findall(location))


def locate(path: tuple[Any, ...], spans: SourceMap) -> Span | None:
    """The span of the nearest construct that produced `path`."""
    # The engine names the chosen member of a source or target union inside the path.
    if len(path) > 2 and path[0] in ("sources", "targets"):
        path = (*path[:2], *path[3:])
    while path and path not in spans:
        path = path[:-1]
    return spans.get(path)


def validate(config: dict[str, Any], spans: SourceMap) -> None:
    try:
        parse_pipeline_config(config)
    except PipelineConfigError as error:
        problems = []
        for problem in error.problems:
            path = path_of(problem.location)
            hint = _WHEN_HINT if path and path[-1] == "when" else None
            text = f"{problem.text} [{problem.code}]"
            problems.append(Diagnostic("lang.config", text, locate(path, spans), hint))
    else:
        return
    # Raised outside the handler so the engine error is not attached as context.
    raise LangError(problems)
