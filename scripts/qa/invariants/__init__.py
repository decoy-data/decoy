"""The invariants I1 to I7 (plan 5.5): checks over a run's outputs, one module per invariant.

Each checker takes rows or bytes already read, so it does not depend on a file format, and returns
`Violation`s. A violation names the invariant, a surface and an opaque coordinate. It never holds
a cell, a needle or any text from the data.
"""

from __future__ import annotations

from dataclasses import dataclass

Row = dict[str, object]
Rows = list[Row]


@dataclass(frozen=True)
class Violation:
    invariant: str  # "I1" .. "I7"
    surface: str  # a registry surface id, or "-" when the check has no surface
    coordinate: str  # `<table>/<column>/<row>` or similar; positions only, never values
    kind: str  # a fixed word such as "same-row" or "orphan"
