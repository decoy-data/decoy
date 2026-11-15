"""What prune and export may act on: the library taken stock of under the lock (plan 4.7, 4.11).

Prune deletes what no ref and no kept record reaches; export writes what a ref reaches. Both are
only as safe as the roots they can see, so they first account for every entry: each ref file
read and parsed (a leading byte order mark is fine), and every object file indexed after the
index is caught up. An entry they cannot account for (a ref that cannot be read or holds no id,
a link or pipe among the refs or objects, a folder that cannot be listed, a record file with no
index row because it cannot be read or verified) is counted in `unexplained`; prune `--yes` and
export refuse while it is not empty, and `decoy library fsck` names each one. A linked
`library/`, `objects/` or `refs/` folder is `library_path_unsafe` from the walk itself.

Everything here lists through `_fs` and `_paths.object_entries`; nothing is opened by a path
that could lead outside the root.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from decoy.cli.library import _index, _refs
from decoy.cli.library._errors import LIBRARY_UNEXPLAINED_ENTRIES, LibraryError
from decoy.cli.library._paths import OBJECTS, REFS, object_entries

if TYPE_CHECKING:
    import sqlite3

    from decoy.cli.library._index import IndexRow
    from decoy.cli.library._store import Library

__all__ = ["Inventory", "take_inventory"]


@dataclass(frozen=True)
class Inventory:
    rows: tuple[IndexRow, ...]
    refs: dict[str, str]  # ref name (relative to `refs/`) -> record id
    unexplained: int

    def require_explained(self) -> None:
        """`library_unexplained_entries` unless every entry is accounted for."""
        if self.unexplained:
            raise LibraryError(LIBRARY_UNEXPLAINED_ENTRIES)


def take_inventory(library: Library, conn: sqlite3.Connection) -> Inventory:
    """Catch the index up and account for every ref and object; call under `_index.locked`."""
    objects_dir = library.library_dir / OBJECTS
    refs_dir = library.library_dir / REFS
    found = list(object_entries(library.root, objects_dir))
    stored = {o.record_id for o in found if o.stored and o.record_id is not None}
    _index.ensure_schema(conn)
    _index.sync(conn, stored, library.index_row)
    rows = tuple(_index.all_rows(conn))
    indexed = {row.id for row in rows}
    unexplained = sum(1 for o in found if not o.stored) + len(stored - indexed)
    refs: dict[str, str] = {}
    for entry, read, rid in _refs.iter_refs(library.root, refs_dir):
        if entry.kind != "file" or not read or rid is None:
            unexplained += 1
            continue
        refs[entry.path.relative_to(refs_dir).as_posix()] = rid
    return Inventory(rows, refs, unexplained)
