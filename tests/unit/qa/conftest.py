"""Make the repository root importable so tests can `import scripts.qa...`.

`scripts/` is not a package the wheel ships and `pythonpath` only lists `src`, so the QA tooling is
imported by its path from the repository root, the same way `python -m scripts.qa.matrix` runs it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
