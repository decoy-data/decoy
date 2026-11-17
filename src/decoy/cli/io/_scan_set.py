"""`load_scan_set`: the one reader of a saved scan, from a path or from stdin.

`decoy scan fields`, `show` and `diff` (and the CI drift check) read a scan through here
and nowhere else, so the accepted shapes and the value-free guarantee live in one place.
G-ONE-SCAN-READER (tests/sentry/test_scan_reader.py) fails when another module reads the
`scan_schema` key itself.

Only a file with a top-level `scan_schema` is read: it must carry the `scan-set/v1` major and
match the engine's read model (`ScanSetCoreRead`, which ignores fields a newer minor added). A
file without the tag (the bare `profile.to_dict()` that `decoy scan --output` wrote before
`scan-set/v1`) is refused with `SAVED_SCAN_SCHEMA_UNSUPPORTED`.

Every refusal is a `ScanSetFormatError` with a fixed message (and a code for a schema
refusal). The input text is never put in an error, because a file that is not a saved scan can
hold cell data.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

_NOT_A_SCAN = "not a saved scan Decoy can read"
_SCHEMA_MAJOR = "scan-set/v1"
_TAG_SHAPE = re.compile(r"^[A-Za-z0-9._/-]{1,32}\Z")

# Printed in the refusal, never matched on: `decoy scan` reports `code: message`.
SAVED_SCAN_SCHEMA_UNSUPPORTED = "scan.saved_scan_schema_unsupported"


class ScanSetFormatError(ValueError):
    """The input is not a saved scan this CLI can read. The message is fixed text."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message if code is None else f"{code}: {message}")
        self.code = code


def load_scan_set(path_or_dash: str) -> dict[str, Any]:
    """Read a saved scan (`-` is stdin) and return it as a `scan-set/v1` dict."""
    try:
        if path_or_dash == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(path_or_dash).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # A ValueError, not an OSError: normalised so callers that catch OSError report it
        # cleanly instead of crashing with a traceback. The decode error text is not kept.
        raise OSError("scan file is not valid UTF-8") from None
    return scan_set_from_data(json.loads(raw))


def scan_set_from_data(data: object) -> dict[str, Any]:
    """The same interpretation for an already-parsed document."""
    if not isinstance(data, dict) or _has_non_finite(data):
        raise ScanSetFormatError(_NOT_A_SCAN)
    if "scan_schema" not in data:
        raise ScanSetFormatError(
            f"the file has no scan_schema tag (expected {_SCHEMA_MAJOR}); "
            "rerun decoy scan --output to save a new one",
            SAVED_SCAN_SCHEMA_UNSUPPORTED,
        )
    return _from_core(data)


def _has_non_finite(node: object) -> bool:
    """True when a parsed document holds NaN, Infinity or an overflowed float anywhere.

    The one check for both saved formats: `json.loads` accepts the bare constants and turns
    `1e999` into infinity, and none of them is valid JSON on the way back out.
    """
    stack = [node]
    while stack:
        item = stack.pop()
        if isinstance(item, float):
            if not math.isfinite(item):
                return True
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return False


def select_table(scan_set: dict[str, Any], table: str | None) -> dict[str, Any]:
    """The one table `fields`, `show` and `diff` work on."""
    tables = scan_set["tables"]
    names = [str(t["name"]) for t in tables]
    if table is None:
        if len(tables) == 1:
            return dict(tables[0])
        raise ScanSetFormatError(
            f"the scan holds {len(tables)} tables ({', '.join(names)}); pass --table NAME"
        )
    for t in tables:
        if t["name"] == table:
            return dict(t)
    raise ScanSetFormatError(f"the scan has no table {table!r}; it holds: {', '.join(names)}")


def _from_core(data: dict[str, Any]) -> dict[str, Any]:
    from decoy_engine.profiling import ScanSetCoreRead

    tag = data.get("scan_schema")
    if not (isinstance(tag, str) and (tag == _SCHEMA_MAJOR or tag.startswith(_SCHEMA_MAJOR + "."))):
        shown = tag if isinstance(tag, str) and _TAG_SHAPE.fullmatch(tag) else "an unrecognised tag"
        raise ScanSetFormatError(
            f"scan_schema {shown} is not supported (expected {_SCHEMA_MAJOR})",
            SAVED_SCAN_SCHEMA_UNSUPPORTED,
        )
    failed = False
    try:
        model = ScanSetCoreRead.model_validate({**data, "scan_schema": _SCHEMA_MAJOR})
    except Exception:
        failed = True
    # Raised outside the handler: a validation error carries the input and must not chain.
    if failed:
        raise ScanSetFormatError(_NOT_A_SCAN)
    dumped: dict[str, Any] = model.model_dump()
    return dumped
