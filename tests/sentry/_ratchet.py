"""Shared shrink-only ratchet logic for sentry baselines (stdlib plus tomllib).

A baseline is a JSON file ``{"sentry_id", "created_in", "entries": {key: {"reason"}}}``
under ``tests/sentry/baselines/``. ``scripts/dev/sentry_registry.toml`` binds each sentry id to
exactly one baseline path. ``check`` compares the working tree with a base commit and returns
findings; an empty list means the ratchet holds. An entry that carries a numeric ceiling
(``max``, ``count`` or ``sites``, each on its own) may keep or lower it, never raise or drop it (see
``max_raised``). Messages carry ids, paths and keys only. ``load_allowlist`` is the one reader a
sentry uses for its allowlist: the registered baseline JSON, which is the only copy.

Growth has one recorded path: a registry row may list ``approved_growth`` entries, each an exact
key and a dated owner decision ``owner YYYY-MM-DD <text>``. Ported from decoy-engine
``tests/sentry/_ratchet.py`` (``DECISION``, ``parse_approvals`` and the stale-row check) and its
``scripts/dev/sentry_registry.toml`` rows. A listed key may be added; a pattern, a bad decision, or
a key the baseline does not hold is a finding.

Ported from decoy-engine ``tests/sentry/_ratchet.py`` (X0a), plus the platform's
``created_in`` rules: every baseline names a non-empty ``created_in``, and a first inventory
must name the slice passed as ``slice_name`` when one is given.

A code move renames baseline keys without adding anything. A baseline may carry a top-level
``"moved_from": {new_key: old_key}`` map. A gained key is admitted only when the map names an
old key that was in the merge base, is gone from the head, is named once, and whose base entry
equals the new head entry exactly. An entry whose new key is already in the base is a leftover
of a merged move and is ignored. The map is top-level, not inside an entry, because other
sentries compare entries exactly.

A code split moves one counted key's hits into several files. A baseline may carry a top-level
``"split_from": {old_key: [new_key, ...]}`` map (CLI-SPLIT). The new keys are admitted only when
the old key was in the merge base and is gone from the head, every listed new key is a head entry,
each new entry equals the old one apart from its ceilings, and each ceiling the old entry held
sums across the new entries to exactly the old value, with each part in ``0..old``. A new key
named by both maps is a finding, and so is an old key consumed more than once (by a move and a
split, or by a split group repeated in the JSON). A split whose new keys are all already in the
base is a leftover of a merged split and is ignored. Only a registry row marked ``split = true``
may carry ``split_from``: the parts of an additive count (lint-debt hits) sum across files, but
a module size does not, so one oversize ``max`` could otherwise become several.

A JSON object that repeats a key anywhere in a baseline is a finding: ``json`` would keep only the
last copy and hide the other.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REGISTRY = "scripts/dev/sentry_registry.toml"
BASELINE_DIR = "tests/sentry/baselines"
MIN_REASON = 15
PLACEHOLDERS = frozenset({"todo", "tbd", "fixme", "xxx", "n/a", "none"})
# Numeric fields a baseline entry may carry as a count the ratchet lets only fall, each checked.
CEILING_FIELDS = ("max", "count", "sites")


def _load_decision_check():
    """The one dated-owner-decision grammar lives in shipped code; load it by path (stdlib only)."""
    path = Path(__file__).resolve().parents[2] / "src/decoy/distribution/release_identity.py"
    spec = importlib.util.spec_from_file_location("_release_identity_for_ratchet", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.is_dated_owner_decision


_decision_ok = _load_decision_check()
_GLOB_CHARS = frozenset("*?[]")


@dataclass(frozen=True)
class Baseline:
    sentry_id: str
    created_in: str  # as written; "" when missing or not a string
    keys: frozenset[str]
    reasons: dict[str, object]
    moved_from: object = None  # raw top-level map; validated in ``move_findings``
    split_from: object = None  # raw top-level map; validated in ``split_findings``
    duplicate_keys: tuple[str, ...] = ()  # keys repeated inside any object of the document


def parse_registry(text: str) -> tuple[dict[str, str], list[str]]:
    """Return ``{id: path}`` and findings for duplicate ids or shared paths."""
    rows = tomllib.loads(text).get("sentry", [])
    out: dict[str, str] = {}
    findings: list[str] = []
    for row in rows:
        sid, path = row.get("id", ""), row.get("baseline", "")
        if sid in out:
            findings.append(f"registry: sentry id {sid} appears twice")
        out[sid] = path
    for path in sorted(set(out.values())):
        ids = sorted(i for i, p in out.items() if p == path)
        if len(ids) > 1:
            findings.append(f"registry: two sentries ({', '.join(ids)}) share baseline {path}")
        if not path.startswith(BASELINE_DIR + "/"):
            findings.append(f"registry: baseline {path} is outside {BASELINE_DIR}/")
    return out, findings


def load_allowlist(sentry_id: str, root: Path | None = None) -> dict[str, dict[str, Any]]:
    """The entries of the baseline the registry names for ``sentry_id``: ``{key: entry}``."""
    base = root if root is not None else Path(__file__).resolve().parents[2]
    registered, _ = parse_registry((base / REGISTRY).read_text(encoding="utf-8"))
    doc = json.loads((base / registered[sentry_id]).read_text(encoding="utf-8"))
    return dict(doc["entries"])


def parse_split_ids(text: str) -> frozenset[str]:
    """Ids of the registry rows marked ``split = true``: the rows whose ceilings add across files."""
    return frozenset(
        str(row.get("id", ""))
        for row in tomllib.loads(text).get("sentry", [])
        if row.get("split") is True
    )


def parse_approvals(text: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    """``{sentry id: {key: decision}}`` from ``approved_growth`` rows, and findings for bad rows.

    A row is ``{ key, decision }``; the key compares exactly (no glob or prefix) and the decision
    must name a dated owner decision. Growth of a baseline passes only through a row here.
    """
    out: dict[str, dict[str, str]] = {}
    findings: list[str] = []
    for row in tomllib.loads(text).get("sentry", []):
        sid = row.get("id", "")
        for item in row.get("approved_growth", []):
            key = item.get("key") if isinstance(item, dict) else None
            decision = item.get("decision") if isinstance(item, dict) else None
            if not isinstance(key, str) or not key:
                findings.append(f"{sid}: approved_growth row has no key")
            elif _GLOB_CHARS & set(key):
                findings.append(f"{sid}: approved_growth key {key} is a pattern; list exact keys")
            elif not _decision_ok(decision):
                findings.append(
                    f"{sid}: approved_growth for {key} needs a decision "
                    "'owner YYYY-MM-DD <text of 10+ chars>'"
                )
            else:
                out.setdefault(sid, {})[key] = decision
    return out, findings


class _Pairs(dict):  # type: ignore[type-arg]
    """A JSON object that remembers the keys the text repeated (``json`` keeps only the last)."""

    dupes: tuple[str, ...] = ()


def _pairs(items: list[tuple[str, object]]) -> _Pairs:
    out = _Pairs(items)
    names = [k for k, _ in items]
    out.dupes = tuple(sorted({k for k in names if names.count(k) > 1}))
    return out


def _repeated_keys(node: object) -> set[str]:
    """Every key that some object in the parsed document repeats."""
    found: set[str] = set()
    if isinstance(node, _Pairs):
        found.update(node.dupes)
    if isinstance(node, dict):
        for child in node.values():
            found |= _repeated_keys(child)
    elif isinstance(node, list):
        for child in node:
            found |= _repeated_keys(child)
    return found


def parse_baseline(text: str) -> Baseline:
    data = json.loads(text, object_pairs_hook=_pairs)
    entries = data.get("entries", {})
    created_in = data.get("created_in")
    return Baseline(
        str(data.get("sentry_id", "")),
        created_in if isinstance(created_in, str) else "",
        frozenset(entries),
        entries,
        data.get("moved_from"),
        data.get("split_from"),
        tuple(sorted(_repeated_keys(data))),
    )


def reason_findings(path: str, base: Baseline) -> list[str]:
    out = []
    for key in sorted(base.keys):
        entry = base.reasons[key]
        reason = entry.get("reason") if isinstance(entry, dict) else None
        text = reason.strip() if isinstance(reason, str) else ""
        if len(text) < MIN_REASON or text.lower().strip(".!") in PLACEHOLDERS:
            out.append(
                f"{path}: reason for {key} is empty, a placeholder or under {MIN_REASON} chars"
            )
    return out


def _git_show(root: Path, ref: str, rel: str) -> str | None:
    res = subprocess.run(
        ["git", "-C", str(root), "show", f"{ref}:{rel}"],
        capture_output=True,
        text=True,
    )
    return res.stdout if res.returncode == 0 else None


def _base_entries(root: Path, ref: str, path: str) -> dict[str, object]:
    text = _git_show(root, ref, path)
    return dict(parse_baseline(text).reasons) if text is not None else {}


def _int_field(entry: dict[str, object], field: str) -> int | None:
    value = entry.get(field)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def max_raised(head: object, base: object) -> bool:
    """True when the ceiling of an entry rose, was dropped, or moved to another field.

    Each ceiling field (``max``, ``count``, ``sites``) the base entry holds as an integer is
    checked on its own. An entry that had a ceiling may not gain a ceiling field it did not have:
    lowering ``count`` while adding ``max`` would move the cap to the new field.
    """
    if not isinstance(base, dict):
        return False
    held = [f for f in CEILING_FIELDS if _int_field(base, f) is not None]
    if not held:
        return False
    head_entry = head if isinstance(head, dict) else {}
    if any(_int_field(head_entry, f) is not None for f in CEILING_FIELDS if f not in held):
        return True
    for field in held:
        old, new = _int_field(base, field), _int_field(head_entry, field)
        if old is not None and (new is None or new > old):
            return True
    return False


def _base_baseline(root: Path, ref: str, path: str) -> Baseline | None:
    text = _git_show(root, ref, path)
    return parse_baseline(text) if text is not None else None


def move_findings(
    path: str, head: Baseline, base: Baseline | None, gained: frozenset[str]
) -> tuple[list[str], frozenset[str]]:
    """Validate ``moved_from`` against the base; return findings and the admitted new keys."""
    raw = head.moved_from
    if raw is None:
        return [], frozenset()
    if not isinstance(raw, dict):
        return [f"{path}: moved_from is not an object"], frozenset()
    findings: list[str] = []
    admitted: set[str] = set()
    base_keys = base.keys if base is not None else frozenset()
    base_entries = base.reasons if base is not None else {}
    named_olds: dict[str, str] = {}
    for new, old in sorted(raw.items(), key=lambda kv: str(kv[0])):
        if (
            not isinstance(new, str)
            or not isinstance(old, str)
            or not new.strip()
            or not old.strip()
        ):
            findings.append(f"{path}: moved_from needs non-empty string keys and values")
            continue
        if old in named_olds:
            findings.append(f"{path}: moved_from names {old} for both {named_olds[old]} and {new}")
            continue
        named_olds[old] = new
        if new not in head.keys:
            findings.append(f"{path}: moved_from key {new} is not an entry in the head")
        elif new not in gained:
            continue  # the move already merged: the key is in the base, so it admits nothing
        elif old not in base_keys:
            findings.append(f"{path}: moved_from old key {old} was not in the merge base")
        elif old in head.keys:
            findings.append(f"{path}: moved_from old key {old} is still in the head")
        elif base_entries[old] != head.reasons[new]:
            findings.append(f"{path}: moved entry {new} differs from {old} in the merge base")
        else:
            admitted.add(new)
    return findings, frozenset(admitted)


def _split_entry_finding(
    path: str, old: str, old_entry: object, news: list[str], head: Baseline
) -> str | None:
    """Why the split of ``old`` into ``news`` is refused, or None when it keeps the total."""
    held = (
        [f for f in CEILING_FIELDS if _int_field(old_entry, f) is not None]
        if isinstance(old_entry, dict)
        else []
    )
    if not held:
        return f"{path}: split of {old} needs a counted entry (max, count or sites)"
    assert isinstance(old_entry, dict)
    rest = {k: v for k, v in old_entry.items() if k not in CEILING_FIELDS}
    for new in news:
        entry = head.reasons[new]
        if not isinstance(entry, dict) or (
            {k: v for k, v in entry.items() if k not in CEILING_FIELDS} != rest
            or {f for f in CEILING_FIELDS if f in entry} != set(held)
            or any(_int_field(entry, f) is None for f in held)
        ):
            return f"{path}: split entry {new} differs from {old} in the merge base"
    for field in held:
        why = _split_field_finding(path, old, _int_field(old_entry, field) or 0, field, news, head)
        if why is not None:
            return why
    return None


def _split_field_finding(
    path: str, old: str, cap: int, field: str, news: list[str], head: Baseline
) -> str | None:
    """Each part of ``field`` must lie in ``0..cap`` and the parts must sum to ``cap``."""
    parts: list[int] = []
    for new in news:
        entry = head.reasons[new]
        part = _int_field(entry, field) if isinstance(entry, dict) else None
        if part is None or not 0 <= part <= cap:
            return f"{path}: split entry {new}: {field} {part} is outside 0..{cap}"
        parts.append(part)
    if sum(parts) != cap:
        return f"{path}: split of {old}: {field} sums to {sum(parts)}, the merge base holds {cap}"
    return None


def double_spend_findings(path: str, head: Baseline) -> list[str]:
    """An old key that ``moved_from`` and ``split_from`` consume more than once, in one pass."""
    uses: dict[str, int] = {}
    moved, split = head.moved_from, head.split_from
    if isinstance(moved, dict):
        for old in moved.values():
            if isinstance(old, str):
                uses[old] = uses.get(old, 0) + 1
    if isinstance(split, dict):
        for old in [*split, *getattr(split, "dupes", ())]:
            if isinstance(old, str):
                uses[old] = uses.get(old, 0) + 1
    return [
        f"{path}: old key {old} is consumed more than once by moved_from and split_from"
        for old in sorted(k for k, n in uses.items() if n > 1)
    ]


def _split_shape_finding(
    path: str, old: object, news: object, seen: set[str], moved: dict[str, str], head: Baseline
) -> str | None:
    """Why one ``split_from`` group is malformed, or None; records its new keys in ``seen``."""
    if (
        not isinstance(old, str)
        or not old.strip()
        or not isinstance(news, list)
        or not news
        or not all(isinstance(n, str) and n.strip() for n in news)
    ):
        return f"{path}: split_from needs non-empty string keys and lists of keys"
    twice = sorted({n for n in news if n in seen or news.count(n) > 1})
    if twice:
        return f"{path}: split_from names {', '.join(twice)} twice"
    seen.update(news)
    both = sorted(n for n in news if n in moved)
    if both:
        return f"{path}: {', '.join(both)} is named by both moved_from and split_from"
    missing = sorted(n for n in news if n not in head.keys)
    if missing:
        return f"{path}: split_from key {', '.join(missing)} is not an entry in the head"
    return None


def split_findings(
    path: str,
    head: Baseline,
    base: Baseline | None,
    gained: frozenset[str],
    additive: bool = False,
) -> tuple[list[str], frozenset[str]]:
    """Validate ``split_from`` against the base; return findings and the admitted new keys.

    ``additive`` is the registry row's ``split = true``: without it no split is admitted.
    """
    raw = head.split_from
    if raw is None:
        return [], frozenset()
    if not additive:
        return [f"{path}: split_from is not allowed here, the registry row has no split = true"], (
            frozenset()
        )
    if not isinstance(raw, dict):
        return [f"{path}: split_from is not an object"], frozenset()
    findings: list[str] = []
    admitted: set[str] = set()
    base_keys = base.keys if base is not None else frozenset()
    moved = head.moved_from if isinstance(head.moved_from, dict) else {}
    seen: set[str] = set()
    for old, news in sorted(raw.items(), key=lambda kv: str(kv[0])):
        why = _split_shape_finding(path, old, news, seen, moved, head)
        if why is not None:
            findings.append(why)
            continue
        if not any(n in gained for n in news):
            continue  # the split already merged: its keys are in the base, so it admits nothing
        if old not in base_keys:
            findings.append(f"{path}: split_from old key {old} was not in the merge base")
            continue
        if old in head.keys:
            findings.append(f"{path}: split_from old key {old} is still in the head")
            continue
        assert base is not None
        why = _split_entry_finding(path, old, base.reasons[old], news, head)
        if why is not None:
            findings.append(why)
            continue
        admitted.update(news)
    return findings, frozenset(admitted)


def _fmt(keys: frozenset[str]) -> str:
    return ", ".join(sorted(keys))


def check(root: Path, base_ref: str, slice_name: str | None = None) -> tuple[list[str], list[str]]:
    """Return ``(findings, report_lines)`` for the tree at ``root`` against ``base_ref``."""
    reg_file = root / REGISTRY
    reg_text = reg_file.read_text(encoding="utf-8") if reg_file.exists() else ""
    head, findings = parse_registry(reg_text)
    approvals, approval_findings = parse_approvals(reg_text)
    split_ids = parse_split_ids(reg_text)
    findings += approval_findings
    base_text = _git_show(root, base_ref, REGISTRY)
    base_reg = parse_registry(base_text)[0] if base_text is not None else {}
    report: list[str] = []

    on_disk = {p.relative_to(root).as_posix() for p in (root / BASELINE_DIR).glob("*.json")}
    for path in sorted(on_disk - set(head.values())):
        findings.append(f"{path}: baseline file is not registered in {REGISTRY}")

    loaded: dict[str, Baseline] = {}
    for sid, path in sorted(head.items()):
        file = root / path
        if not file.exists():
            findings.append(f"{sid}: registry points at {path} but there is no baseline file")
            continue
        loaded[sid] = head_doc = parse_baseline(file.read_text(encoding="utf-8"))
        if head_doc.sentry_id != sid:
            findings.append(
                f"{path}: sentry_id {head_doc.sentry_id!r} does not match registry id {sid}"
            )
        if not head_doc.created_in.strip():
            findings.append(f"{path}: created_in is missing or not a non-empty string")
        findings += reason_findings(path, head_doc)
        findings += [
            f"{path}: JSON key {key} is repeated inside one object"
            for key in head_doc.duplicate_keys
        ]
        findings += [
            f"{sid}: stale approved_growth, {key} is not in {path}"
            for key in sorted(set(approvals.get(sid, {})) - head_doc.keys)
        ]

    removed = set(base_reg) - set(head)
    # A key a replacement keeps must keep its max too, or a rename would launder a raised max.
    old_entries: dict[str, list[object]] = {}
    for s in removed:
        for key, entry in _base_entries(root, base_ref, base_reg[s]).items():
            old_entries.setdefault(key, []).append(entry)
    old_union = frozenset(old_entries)
    new_union: frozenset[str] = frozenset()
    replaced_raised: set[str] = set()
    for sid, head_doc in sorted(loaded.items()):
        path = head[sid]
        report.append(f"{sid}: {len(head_doc.keys)} key(s) in {path}")
        if sid in base_reg:
            if base_reg[sid] != path:
                findings.append(f"{sid}: baseline moved from {base_reg[sid]} to {path}")
                continue
            base_doc = _base_baseline(root, base_ref, path)
            grown = head_doc.keys - (base_doc.keys if base_doc is not None else frozenset())
            moved_f, admitted = move_findings(path, head_doc, base_doc, grown)
            findings += moved_f
            grown -= admitted
            split_f, split_admitted = split_findings(
                path, head_doc, base_doc, grown, sid in split_ids
            )
            findings += split_f + double_spend_findings(path, head_doc)
            grown -= split_admitted
            approved = grown & frozenset(approvals.get(sid, {}))
            report += [
                f"{sid}: approved growth {k} ({approvals[sid][k]})" for k in sorted(approved)
            ]
            grown -= approved
            if grown:
                findings.append(
                    f"{sid}: baseline gained key(s) not in the merge base: {_fmt(grown)}"
                )
            old = base_doc.reasons if base_doc is not None else {}
            raised = sorted(
                k for k in head_doc.keys & old.keys() if max_raised(head_doc.reasons[k], old[k])
            )
            if raised:
                findings.append(f"{sid}: max raised or dropped for key(s): {', '.join(raised)}")
        elif removed:
            new_union |= head_doc.keys
            replaced_raised |= {
                k
                for k in head_doc.keys & old_union
                if any(max_raised(head_doc.reasons[k], old) for old in old_entries[k])
            }
        else:
            # Newly registered in this diff: the one way a first inventory is admitted.
            report.append(f"{sid}: first inventory, {len(head_doc.keys)} key(s), review required")
            if slice_name is not None and head_doc.created_in != slice_name:
                findings.append(
                    f"{sid}: created_in {head_doc.created_in!r} is not slice {slice_name!r}"
                )
    grown = new_union - old_union
    if removed and grown:
        findings.append(
            f"replacement or split of {_fmt(frozenset(removed))} adds key(s): {_fmt(grown)}"
        )
    if replaced_raised:
        findings.append(
            f"replacement or split of {_fmt(frozenset(removed))} raised or dropped max for"
            f" key(s): {_fmt(frozenset(replaced_raised))}"
        )
    return findings, report
