"""A valid `scan-set/v1` document for tests that need a saved scan without scanning a file.

The engine's read model is strict about member types, so a test that hand-writes a scan lists
only what it cares about (field names, PII scores, QI groups) and this fills in the rest. The
document holds no cell values, as a real one does not.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

PII_CANDIDATE_THRESHOLD = 0.6


def scan_set_doc(
    fields: Sequence[Mapping[str, Any]],
    *,
    table: str = "table",
    row_count: int = 5,
    reid_risk_score: float | None = None,
    quasi_identifier_groups: Sequence[Sequence[str]] = (),
    basis: str | None = None,
    scanned_rows: int | None = None,
) -> dict[str, Any]:
    """One-table `scan-set/v1` document. Each field names `name`, and may set `pii_score`
    and `detector_hits`. Without `basis` the table has neither it nor `scanned_rows`, the shape
    of a scan saved before the basis labels."""
    doc = {
        "scan_schema": "scan-set/v1",
        "engine_version": "",
        "scanned_at": "",
        "tables": [
            {
                "name": table,
                "descriptor": {},
                "row_count": row_count,
                "row_count_exact": True,
                "sample_strategy": "head",
                "sample_row_cap": None,
                "fields": [_field(f) for f in fields],
                "key_candidates": [],
                "warnings": [],
                "reid_risk_score": reid_risk_score,
                "quasi_identifier_groups": [list(g) for g in quasi_identifier_groups],
            }
        ],
        "relationships": [],
    }
    if basis is not None:
        doc["tables"][0]["basis"] = basis
        doc["tables"][0]["scanned_rows"] = scanned_rows
    return doc


def _field(spec: Mapping[str, Any]) -> dict[str, Any]:
    score = spec.get("pii_score")
    return {
        "name": spec["name"],
        "dtype": "string",
        "null_count": 0,
        "null_rate": 0.0,
        "distinct_count": 0,
        "pii_score": score,
        "pii_candidate": bool(score is not None and score >= PII_CANDIDATE_THRESHOLD),
        "detector_hits": list(spec.get("detector_hits", [])),
        "leading_zero_count": None,
    }
