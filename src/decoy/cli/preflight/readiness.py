"""The one import path for the readiness checks.

`decoy validate preflight` and the gate both look the checks up on this module at call
time, so a test spy patched here sees both routes. Names are bound here, not defined.
"""

from __future__ import annotations

from decoy.cli.preflight._capacity import _check_capacity
from decoy.cli.preflight._checks import (
    _check_native,
    _check_source_files,
    _check_target_overwrite,
)
from decoy.cli.preflight._result import _PreflightAccumulator

__all__ = [
    "_PreflightAccumulator",
    "_check_capacity",
    "_check_native",
    "_check_source_files",
    "_check_target_overwrite",
]
