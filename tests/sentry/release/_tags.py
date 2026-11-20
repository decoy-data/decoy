"""Tag census helpers (freeze S7b): find every `"<name>/vN"` literal in `src/decoy` and classify it.

A tag literal is one of three things. A frozen format is named in a row of
`docs/release/frozen-surfaces.md` (its Surface cell holds the tag in backticks) and pinned by the
test in that row. A derivation label is an input to a key, a digest or a seed (`DERIVATION_LABELS`,
empty today because the CLI derives nothing itself). An internal tag never reaches disk, `--json`,
a signed or hashed record or a derivation input, and carries a one-line reason (`INTERNAL_TAGS`).
The rule is the one in the engine census (`tests/sentry/release/_tags.py` in decoy-engine).

The scan parses every `.py` file under `src/decoy` and reads each string or bytes constant, so
comments and docstrings never count and any quoting style is seen. A tag must be the whole
constant. Known limit (S7B-KL-1): tags built with f-strings or concatenation, and tags in
non-Python files, are outside the scan.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"
MAP = ROOT / "docs" / "release" / "frozen-surfaces.md"

WHOLE = re.compile(r"[a-z][a-z0-9._-]*(?:/[a-z0-9._-]+)*/v[0-9]+")
SPAN = re.compile(r"`([^`]+)`")

# Derivation labels: the tag is an input to a key, a digest or a seed. Value: the owning module.
DERIVATION_LABELS: Final[dict[str, str]] = {}

# Internal tags: tag -> (owning module under src/decoy, why it never leaves the process).
INTERNAL_TAGS: Final[dict[str, tuple[str, str]]] = {}


def literals(text: str) -> set[str]:
    """Every string or bytes constant in `text` that is exactly one tag."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            value = node.value
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            if WHOLE.fullmatch(value):
                found.add(value)
    return found


def source_tags(root: Path = SRC) -> dict[str, list[str]]:
    """Every tag literal under `root`, with the files that hold it."""
    found: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        for tag in literals(path.read_text(encoding="utf-8")):
            found.setdefault(tag, []).append(path.relative_to(root).as_posix())
    return found


def map_tags(text: str) -> set[str]:
    """Tags named in backticks in the Surface cell of a map row."""
    tags: set[str] = set()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        surface = line.strip().strip("|").split("|")[0]
        tags |= {s for s in SPAN.findall(surface) if WHOLE.fullmatch(s)}
    return tags


def unclassified(
    found: set[str], frozen: set[str], labels: set[str], internal: set[str]
) -> set[str]:
    return found - frozen - labels - internal


def overlaps(frozen: set[str], labels: set[str], internal: set[str]) -> set[str]:
    sets = (frozen, labels, internal)
    return {tag for i, one in enumerate(sets) for other in sets[i + 1 :] for tag in one & other}


def classes() -> tuple[set[str], set[str], set[str]]:
    return (
        map_tags(MAP.read_text(encoding="utf-8")),
        set(DERIVATION_LABELS),
        set(INTERNAL_TAGS),
    )
