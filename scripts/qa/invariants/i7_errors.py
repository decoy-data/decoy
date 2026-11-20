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
from scripts.qa.sweep import RefusalSet, load_registry, sweep


def check_text(
    texts: Mapping[str, str],
    needles: Sequence[bytes],
    refusal: RefusalSet | None = None,
    input_cells: Iterable[object] = (),
) -> list[Violation]:
    """`texts` maps a surface id (`stdout`, `stderr`, `logs`) to its text.

    Raises `NothingRead` (through the sweep) when every text is empty, or when there is nothing
    to look for: no needle, an empty refusal set and no input cells.
    """
    cells = RefusalSet.build(input_cells)
    sets = [cells] if refusal is None else [refusal, cells]
    captures = {surface: (surface, text.encode()) for surface, text in texts.items()}
    kinds = {0: "scalar", 1: "input-cell"} if refusal is not None else {0: "input-cell"}
    found = []
    for leak in sweep(captures, needles, load_registry(), sets):
        index = leak.coordinate[1:]
        kind = "needle" if leak.coordinate[0] == "n" else kinds[int(index)]
        found.append(Violation("I7", leak.surface, leak.coordinate, kind))
    return found
