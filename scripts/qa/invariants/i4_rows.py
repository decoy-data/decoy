"""I4: every input row is accounted for.

Mask: input rows = output rows + quarantined rows, per table, and the quarantine count the run
reported equals the rows found in the quarantine output. Subset: output rows never exceed input
rows (I2 covers the keys). Generate: rows match the config, or the `--rows` ratio when given.
"""

from __future__ import annotations

from scripts.qa.invariants import Violation


def _v(table: str, kind: str) -> list[Violation]:
    return [Violation("I4", "output-data-files", f"{table}/-/-", kind)]


def check_mask(
    table: str, rows_in: int, rows_out: int, quarantined: int, reported_quarantined: int
) -> list[Violation]:
    """`quarantined` is counted from the quarantine output; `reported_quarantined` from the run."""
    if quarantined != reported_quarantined:
        return _v(table, "quarantine-count")
    if rows_in != rows_out + quarantined:
        return _v(table, "row-loss")
    return []


def check_subset(table: str, rows_in: int, rows_out: int) -> list[Violation]:
    return _v(table, "subset-grew") if rows_out > rows_in else []


def check_generate(
    table: str, rows_out: int, configured: int, ratio: float = 1.0
) -> list[Violation]:
    expected = round(configured * ratio)
    return [] if rows_out == expected else _v(table, "generated-count")
