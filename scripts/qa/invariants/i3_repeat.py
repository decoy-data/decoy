"""I3: re-runs and route pairs give equal outputs exactly where the docs promise it.

Data files are compared by SHA-256. Result and evidence files carry run ids and timestamps, so
they are compared as JSON with those members removed. `PROMISES` lists the pairs the docs make.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping

from scripts.qa.invariants import Violation

PROMISES = {
    "rerun-same-mask-secret": "docs/cli-reference.md:108",
    "chunked-vs-plain-value-keyed": "docs/cli-reference.md:109",
    "generate-same-master-key": "docs/cli-reference.md:107",
    "ignored-flag-vs-without": "docs/cli-reference.md:111",
}
VOLATILE = frozenset({"run_id", "started_at", "finished_at", "timestamp", "created_at", "duration"})


def _strip(node: object, volatile: Collection[str]) -> object:
    if isinstance(node, dict):
        return {k: _strip(v, volatile) for k, v in node.items() if k not in volatile}
    if isinstance(node, list):
        return [_strip(v, volatile) for v in node]
    return node


def _digest(
    name: str, blob: bytes, result_files: Collection[str], volatile: Collection[str]
) -> str:
    if name in result_files:
        try:
            blob = json.dumps(_strip(json.loads(blob), volatile), sort_keys=True).encode()
        except ValueError:
            pass  # a result file that is not JSON is compared as bytes
    return hashlib.sha256(blob).hexdigest()


def compare(
    first: Mapping[str, bytes],
    second: Mapping[str, bytes],
    *,
    result_files: Collection[str] = (),
    volatile: Collection[str] = VOLATILE,
) -> list[Violation]:
    """Names are output file names. A name in only one run is a violation too."""
    found = []
    for name in sorted(set(first) | set(second)):
        if name not in first or name not in second:
            found.append(Violation("I3", "output-data-files", f"{name}/-/-", "missing"))
        elif _digest(name, first[name], result_files, volatile) != _digest(
            name, second[name], result_files, volatile
        ):
            found.append(Violation("I3", "output-data-files", f"{name}/-/-", "differs"))
    return found
