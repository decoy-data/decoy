"""What `decoy library export` writes, chosen under the library lock (plan 4.11, 4.3a; L4b).

The engine owns the codec (`decoy_engine.records.export_lines`); this module chooses the records
and their refs from the locked inventory (`_inventory`) and puts the raw verified envelopes in
link order. It refuses while any entry is unexplained (`library_unexplained_entries`): a record
it cannot verify would otherwise be silently missing from an export that reports success. `--ref`
exports the closure from `_index.reachable`, the walk prune uses. The destination is checked
by `_fs.write_export`, the one checked write for a path the user names.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from decoy.cli.library import _index
from decoy.cli.library._errors import LIBRARY_UNEXPLAINED_ENTRIES, LibraryError
from decoy.cli.library._inventory import take_inventory

if TYPE_CHECKING:
    from decoy.cli.library._index import IndexRow
    from decoy.cli.library._store import Library

__all__ = ["export_lines", "link_order", "select"]


def select(
    library: Library,
    *,
    kind: str | None,
    since: datetime | None,
    ref: str | None,
    target: str | None,
) -> tuple[list[str], dict[str, str]]:
    """The record ids to export and the refs to name, from the locked inventory. `target` is
    `ref` resolved to an id; with it, the export is exactly what `target` reaches (filters
    cannot be combined with `--ref`, so every header ref and link stays inside the file)."""
    with _index.locked(library.library_dir) as conn:
        stock = take_inventory(library, conn)
    stock.require_explained()
    rows = {row.id: row for row in stock.rows}
    if target is not None:
        chosen = _index.reachable([target], stock.rows)
        if not chosen <= set(rows):
            raise LibraryError(LIBRARY_UNEXPLAINED_ENTRIES)
        refs = {ref: target} if ref in stock.refs else {}
        return link_order([rows[rid] for rid in chosen]), refs
    chosen = set(rows)
    if kind is not None:
        chosen = {rid for rid in chosen if rows[rid].kind == kind}
    if since is not None:
        chosen = {rid for rid in chosen if _index.parse_instant(rows[rid].created_at) >= since}
    refs = {name: rid for name, rid in sorted(stock.refs.items()) if rid in chosen}
    return link_order([rows[rid] for rid in chosen]), refs


def link_order(rows: Sequence[IndexRow]) -> list[str]:
    """Ids with every link target inside the set before the record that links to it (Kahn's
    order); ties by `(created_at, id)`. Links point only to earlier records (plan 4.3), so an
    order always exists; skewed clocks cannot break it."""
    by_id = {row.id: row for row in rows}
    waiting = {row.id: {dst for _rel, dst in row.links if dst in by_id} for row in rows}
    order: list[str] = []
    while waiting:
        ready = sorted(
            (by_id[rid] for rid, deps in waiting.items() if not deps),
            key=lambda r: (r.created_at, r.id),
        )
        if not ready:  # a cycle cannot be built (ids hash their links); keep the rest by time
            ready = sorted((by_id[rid] for rid in waiting), key=lambda r: (r.created_at, r.id))
        for row in ready:
            order.append(row.id)
            del waiting[row.id]
        done = {row.id for row in ready}
        for deps in waiting.values():
            deps -= done
    return order


def export_lines(
    library: Library, ids: Iterable[str], refs: dict[str, str], keep_paths: bool
) -> list[bytes]:
    """The codec's lines for these records: raw verified envelopes only."""
    import decoy_engine
    from decoy_engine import records

    from decoy._version import __version__

    raws: list[Any] = []
    for rid in ids:
        found = library.get(rid)
        if isinstance(found, records.RecordNeedsNewer) and not found.verified:
            continue  # a later envelope major cannot be verified or rewritten by this version
        raws.append(found.raw)
    producer = {
        "name": "decoy-cli",
        "version": __version__,
        "engine_version": decoy_engine.__version__,
    }
    return list(
        records.export_lines(
            raws,
            producer=producer,
            exported_at=datetime.now(timezone.utc),
            refs=refs,
            keep_paths=keep_paths,
            logs=(),
        )
    )
