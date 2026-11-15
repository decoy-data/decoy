"""The files a project's library holds after `decoy run` stored its records (LIB L3a).

For tests that list every path a command wrote: the library's own files plus one object file
per stored record, each named from the record's id, so the expectation stays exact.
"""

from __future__ import annotations

from pathlib import Path

from decoy.cli.io import DECOY_DIR
from decoy.cli.library import open_library


def library_paths(project: Path, *, kinds: dict[str, int]) -> set[Path]:
    """Every path under `project/.decoy/` once the records were stored: the git files, the
    library skeleton, and each record's fan folder and object file. `kinds` is how many records
    of each kind must be there (checked, so a missing or extra record fails the caller)."""
    root = project / DECOY_DIR
    rows = open_library(root).rows()
    found: dict[str, int] = {}
    for row in rows:
        found[row.kind] = found.get(row.kind, 0) + 1
    assert found == kinds, f"records stored: {found}, expected {kinds}"
    library = root / "library"
    paths = {
        root,
        root / ".gitignore",
        root / ".gitattributes",
        library,
        library / "LAYOUT",
        library / "index.sqlite",
        library / "objects",
        library / "tmp",
    }
    for row in rows:
        digest = row.id.removeprefix("sha256:")
        paths |= {
            library / "objects" / digest[:2],
            library / "objects" / digest[:2] / f"{digest[2:]}.json",
        }
    return paths
