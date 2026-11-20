"""I1: no original value survives where the column's strategy replaces it.

Cell rules run per column by the config's strategy. Text surfaces get the needles sweep
(`scripts/qa/sweep.py`), not this module. The documented exceptions come from
`docs/qa/surfaces.toml`, and `EXCEPTION_RULES` must name every one of them (a consistency test
fails otherwise), so a new exception cannot be added without a rule and a pass case.

Strategy families (plan 5.5):
- Six replacing strategies (hash, fpe, faker, date_shift, tokenize, redact) get both checks:
  the output cell differs from the same row's input cell, and it equals no input cell of that
  column. The second check is what fails a run that swaps original values between rows, which a
  same-row check alone passes.
- `categorical` and `bucketize` map into a closed set that may overlap the input column (a
  category can map to another category). They get the same-row check, and the exact-cell check is
  dropped. Instead every output cell must be in `Rule.allowed`: the configured categories or the
  values the documented mapping gives, and the bucket labels or bounds in their documented form.
- `passthrough`: exempt.
- `truncate`: the output is exactly the documented prefix of the input. An empty output or a
  different prefix fails.
- `text_redact`: surrounding text may stay, a detected entity may not.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from scripts.qa.invariants import Rows, Violation
from scripts.qa.sweep import canonical

REPLACE = frozenset({"hash", "fpe", "faker", "date_shift", "tokenize", "redact"})
CLOSED = frozenset({"categorical", "bucketize"})
# Registry exception id -> the strategy it exempts (or limits). Keep equal to surfaces.toml.
EXCEPTION_RULES = {
    "passthrough": "passthrough",
    "truncate-prefix": "truncate",
    "text-redact-context": "text_redact",
    "unmask-output": "unmask",
}


class UnknownStrategy(ValueError):
    """A column names a strategy the checker has no rule for. It must not pass silently."""


@dataclass(frozen=True)
class Rule:
    strategy: str
    prefix: int = 0  # truncate: the documented prefix length
    entities: tuple[tuple[str, ...], ...] = field(default=())  # text_redact: entities per row
    allowed: tuple[object, ...] = field(default=())  # categorical, bucketize: the legal outputs


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
        if rule.strategy not in REPLACE | CLOSED | {"truncate", "text_redact"}:
            raise UnknownStrategy(f"{table}/{column}: no I1 rule for this strategy")
        if rule.strategy == "text_redact" and len(rule.entities) != len(source):
            # No entity list means nothing is checked, and a pass would be a lie.
            raise UnknownStrategy(f"{table}/{column}: text_redact needs the entities of every row")
        if rule.strategy in CLOSED and not rule.allowed:
            raise UnknownStrategy(f"{table}/{column}: {rule.strategy} needs its allowed values")
        allowed = {canonical(a) for a in rule.allowed}
        seen = {canonical(r[column]) for r in source if r.get(column) is not None}
        for i, (src, out) in enumerate(zip(source, output)):
            kind = _violation(rule, src.get(column), out.get(column), seen, allowed, i)
            if kind:
                found.append(Violation("I1", surface, f"{table}/{column}/{i}", kind))
    return found


def _violation(
    rule: Rule, before: object, after: object, domain: set[str], allowed: set[str], row: int
) -> str:
    if before is None:
        return ""  # a null has no original value to leak
    if rule.strategy == "truncate":
        keep = str(before)[: rule.prefix]
        return "" if after is not None and str(after) == keep else "truncate-extra"
    if rule.strategy == "text_redact":
        found = any(e and e in str(after) for e in rule.entities[row])
        return "entity" if found else ""
    if after is not None and canonical(after) == canonical(before):
        return "same-row"
    if rule.strategy in CLOSED and (after is None or canonical(after) not in allowed):
        return "not-allowed"
    if rule.strategy in REPLACE and after is not None and canonical(after) in domain:
        return "exact-cell"
    return ""
