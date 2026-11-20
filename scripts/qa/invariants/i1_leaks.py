"""I1: no original value survives where the column's strategy replaces it.

Cell rules run per column by the config's strategy. Text surfaces get the needles sweep
(`scripts/qa/sweep.py`), not this module. The documented exceptions come from
`docs/qa/surfaces.toml`, and `EXCEPTION_RULES` must name every one of them (a consistency test
fails otherwise), so a new exception cannot be added without a rule and a pass case.

Strategy families (plan 5.5):
- `replace`: the output cell differs from the same row's input cell, and equals no input cell of
  that column (hash, faker, tokenize, redact).
- `domain`: the output may reuse a value from the column's domain, so only the same-row check
  applies (fpe, categorical, date_shift, bucketize).
- `passthrough`: exempt.
- `truncate`: the output is the documented prefix of the input and nothing more.
- `text_redact`: surrounding text may stay, a detected entity may not.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from scripts.qa.invariants import Rows, Violation
from scripts.qa.sweep import canonical

REPLACE = frozenset({"hash", "faker", "tokenize", "redact"})
DOMAIN = frozenset({"fpe", "categorical", "date_shift", "bucketize"})
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
        if rule.strategy not in REPLACE | DOMAIN | {"truncate", "text_redact"}:
            raise UnknownStrategy(f"{table}/{column}: no I1 rule for this strategy")
        if rule.strategy == "text_redact" and len(rule.entities) != len(source):
            # No entity list means nothing is checked, and a pass would be a lie.
            raise UnknownStrategy(f"{table}/{column}: text_redact needs the entities of every row")
        seen = {canonical(r[column]) for r in source if r.get(column) is not None}
        for i, (src, out) in enumerate(zip(source, output)):
            kind = _violation(rule, src.get(column), out.get(column), seen, i)
            if kind:
                found.append(Violation("I1", surface, f"{table}/{column}/{i}", kind))
    return found


def _violation(rule: Rule, before: object, after: object, domain: set[str], row: int) -> str:
    if before is None:
        return ""  # a null has no original value to leak
    if rule.strategy == "truncate":
        keep = str(before)[: rule.prefix]
        return "" if str(after) == keep or str(after) == "" else "truncate-extra"
    if rule.strategy == "text_redact":
        found = any(e and e in str(after) for e in rule.entities[row])
        return "entity" if found else ""
    if after is not None and canonical(after) == canonical(before):
        return "same-row"
    if rule.strategy in REPLACE and after is not None and canonical(after) in domain:
        return "exact-cell"
    return ""
