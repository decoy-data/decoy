"""L3a: `store_run_result` has exactly one caller outside the library package.

The run-result record stores the document `cli/run/_result.py` built, from the one place that
writes the envelope and the `--result` file. A second caller would store a second, differently
built document (ML3-rebuild).
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
                if name == "store_run_result":
                    found.append(rel)
    return found


def test_store_run_result_has_exactly_one_caller() -> None:
    assert _callers() == ["cli/run/_result.py"]
