"""What a run folder name looks like: the one rule `_layout`, `_placement`, `_pipelines` and
`_pointer` share.

A leaf module, so `_pointer` (which `_layout` imports) can test a run id without importing
`_layout` back. `decoy.cli.io` re-exports `is_run_id` for callers outside the package.
"""

from __future__ import annotations

import re

# <UTC start YYYYMMDDTHHMMSSffffffZ>-<8 hex of the invocation id>, plus 4 more hex digits per
# clash, up to all 32.
_RUN_ID = re.compile(r"[0-9]{8}T[0-9]{12}Z-[0-9a-f]{8}(?:[0-9a-f]{4}){0,6}")


def is_run_id(value: str) -> bool:
    """True when `value` is a well-formed run folder name."""
    return _RUN_ID.fullmatch(value) is not None
