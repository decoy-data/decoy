"""I7: no refusal or error text holds a value.

Runs the needles sweep and the refusal set over stdout, stderr and logs. The input cells of the
run (every value of every input row) become a refusal set of their own, built by the sweep module,
so an echoed cell that is not a marker is found by the same whole-token matcher and `Bob` does not
flag `Bobby Tables`. This module has no matcher of its own. Cells under the sweep's minimum length
are left out, as there.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from scripts.qa.invariants import Violation
from scripts.qa.sweep import RefusalSet, hits


def check_text(
    texts: Mapping[str, str],
    needles: Sequence[bytes],
    refusal: RefusalSet | None = None,
    input_cells: Iterable[object] = (),
) -> list[Violation]:
    """`texts` maps a surface id (`stdout`, `stderr`, `logs`) to its text."""
    cells = RefusalSet.build(input_cells) if input_cells else None
    found: list[Violation] = []
    for surface, text in texts.items():
        found += [Violation("I7", surface, f"n{i}", "needle") for i in hits(text.encode(), needles)]
        if refusal is not None and refusal.found_in(text):
            found.append(Violation("I7", surface, "s", "scalar"))
        if cells is not None and cells.found_in(text):
            found.append(Violation("I7", surface, "c", "input-cell"))
    return found
