"""Paths and a by-path module loader for the QA tooling tests.

`scripts/qa` has no package and its `io.py` would shadow the standard library if the folder
were on `sys.path`, so every QA module is loaded from its file under a private name.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[3]
BRIEFS = REPO / "docs" / "qa" / "briefs"
QA_SCRIPTS = REPO / "scripts" / "qa"


def load_qa_module(name: str) -> ModuleType:
    path = QA_SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_qa_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
