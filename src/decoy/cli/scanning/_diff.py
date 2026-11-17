"""The rules that compare two saved scans: `ScanDiff` and `diff_scan_sets`.

Moved unchanged out of `decoy.cli.scan`. `decoy scan diff` and `decoy ci check` both call
`diff_scan_sets`; import it from `decoy.cli.scanning`, never from this module. Pure: dicts in,
a `ScanDiff` out, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

_BUCKET_RANK: dict[str, int] = {"none": 0, "low": 1, "med": 2, "high": 3}


def pii_bucket(score: float | None) -> str:
    """Same buckets as the `scan` card uses (>=0.6 PII candidate count)."""
    if score is None:
        return "none"
    if score >= 0.6:
        return "high"
    if score >= 0.3:
        return "med"
    if score > 0:
        return "low"
    return "none"


def _bucket_rank(bucket: str) -> int:
    return _BUCKET_RANK.get(bucket, 0)


def _canon_qi(group: list) -> tuple[str, ...]:
    """Canonical, hashable form of a QI group for set comparison."""
    return tuple(sorted(str(x) for x in group))


@dataclass(frozen=True)
class ScanDiff:
    """The categorized difference between two saved scans (pure, no I/O)."""

    added_rows: list[dict]
    removed_rows: list[dict]
    pii_increased: list[dict]
    pii_decreased: list[dict]
    qi_added: list[tuple[str, ...]]
    qi_removed: list[tuple[str, ...]]
    risk_delta: float | None
    new_high_pii: list[dict]

    @property
    def drift(self) -> bool:
        return bool(self.pii_increased or self.new_high_pii or self.qi_added)


def diff_scan_sets(old_data: dict, new_data: dict) -> ScanDiff:
    """Categorize drift between two scan dicts. Shared by `scan diff` and `decoy ci check`."""
    old_fields = {f.get("name"): f for f in old_data.get("fields", []) if f.get("name")}
    new_fields = {f.get("name"): f for f in new_data.get("fields", []) if f.get("name")}

    added_names = sorted(set(new_fields) - set(old_fields))
    removed_names = sorted(set(old_fields) - set(new_fields))
    common_names = sorted(set(old_fields) & set(new_fields))

    pii_increased: list[dict] = []
    pii_decreased: list[dict] = []
    for name in common_names:
        old_score = old_fields[name].get("pii_score") or 0
        new_score = new_fields[name].get("pii_score") or 0
        old_bucket = pii_bucket(old_score)
        new_bucket = pii_bucket(new_score)
        if _bucket_rank(new_bucket) > _bucket_rank(old_bucket):
            pii_increased.append(
                {
                    "name": name,
                    "old_score": old_score,
                    "new_score": new_score,
                    "old_bucket": old_bucket,
                    "new_bucket": new_bucket,
                }
            )
        elif _bucket_rank(new_bucket) < _bucket_rank(old_bucket):
            pii_decreased.append(
                {
                    "name": name,
                    "old_score": old_score,
                    "new_score": new_score,
                    "old_bucket": old_bucket,
                    "new_bucket": new_bucket,
                }
            )

    old_qi = {_canon_qi(g) for g in old_data.get("quasi_identifier_groups", [])}
    new_qi = {_canon_qi(g) for g in new_data.get("quasi_identifier_groups", [])}
    qi_added = sorted(new_qi - old_qi)
    qi_removed = sorted(old_qi - new_qi)

    old_risk = old_data.get("reid_risk_score")
    new_risk = new_data.get("reid_risk_score")
    risk_delta: float | None = None
    if isinstance(old_risk, (int, float)) and isinstance(new_risk, (int, float)):
        risk_delta = float(new_risk) - float(old_risk)

    added_rows = [
        {
            "name": n,
            "pii_score": new_fields[n].get("pii_score"),
            "pii_bucket": pii_bucket(new_fields[n].get("pii_score")),
        }
        for n in added_names
    ]
    removed_rows = [
        {
            "name": n,
            "pii_score": old_fields[n].get("pii_score"),
            "pii_bucket": pii_bucket(old_fields[n].get("pii_score")),
        }
        for n in removed_names
    ]

    new_high_pii = [r for r in added_rows if r["pii_bucket"] == "high"]
    return ScanDiff(
        added_rows=added_rows,
        removed_rows=removed_rows,
        pii_increased=pii_increased,
        pii_decreased=pii_decreased,
        qi_added=qi_added,
        qi_removed=qi_removed,
        risk_delta=risk_delta,
        new_high_pii=new_high_pii,
    )
