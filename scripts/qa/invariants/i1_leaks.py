"""I1: no original value survives where the column's strategy replaces it (plan 5.5, rev 3.3).

Cell rules run per column by the config's strategy. Text surfaces get the needles sweep
(`scripts/qa/sweep.py`), not this module. The documented exceptions come from
`docs/qa/surfaces.toml`, and `EXCEPTION_RULES` must name every one of them (a consistency test
fails otherwise), so a new exception cannot be added without a rule and a pass case.

An exact-cell check is used only where the output domain cannot overlap the input by
construction. Anywhere else a correct run can land on another row's input value, so the check
would cry wolf:
- `hash`, `tokenize`, `redact`: same-row plus exact-cell (the output equals no input cell of the
  column). an unpooled `faker` gets the same pair over marker inputs only; marker cells are ours, so a faker
  value can never equal one by chance.
- `date_shift`: same-row, plus `0 < |out - in| <= Rule.range` days.
- `fpe` and `faker` with `Rule.pool`: same-row, plus a swap check. A correct permutation of a
  domain lands in the input domain, so single hits prove nothing. On `SWAP_ROWS` or more non-null
  rows the column fails when 90 percent or more of it is made of its own input values (the
  multiset overlap, a null output counting as no match), so shifting a column by one row and
  changing one cell still fails.
- `categorical`, `bucketize`: no same-row or exact-cell check, because a legitimate mapping can
  return the input value. Each output must be in `Rule.allowed`, and equal canonical inputs must
  give equal outputs.
- `passthrough`: exempt.
- Null rows: `NULL_ROW` is the one contract. A null source stays null; `categorical` and `bucketize`
  may also land in their allowed set. Any other output in a null row is invented data.
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
CLOSED = frozenset({"categorical", "bucketize"})
KNOWN = EXACT | MARKER_ONLY | CLOSED | {"fpe", "date_shift", "truncate", "text_redact"}
# The null-row contract of every strategy, in one place. A null stays null unless the strategy's
# docs say it maps to something: `categorical` and `bucketize` have a closed output set, so a
# null may land in it. Nothing in the docs gives another strategy a value for null, so it stays
# null. To relax one, give it an explicit checked domain here.
NULL_ROW = {
    **dict.fromkeys(KNOWN | {"passthrough"}, "null"),
    **dict.fromkeys(CLOSED, "domain"),
}
SWAP_ROWS = 20
SWAP_OVERLAP = 0.9  # a column this much made of its own input values has been shuffled
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
        if rule.strategy in MARKER_ONLY and not rule.pool:
            domain = {c for c in domain if has_fragment(c, MARKER)}
        allowed = {canonical(a) for a in rule.allowed}
        mapping: dict[str, str] = {}
        for i, (src, out) in enumerate(zip(before, after)):
            kind = _violation(rule, src, out, domain, allowed, mapping, i)
            if kind:
                found.append(Violation("I1", surface, f"{table}/{column}/{i}", kind))
        if _swap_checked(rule) and _is_shuffle(before, after):
            found.append(Violation("I1", surface, f"{table}/{column}/-", "permutation"))
    return found


def _swap_checked(rule: Rule) -> bool:
    return rule.strategy == "fpe" or (rule.strategy in MARKER_ONLY and rule.pool)


def _is_shuffle(before: list[object], after: list[object]) -> bool:
    """True when the output column is made of the input column's own values, on enough rows."""
    pairs = [(b, a) for b, a in zip(before, after) if b is not None]
    if len(pairs) < SWAP_ROWS:
        return False
    originals = Counter(canonical(b) for b, _ in pairs)
    produced = Counter(canonical(a) for _, a in pairs if a is not None)  # a null matches nothing
    overlap = sum((originals & produced).values())
    return overlap >= SWAP_OVERLAP * len(pairs)


def _day(value: object) -> datetime.date | None:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _null_source(rule: Rule, after: object, allowed: set[str]) -> str:
    """The null-row contract (`NULL_ROW`): a null source has no original to keep.

    Under `null` the output must be null. Under `domain` it may be null or one of the rule's
    allowed values. Anything else, such as a date, `1234` or a pooled name, is invented data.
    """
    if after is None:
        return ""
    if NULL_ROW[rule.strategy] == "domain":
        return "" if canonical(after) in allowed else "not-allowed"
    return "null-row"


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
        return _null_source(rule, after, allowed)
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
    if (
        rule.strategy in EXACT | MARKER_ONLY
        and not rule.pool
        and after is not None
        and canonical(after) in domain
    ):
        return "exact-cell"
    return ""
