"""I2: each output foreign key obeys its configured orphan policy.

Keys are compared as whole tuples. A composite key can pass a per-column check and still be an
orphan: parents (A,1) and (B,2) do not contain the child (A,2), though A and 2 each exist.

Policies (`docs/cli-reference.md:897`):
- `fail`: a source orphan must be refused; a clean source must give joining children.
- `remap`: every non-null output child tuple joins an output parent tuple.
- `preserve`: a child that was an orphan stays one, a child that joined still joins.
A child tuple with any null part is not checked, as SQL treats it.
"""

from __future__ import annotations

from collections.abc import Sequence

from scripts.qa.invariants import Rows, Violation

POLICIES = ("fail", "remap", "preserve")


def _key(row: dict[str, object], columns: Sequence[str]) -> tuple[object, ...] | None:
    key = tuple(row.get(c) for c in columns)
    return None if any(v is None or v == "" for v in key) else key


def orphans(parents: Rows, children: Rows, parent_cols: Sequence[str], child_cols: Sequence[str]):
    """Row indexes of children whose complete key matches no parent."""
    have = {k for p in parents if (k := _key(p, parent_cols)) is not None}
    return [
        i
        for i, c in enumerate(children)
        if (k := _key(c, child_cols)) is not None and k not in have
    ]


def check_fk(
    policy: str,
    table: str,
    source_parents: Rows,
    source_children: Rows,
    out_parents: Rows,
    out_children: Rows,
    parent_cols: Sequence[str],
    child_cols: Sequence[str],
    *,
    refused: bool = False,
) -> list[Violation]:
    if policy not in POLICIES:
        raise ValueError(f"unknown orphan policy {policy!r}")
    src = set(orphans(source_parents, source_children, parent_cols, child_cols))
    if policy == "fail" and src:
        return (
            [] if refused else [Violation("I2", "output-data-files", f"{table}/-/-", "not-refused")]
        )
    if refused:
        return (
            []
            if policy == "fail"
            else [Violation("I2", "output-data-files", f"{table}/-/-", "refused")]
        )
    out = set(orphans(out_parents, out_children, parent_cols, child_cols))
    if policy == "preserve":
        if len(source_children) != len(out_children):
            return [Violation("I2", "output-data-files", f"{table}/-/-", "row-count")]
        bad = sorted(src ^ out)
    else:  # fail with a clean source, and remap
        bad = sorted(out)
    return [
        Violation("I2", "output-data-files", f"{table}/{'+'.join(child_cols)}/{i}", "orphan")
        for i in bad
    ]
