"""I5: column names, order and types of each output match what the docs say for the strategy.

The caller supplies the expected `(name, type)` pairs from the pipeline config and the strategy
docs; this module compares them to what the output file carries. Types are compared as given, so a
reader that sees `int64` and a docs table that says `integer` must agree on one spelling first.
"""

from __future__ import annotations

from collections.abc import Sequence

from scripts.qa.invariants import Violation

Columns = Sequence[tuple[str, str]]


def check_schema(table: str, expected: Columns, actual: Columns) -> list[Violation]:
    found = []
    want, have = [n for n, _ in expected], [n for n, _ in actual]
    if sorted(want) != sorted(have):
        found.append(Violation("I5", "output-data-files", f"{table}/-/-", "names"))
    elif want != have:
        found.append(Violation("I5", "output-data-files", f"{table}/-/-", "order"))
    types = dict(actual)
    for name, kind in expected:
        if name in types and types[name] != kind:
            found.append(Violation("I5", "output-data-files", f"{table}/{name}/-", "type"))
    return found
