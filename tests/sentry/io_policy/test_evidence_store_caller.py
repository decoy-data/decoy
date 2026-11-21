"""L3a: `store_evidence` has exactly one caller outside the library package (amendment 2026-11-12).

Until RESULT C1a and C1b land, the evidence record is stored where the manifest is built,
`cli/run/_evidence.py`; `finish` takes the call over in the RESULT PR. A second caller would
store a second, differently built manifest (ML3-drift).
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "decoy"


def _callers() -> list[str]:
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel.startswith("cli/library/"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
                if name == "store_evidence":
                    found.append(rel)
    return found


def test_store_evidence_has_exactly_one_caller() -> None:
    assert _callers() == ["cli/run/_evidence.py"]
