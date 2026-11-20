"""What `decoy library export` writes, chosen under the library lock (plan 4.11, 4.3a; L4b).

The engine owns the codec (`decoy_engine.records.export_lines`); this module chooses the records
and their refs from the locked inventory (`_inventory`) and puts the raw verified envelopes in
link order. It refuses while any entry is unexplained (`library_unexplained_entries`): a record
it cannot verify would otherwise be silently missing from an export that reports success. The
destination is checked by `_fs.write_export`, the one checked write for a path the user names.

An export is always closed (review round 3 on #219), as a dependency closure is in package
managers and `git bundle`: every link of every record in the file resolves inside the file.

- `--kind`, `--since` and `--ref` choose the starting records only. `closure` then adds every
  record they link to, transitively, whatever its kind or date (`_index.reachable`, the walk
  prune uses).
- When the codec withholds a record (a kind or payload this version cannot strip), every record
  that links to it, directly or not, is withheld too, and a ref to any of them is left out. The
  header's `withheld_records` lists both; `ExportLines` tells them apart for the notice.
- As a last check, a set the codec reports with `external_links > 0` is refused
  (`export_not_closed`) before anything is written.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from decoy.cli.library import _index
from decoy.cli.library._errors import (
    EXPORT_NOT_CLOSED,
    LIBRARY_UNEXPLAINED_ENTRIES,
    LibraryError,
)
from decoy.cli.library._inventory import take_inventory

if TYPE_CHECKING:
    from decoy.cli.library._index import IndexRow
    from decoy.cli.library._store import Library

__all__ = ["ExportLines", "closure", "export_lines", "link_order", "select"]


def closure(start: Iterable[str], rows: Iterable[IndexRow]) -> set[str]:
    """The starting records plus everything they link to, transitively."""
    return _index.reachable(start, rows)


def select(
    library: Library,
    *,
    kind: str | None,
    since: datetime | None,
    ref: str | None,
    target: str | None,
) -> tuple[list[str], dict[str, str]]:
    """The record ids to export and the refs to name, from the locked inventory. `target` is
    `ref` resolved to an id and starts the export alone; otherwise the filters choose the starting
    records. Either way the export is their `closure`."""
    with _index.locked(library.library_dir) as conn:
        stock = take_inventory(library, conn)
    stock.require_explained()
    rows = {row.id: row for row in stock.rows}
    if target is not None:
        start = {target}
    else:
        start = set(rows)
        if kind is not None:
            start = {rid for rid in start if rows[rid].kind == kind}
        if since is not None:
            start = {rid for rid in start if _index.parse_instant(rows[rid].created_at) >= since}
    chosen = closure(start, stock.rows)
    if not chosen <= set(rows):
        raise LibraryError(LIBRARY_UNEXPLAINED_ENTRIES)
    if target is not None:
        refs = {ref: target} if ref in stock.refs else {}
    else:
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


@dataclass(frozen=True)
class ExportLines:
    """The codec's lines, and what was withheld: by the codec (it cannot strip them) and here
    (they link to a withheld record). The header's `withheld_records` lists both."""

    lines: list[bytes]
    cannot_strip: tuple[str, ...]
    links_withheld: tuple[str, ...]


def export_lines(
    library: Library, ids: Iterable[str], refs: dict[str, str], keep_paths: bool
) -> ExportLines:
    """The codec's lines for these records (raw verified envelopes, in link order), closed:
    raises `export_not_closed` rather than return a set with external links."""
    from decoy_engine import records

    raws: list[Any] = []
    for rid in ids:
        found = library.get(rid)
        if isinstance(found, records.RecordNeedsNewer) and not found.verified:
            continue  # a later envelope major cannot be verified or rewritten by this version
        raws.append(found.raw)
    lines = _encode(raws, refs, keep_paths)
    cannot_strip = tuple(json.loads(lines[0])["withheld_records"])
    dropped = set(cannot_strip)
    dependents: list[str] = []
    for raw in raws:  # link order: a record's targets come before it
        if raw["id"] not in dropped and any(link["id"] in dropped for link in raw["links"]):
            dropped.add(raw["id"])
            dependents.append(raw["id"])
    if dropped:
        kept = [raw for raw in raws if raw["id"] not in dependents]
        lines = _encode(kept, {n: t for n, t in refs.items() if t not in dropped}, keep_paths)
        if dependents:
            lines[0] = _with_withheld(lines[0], dependents)
    if json.loads(lines[0])["external_links"]:
        raise LibraryError(EXPORT_NOT_CLOSED)
    return ExportLines(lines, cannot_strip, tuple(dependents))


def _encode(raws: Sequence[Any], refs: dict[str, str], keep_paths: bool) -> list[bytes]:
    import decoy_engine
    from decoy_engine import records

    from decoy._version import __version__

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


def _with_withheld(header_line: bytes, more: Sequence[str]) -> bytes:
    """The codec's header with `more` (ids of verified records) added to `withheld_records`, in
    the codec's canonical form; `records.read_export` validates the whole header on import."""
    from decoy_engine import records

    header = json.loads(header_line)
    header["withheld_records"] = [*header["withheld_records"], *more]
    return records.canonical_bytes(header) + b"\n"
