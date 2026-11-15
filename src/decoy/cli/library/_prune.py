"""`decoy library prune`: delete records the user no longer keeps (plan 4.7, 4.8, 4.3a; L4b).

Garbage collection in git's shape (`git gc` / `git prune`): refs are the roots, links are the
edges, and only records unreachable from a ref or from a record that is kept may go, and never one
younger than the grace period (one hour, git's `gc.pruneExpire` idea, so a record a running
command just wrote cannot vanish). A record of a kind this version does not know (or a newer
payload major) is never deleted whatever the arguments, and its links still protect their targets.

`prune_preview` and `prune_apply` are separate functions with no behavior flag. Both take the
library lock (`_index.locked`), catch the index up with the object files and resolve the exact
targets from there; apply then deletes those files one by one (best effort: a file that cannot
be removed is reported and kept) and drops a record's index rows only after its file is gone.
A degraded library refuses both with `library_lock_unavailable`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from decoy.cli.library import _index
from decoy.cli.library._errors import LIBRARY_LOCK_UNAVAILABLE, LIBRARY_PATH_UNSAFE, LibraryError
from decoy.cli.library._fs import remove_file
from decoy.cli.library._inventory import take_inventory

if TYPE_CHECKING:
    from decoy.cli.library._index import IndexRow
    from decoy.cli.library._store import Library

__all__ = [
    "GRACE",
    "PrunePlan",
    "PruneReport",
    "Rule",
    "policy_rules",
    "prune_apply",
    "prune_preview",
]

GRACE = timedelta(hours=1)


@dataclass(frozen=True)
class Rule:
    """One prune rule. `kind` None applies to every known kind, each kind counted on its own.
    With both limits a record must be beyond `keep_last` and older than `older_than`."""

    kind: str | None = None
    keep_last: int | None = None
    older_than: timedelta | None = None


@dataclass(frozen=True)
class PrunePlan:
    delete: tuple[str, ...]  # oldest first
    protected: tuple[str, ...]  # matched a rule but reachable from a ref or a kept record
    young: tuple[str, ...]  # matched a rule but inside the grace period
    unexplained: int = 0  # entries prune cannot account for; `--yes` refuses while any exist


@dataclass(frozen=True)
class PruneReport:
    deleted: tuple[str, ...]
    left: tuple[str, ...]  # could not be removed (held open); kept with their index rows


def _when(row: IndexRow) -> datetime:
    return datetime.fromisoformat(row.created_at.replace("Z", "+00:00"))


def _order(row: IndexRow) -> tuple[str, str]:
    return row.created_at, row.id


def _matches(rows: Sequence[IndexRow], rule: Rule, now: datetime) -> set[str]:
    if rule.keep_last is None and rule.older_than is None:
        return set()
    groups: dict[str, list[IndexRow]] = {}
    for row in rows:
        if row.known and (rule.kind is None or row.kind == rule.kind):
            groups.setdefault(row.kind, []).append(row)
    chosen: set[str] = set()
    for group in groups.values():
        group.sort(key=_order)
        pool = group if rule.keep_last is None else group[: max(len(group) - rule.keep_last, 0)]
        if rule.older_than is not None:
            pool = [r for r in pool if _when(r) < now - rule.older_than]
        chosen.update(r.id for r in pool)
    return chosen


def _plan(
    rows: Sequence[IndexRow], ref_ids: Iterable[str], rules: Sequence[Rule], now: datetime
) -> PrunePlan:
    matched: set[str] = set()
    for rule in rules:
        matched |= _matches(rows, rule, now)
    by_id = {row.id: row for row in rows}
    young = {rid for rid in matched if now - _when(by_id[rid]) < GRACE}
    candidates = matched - young
    kept = set(by_id) - candidates  # opaque, newer, young and unmatched records are roots too
    reachable = _index.reachable([*ref_ids, *kept], rows)
    ordered = sorted((by_id[rid] for rid in candidates), key=_order)
    return PrunePlan(
        delete=tuple(r.id for r in ordered if r.id not in reachable),
        protected=tuple(r.id for r in ordered if r.id in reachable),
        young=tuple(sorted(young)),
    )


def _require_lockable(library: Library) -> None:
    if library.degraded is not None:
        raise LibraryError(LIBRARY_LOCK_UNAVAILABLE)


def prune_preview(library: Library, rules: Sequence[Rule], *, now: datetime) -> PrunePlan:
    """The exact records `prune_apply` would delete now, and how many entries would stop it;
    deletes nothing."""
    _require_lockable(library)
    with _index.locked(library.library_dir) as conn:
        stock = take_inventory(library, conn)
        plan = _plan(stock.rows, stock.refs.values(), rules, now)
        return replace(plan, unexplained=stock.unexplained)


def prune_apply(library: Library, rules: Sequence[Rule], *, now: datetime) -> PruneReport:
    """Delete what the plan resolves to under the lock; report what could not be removed.

    Refuses with `library_unexplained_entries` while any ref or object cannot be accounted
    for (a root it cannot see could protect a candidate). Each file goes through `_fs`, so a
    linked folder on the way is `library_path_unsafe` and nothing outside the root is touched.
    """
    _require_lockable(library)
    deleted: list[str] = []
    left: list[str] = []
    with _index.locked(library.library_dir) as conn:
        stock = take_inventory(library, conn)
        stock.require_explained()
        for rid in _plan(stock.rows, stock.refs.values(), rules, now).delete:
            path = library.object_path(rid)
            if path is None:
                continue
            gone = True
            try:
                remove_file(library.root, path)
            except LibraryError as exc:
                if exc.code == LIBRARY_PATH_UNSAFE:
                    raise
                gone = False  # held open (Windows) or not removable: keep file and row
            if not gone:
                left.append(rid)
                continue
            _index.delete_row(conn, rid)
            deleted.append(rid)
    return PruneReport(tuple(deleted), tuple(left))


def policy_rules(root: Path) -> list[Rule]:
    """The rules `.decoy/library.yaml` asks for (plan 4.7): `keep_last` per kind, or for every
    kind from `default`. The default policy keeps all, so it gives no rule."""
    from decoy_engine.records import registered_kinds

    from decoy.cli.library._policy import KeepLast, load_policy

    retention = load_policy(root).retention.records
    rules = [
        Rule(kind=kind, keep_last=rule.keep_last)
        for kind, rule in sorted(retention.kinds.items())
        if isinstance(rule, KeepLast)
    ]
    if isinstance(retention.default, KeepLast):
        rules += [
            Rule(kind=spec.kind, keep_last=retention.default.keep_last)
            for spec in registered_kinds()
            if spec.kind not in retention.kinds
        ]
    return rules
