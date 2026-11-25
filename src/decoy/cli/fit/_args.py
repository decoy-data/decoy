"""Flag and column-type parsing for `decoy fit`: checks that run before the CSV is read."""

from __future__ import annotations

import math
from typing import Any


class _FitUsageError(Exception):
    """A pre-CSV-read validation failure: bad flag combination, malformed
    carrier declaration, or an omitted column with no `--dp-allow-omit`.
    Carries a machine-readable `code` so `--json` mode can surface it
    alongside the human message, same shape as the engine's own coded
    exceptions."""

    def __init__(self, message: str, *, code: str) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


def _parse_dp_number_spec(spec: str) -> tuple[str, tuple[float, float]]:
    """Parse one `--dp-number COL:LO:HI` spec. Validated here, before the CSV
    is read, so a malformed domain never reaches the engine (which would
    otherwise reject it only after the source file has been opened)."""
    parts = spec.split(":")
    if len(parts) != 3 or not parts[0].strip():
        raise _FitUsageError(
            f"--dp-number expects 'COL:LO:HI'; got {spec!r}.",
            code="dp_number_spec_invalid",
        )
    col, lo_raw, hi_raw = parts[0].strip(), parts[1].strip(), parts[2].strip()
    try:
        lo = float(lo_raw)
        hi = float(hi_raw)
    except ValueError:
        raise _FitUsageError(
            f"--dp-number {spec!r}: LO and HI must be numbers.",
            code="dp_number_spec_invalid",
        )
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise _FitUsageError(
            f"--dp-number {spec!r}: LO and HI must be finite.",
            code="dp_numeric_domain_invalid",
        )
    if not lo < hi:
        raise _FitUsageError(
            f"--dp-number {spec!r}: domain must satisfy LO < HI, got ({lo!r}, {hi!r}).",
            code="dp_numeric_domain_invalid",
        )
    return col, (lo, hi)


def _parse_rows(text: str) -> int:
    """`--rows` as a whole number of 1 or more. Parsed here (not by typer) so a bad value is the
    CLI's usage error (exit 1) with the same envelope as every other fit usage error."""
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value < 1:
        raise _FitUsageError("--rows must be a whole number of 1 or more.", code="fit_rows_invalid")
    return value


def _build_column_schema(
    dp_number: list[str], dp_flag: list[str], dp_text: list[str]
) -> dict[str, dict[str, Any]]:
    """Parse the repeatable carrier flags into the engine's `column_schema`
    shape. Duplicate or conflicting declarations for one column (the same
    column named twice, in the same flag or across flags) are a usage
    error -- never silently last-wins (D1 of the rewire plan)."""
    schema: dict[str, dict[str, Any]] = {}

    def _declare(raw_col: str, entry: dict[str, Any], source: str) -> None:
        col = raw_col.strip()
        if not col:
            raise _FitUsageError(f"{source}: empty column name.", code="dp_schema_column_empty")
        if col in schema:
            raise _FitUsageError(
                f"column {col!r} is declared more than once ({source} conflicts with a "
                "prior --dp-number/--dp-flag/--dp-text declaration for this column); each "
                "column may have exactly one DP carrier declaration.",
                code="dp_schema_duplicate_column",
            )
        schema[col] = entry

    for spec in dp_number:
        col, (lo, hi) = _parse_dp_number_spec(spec)
        _declare(col, {"kind": "numeric", "carrier": "number", "bounds": [lo, hi]}, "--dp-number")
    for raw_col in dp_flag:
        _declare(raw_col, {"kind": "categorical", "carrier": "flag"}, "--dp-flag")
    for raw_col in dp_text:
        _declare(raw_col, {"kind": "categorical", "carrier": "text"}, "--dp-text")
    return schema


# The fixed, case-insensitive, whitespace-trimmed flag grammar (D6 of the
# rewire plan). CSV carries no dtype, so a `--dp-flag` column arrives as
# strings; the engine's flag codec rejects strings outright (a `"1"` is not
# a flag). Every token outside this set maps to null SILENTLY -- no error,
# warning, or count may depend on a cell's content, because that would make
# a fit's success/failure a function of the data, the exact channel the
# codec's totality/boxing-invariance design closes.
_FLAG_TRUE_TOKENS = frozenset({"true", "1"})
_FLAG_FALSE_TOKENS = frozenset({"false", "0"})


def _map_flag_token(cell: object) -> bool | None:
    if cell is None:
        return None
    try:
        import pandas as pd

        if pd.isna(cell):
            return None
    except (TypeError, ValueError):
        pass
    token = str(cell).strip().lower()
    if token in _FLAG_TRUE_TOKENS:
        return True
    if token in _FLAG_FALSE_TOKENS:
        return False
    return None


def _build_typed_frame(df: Any, column_schema: dict[str, dict[str, Any]]) -> Any:
    """Convert only the declared flag columns CLI-side; number and text columns
    reach the engine as their raw CSV-string lexemes.

    The engine's flag codec (`decode_flag`) rejects strings outright, so a
    `--dp-flag` column must arrive as real bool/None cells. Its number and text
    codecs, by contrast, canonicalize per cell: `decode_number` does `float(cell)`
    (so `"1_000"`, `"01"`, unicode digits all parse), and `decode_text` requires
    a genuine `str`. Passing those columns through as raw strings is therefore
    both correct and row-independent by construction.

    CLI-side column-wide numeric conversion (e.g. `pd.to_numeric`) is deliberately
    NOT used: its int64-vs-float64 dtype choice depends on the column's other
    values, so adding one row can rebox an already-released value (e.g. a large
    integer), breaking D6 boxing invariance and stability-1."""
    out = df.copy()
    for col, spec in column_schema.items():
        if spec.get("carrier") == "flag":
            out[col] = out[col].map(_map_flag_token)
    return out
