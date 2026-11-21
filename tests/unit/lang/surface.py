"""The language's frozen surface as data: the grammar text, the code set, the versions.

`python -m tests.unit.lang.surface` rewrites `tests/fixtures/release_freeze/lang-surface.json`.
A person runs it and reviews the diff; the test never writes the file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from decoy.lang import CODES
from decoy.lang._grammar import GRAMMAR
from decoy.lang._parse import SUPPORTED_VERSIONS

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "release_freeze" / "lang-surface.json"


def surface() -> dict[str, Any]:
    return {
        "grammar_sha256": hashlib.sha256(GRAMMAR.encode("utf-8")).hexdigest(),
        "codes": sorted(CODES),
        "supported_versions": list(SUPPORTED_VERSIONS),
    }


if __name__ == "__main__":
    FIXTURE.write_text(json.dumps(surface(), indent=1) + "\n", encoding="utf-8")
