"""I7: no refusal or error text holds a value.

Runs the needles sweep, the refusal set and a same-row check over stdout, stderr and logs. The
same-row check takes the input cells of the run (every value of every input row) and looks for
any of them whole inside the text, which catches an echoed cell that is not a marker, such as a
name or an id in a data file that has no `qamark` cells. A short cell would match ordinary words,
so cells under the refusal set's minimum length are left out, as there.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from scripts.qa.invariants import Violation
from scripts.qa.sweep import MIN_SCALAR, RefusalSet, canonical, hits


def check_text(
    texts: Mapping[str, str],
    needles: Sequence[bytes],
    refusal: RefusalSet | None = None,
    input_cells: Iterable[object] = (),
) -> list[Violation]:
    """`texts` maps a surface id (`stdout`, `stderr`, `logs`) to its text."""
    cells = {
        c for v in input_cells if v is not None and len(c := canonical(v).casefold()) >= MIN_SCALAR
    }
    found: list[Violation] = []
    for surface, text in texts.items():
        found += [Violation("I7", surface, f"n{i}", "needle") for i in hits(text.encode(), needles)]
        if refusal is not None and refusal.found_in(text):
            found.append(Violation("I7", surface, "s", "scalar"))
        if any(c in text.casefold() for c in cells):
            found.append(Violation("I7", surface, "c", "input-cell"))
    return found
