"""Tag census helpers (freeze S7b): find every `"<name>/vN"` literal in `src/decoy` and classify it.

Every tag literal is a frozen format: a row of `docs/release/frozen-surfaces.md` holds the tag in
backticks in its Surface cell, and the test in that row pins it. The CLI derives no keys, digests
or seeds and holds no tag that stays in the process, so it has no derivation-label or internal
class. A tag that never leaves the process (an internal class) needs an artifact-scan proof first,
as the engine census has; add that proof before adding the class.

The scan parses every `.py` file under `src/decoy` and reads each string or bytes constant, so
comments and docstrings never count and any quoting style is seen. A line scan covers the shipped
yaml, json, toml and txt files under `src/decoy`. Known limit (S7B-KL-1): tags built with
f-strings or concatenation are outside the scan.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"
MAP = ROOT / "docs" / "release" / "frozen-surfaces.md"

WHOLE = re.compile(r"[a-z][a-z0-9._-]*(?:/[a-z0-9._-]+)*/v[0-9]+")
SPAN = re.compile(r"`([^`]+)`")

DATA_SUFFIXES = (".yaml", ".yml", ".json", ".toml", ".txt")
# A tag in a data file stands alone: no tag character or `/` on either side.
DATA_TAG = re.compile(r"(?<![A-Za-z0-9._/-])" + WHOLE.pattern + r"(?![A-Za-z0-9._/-])")


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


def data_tags(text: str) -> set[str]:
    """Every standalone tag in the lines of a shipped data file."""
    return {m.group(0) for line in text.splitlines() for m in DATA_TAG.finditer(line)}


def source_tags(root: Path = SRC) -> dict[str, list[str]]:
    """Every tag under `root` (Python literals and shipped data files), with the files that hold it."""
    found: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*")):
        if path.suffix == ".py":
            tags = literals(path.read_text(encoding="utf-8"))
        elif path.suffix in DATA_SUFFIXES:
            tags = data_tags(path.read_text(encoding="utf-8"))
        else:
            continue
        for tag in tags:
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


def unclassified(found: set[str], frozen: set[str]) -> set[str]:
    return found - frozen


def frozen_tags() -> set[str]:
    return map_tags(MAP.read_text(encoding="utf-8"))
