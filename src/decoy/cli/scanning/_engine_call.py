"""The one engine call behind every scan: `decoy scan`, `decoy demo` and, later, `decoy.scan()`.

This module owns the facts the callers must agree on: the default sample size, the strategy
names, the rule that `--rows 0` reads every row, and the bytes of a saved scan. It is the only
first-party caller of the engine scan functions (`tests/sentry/scan/test_one_scan_call.py`).
It catches nothing: each caller keeps its own error text, because an engine message can quote a
cell value.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from decoy_engine import PreScanConfig
    from decoy_engine.profiling import ScanSet

DEFAULT_SCAN_ROWS: Final = 10_000


class SampleStrategy(str, Enum):
    full = "full"
    head = "head"
    random = "random"


class ScanUsageError(ValueError):
    """A bad invocation, found before any file is read. The message is fixed text plus names."""

    def __init__(self, message: str, hint_text: str | None = None) -> None:
        super().__init__(message)
        self.hint_text = hint_text


@dataclass(frozen=True)
class ScanRun:
    # Value-bearing: only the CLI summary reads it. A library caller returns `core` alone.
    result: ScanSet
    core: dict[str, Any]


def check_scan_options(rows: int | None, strategy: str) -> None:
    """Refuse a bad `rows` or `strategy` before any file is read."""
    allowed = [s.value for s in SampleStrategy]
    if strategy not in allowed:
        raise ScanUsageError(f"strategy must be one of {allowed}, got {strategy!r}.")
    if rows is not None and rows < 0:
        raise ScanUsageError(f"rows must be 0 or more, got {rows}.")


def scan_descriptors(
    descriptors: Mapping[str, dict[str, Any]],
    *,
    rows: int | None,
    strategy: str,
    pre_scan: PreScanConfig | None = None,
    on_stage: Callable[[], None] | None = None,
) -> ScanRun:
    """Scan the declared sources and build the value-free `scan-set/v1` core."""
    # Resolved at call time so a test can replace the engine functions on `decoy_engine`.
    from decoy_engine import scan_set_to_dict, scan_sources

    check_scan_options(rows, strategy)
    whole = not rows or strategy == "full"
    stage = on_stage or (lambda: None)
    result = scan_sources(
        descriptors,
        sample_rows=None if whole else rows,
        strategy="full" if whole else strategy,  # type: ignore[arg-type]
        pre_scan=pre_scan,
    )
    stage()
    core = scan_set_to_dict(result, detail=False)
    stage()
    return ScanRun(result=result, core=core)


def core_bytes(core: Mapping[str, Any]) -> bytes:
    """A saved scan file: the one serializer for `--output FILE` and the demo's `scan.json`."""
    return json.dumps(core, indent=2).encode("utf-8")
