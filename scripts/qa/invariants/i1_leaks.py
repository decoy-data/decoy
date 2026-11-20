"""I1: no original value survives where the column's strategy replaces it (plan 5.5, rev 3.3).

Cell rules run per column by the config's strategy. Text surfaces get the needles sweep
(`scripts/qa/sweep.py`), not this module. The documented exceptions come from
`docs/qa/surfaces.toml`, and `EXCEPTION_RULES` must name every one of them (a consistency test
fails otherwise), so a new exception cannot be added without a rule and a pass case.

An exact-cell check is used only where the output domain cannot overlap the input by
construction. Anywhere else a correct run can land on another row's input value, so the check
would cry wolf:
- `hash`, `tokenize`, `redact`: same-row plus exact-cell (the output equals no input cell of the
  column). `faker` gets the same pair over marker inputs only; marker cells are ours, so a faker
  value can never equal one by chance.
- `date_shift`: same-row, plus `0 < |out - in| <= Rule.range` days.
- `fpe` and `faker` with a pool: same-row, plus a swap check. A correct permutation of a domain
  lands in the input domain, so single hits prove nothing. The column fails when its output
  multiset equals its input multiset on `SWAP_ROWS` or more rows, which is a row permutation.
- `categorical`, `bucketize`: no same-row or exact-cell check, because a legitimate mapping can
  return the input value. Each output must be in `Rule.allowed`, and equal canonical inputs must
  give equal outputs.
- `passthrough`: exempt.
- `truncate`: keeps exactly `Rule.prefix` characters, and the prefix must be set.
- `text_redact`: surrounding text may stay, a detected entity may not (matched without case).
"""

from __future__ import annotations

import datetime
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from scripts.qa.invariants import Rows, Violation
from scripts.qa.sweep import canonical, has_fragment

EXACT = frozenset({"hash", "tokenize", "redact"})
MARKER_ONLY = frozenset({"faker"})
SWAPPED = frozenset({"fpe", "faker"})
CLOSED = frozenset({"categorical", "bucketize"})
KNOWN = EXACT | MARKER_ONLY | SWAPPED | CLOSED | {"date_shift", "truncate", "text_redact"}
SWAP_ROWS = 20
MARKER = "qamark"
# Registry exception id -> the strategy it exempts (or limits). Keep equal to surfaces.toml.
EXCEPTION_RULES = {
    "passthrough": "passthrough",
    "truncate-prefix": "truncate",
    "text-redact-context": "text_redact",
    "unmask-output": "unmask",
}


class UnknownStrategy(ValueError):
    """A column names a strategy the checker has no rule for, or leaves a needed setting out.

    It must not pass silently.
    """


@dataclass(frozen=True)
class Rule:
    strategy: str
    prefix: int | None = None  # truncate: the documented prefix length (required)
    entities: tuple[tuple[str, ...], ...] = field(default=())  # text_redact: entities per row
    allowed: tuple[object, ...] = field(default=())  # categorical, bucketize: the legal outputs
    range: int | None = None  # date_shift: the configured maximum shift, in days
    pool: bool = False  # faker: the values come from a pool, so the swap check applies


def _needs(table: str, column: str, rule: Rule, source: Rows) -> None:
    where = f"{table}/{column}"
    if rule.strategy not in KNOWN | {"passthrough"}:
        raise UnknownStrategy(f"{where}: no I1 rule for this strategy")
    needed = [
        (rule.strategy in CLOSED and not rule.allowed, "its allowed values"),
        (rule.strategy == "date_shift" and rule.range is None, "its range"),
        (rule.strategy == "truncate" and rule.prefix is None, "its prefix length"),
        # No entity list means nothing is checked, and a pass would be a lie.
        (
            rule.strategy == "text_redact" and len(rule.entities) != len(source),
            "every row's entities",
        ),
    ]
    for missing, what in needed:
        if missing:
            raise UnknownStrategy(f"{where}: {rule.strategy} needs {what}")


def check_cells(
    table: str,
    rules: Mapping[str, Rule],
    source: Rows,
    output: Rows,
    *,
    unmask_run: bool = False,
    surface: str = "output-data-files",
) -> list[Violation]:
    """Check each ruled column of an output table against the same-position source rows.

    `unmask_run` is the documented case of `unmask` or `detokenize` output when the run holds the
    vault file and the mask secret: originals are expected there.
    """
    if unmask_run:
        return []
    if len(source) != len(output):
        return [Violation("I1", surface, f"{table}/-/-", "row-count")]  # I4 owns the detail
    found: list[Violation] = []
    for column, rule in rules.items():
        if rule.strategy == "passthrough":
            continue
        _needs(table, column, rule, source)
        before = [r.get(column) for r in source]
        after = [r.get(column) for r in output]
        domain = {canonical(v) for v in before if v is not None}
        if rule.strategy in MARKER_ONLY:
            domain = {c for c in domain if has_fragment(c, MARKER)}
        allowed = {canonical(a) for a in rule.allowed}
        mapping: dict[str, str] = {}
        for i, (src, out) in enumerate(zip(before, after)):
            kind = _violation(rule, src, out, domain, allowed, mapping, i)
            if kind:
                found.append(Violation("I1", surface, f"{table}/{column}/{i}", kind))
        if rule.strategy in SWAPPED and _is_permutation(before, after):
            found.append(Violation("I1", surface, f"{table}/{column}/-", "permutation"))
    return found


def _is_permutation(before: list[object], after: list[object]) -> bool:
    """True when the output column is the input column reordered, on enough rows to be no accident."""
    pairs = [(b, a) for b, a in zip(before, after) if b is not None]
    if len(pairs) < SWAP_ROWS or any(a is None for _, a in pairs):
        return False
    return Counter(canonical(b) for b, _ in pairs) == Counter(canonical(a) for _, a in pairs)


def _day(value: object) -> datetime.date | None:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _violation(
    rule: Rule,
    before: object,
    after: object,
    domain: set[str],
    allowed: set[str],
    mapping: dict[str, str],
    row: int,
) -> str:
    if before is None:
        return ""  # a null has no original value to leak
    if rule.strategy == "truncate":
        keep = str(before)[: rule.prefix]
        return "" if after is not None and str(after) == keep else "truncate-extra"
    if rule.strategy == "text_redact":
        found = any(has_fragment(str(after), e) for e in rule.entities[row])
        return "entity" if found else ""
    if rule.strategy in CLOSED:
        out = canonical(after) if after is not None else None
        if out is None or out not in allowed:
            return "not-allowed"
        return "" if mapping.setdefault(canonical(before), out) == out else "nondeterministic"
    if after is not None and canonical(after) == canonical(before):
        return "same-row"
    if rule.strategy == "date_shift":
        was, now = _day(before), _day(after)
        spread = abs((now - was).days) if was and now else None
        return "" if spread is not None and 0 < spread <= (rule.range or 0) else "shift-range"
    if rule.strategy in EXACT | MARKER_ONLY and after is not None and canonical(after) in domain:
        return "exact-cell"
    return ""
