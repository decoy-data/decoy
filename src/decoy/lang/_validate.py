"""Engine validation of a compiled config, reported on source lines.

The engine's `parse_pipeline_config` stays the only validator, and its problems are value-free:
codes, locations and text that never quote the config. This module runs it and translates each
problem's location into the source span recorded during lowering, the way Elm and Rust report a
type error on the expression that caused it rather than on the generated code.
"""

from __future__ import annotations

from typing import Any

from decoy_engine import parse_pipeline_config
from decoy_engine.config import PipelineConfigError

from decoy._source_positions import nearest, segments
from decoy.lang._codes import CONFIG
from decoy.lang._errors import LangError, SourceMap, diagnostic

_WHEN_HINT = (
    "a condition compares one column with a value (`country == 'US'`) or tests a list "
    "(`state in ['CA', 'NY']`), joined with `and`, `or`, `not`; inside a condition, true and false "
    "are written `True` and `False`"
)


def _key(location: str) -> tuple[Any, ...]:
    """An engine problem location (`tables[0].columns[2].namespace`) as a source-map key."""
    parts = segments(location) or ()
    return tuple(int(p) if p.isascii() and p.isdigit() else p for p in parts)


def validate(config: dict[str, Any], spans: SourceMap) -> None:
    try:
        parse_pipeline_config(config)
    except PipelineConfigError as error:
        problems = []
        for problem in error.problems:
            path = _key(problem.location)
            hint = _WHEN_HINT if path and path[-1] == "when" else None
            text = f"{problem.text} [{problem.code}]"
            problems.append(diagnostic(CONFIG, nearest(path, spans), hint, text=text))
    else:
        return
    # Raised outside the handler so the engine error is not attached as context.
    raise LangError(problems)
