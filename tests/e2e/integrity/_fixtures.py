"""Shared inputs for the SCAN-ML C2a acceptance tests (plan 4.7, AT-C2a1 to AT-C2a8).

`write_pipeline` writes a two-table mask pipeline. Its absolute targets share `root/masked/`
(a delivery folder, so a rerun writes the same paths); with `relative=True` the targets go to
`masked/` and `other/` inside the run folder, so "beside the first target" is a real choice.
The YAML text is written byte for byte, so a test can ask for CRLF line ends. `ner_report` builds the value-free report the engine attaches
to `PostScanBlockedError` when an NER finding fails under `ner_findings: fail`.

The real-model tests run `decoy` in the `ner_python` venv (`conftest.py`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from tests.csv_sources import csv_source
from tests.e2e.models._venvs import wheelhouse
from tests.keyed_secret import TEST_MASK_SECRET_REF

NAMES = ("John Smith", "Mary Johnson", "Robert Brown", "Linda Davis", "Michael Wilson")
CANARY = "CANARY-C2A-7781"
MODEL = {"id": "en_core_web_sm", "version": "3.8.0"}

needs_wheelhouse = pytest.mark.skipif(
    wheelhouse() is None, reason="set DECOY_TEST_NER_WHEELHOUSE to a prepared ner wheelhouse"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_pipeline(
    root: Path,
    *,
    post: dict[str, Any] | None = None,
    newline: str = "\n",
    vault: bool = False,
    notes: bool = False,
    relative: bool = False,
    name: str = "pipeline.yaml",
) -> Path:
    """Two mask tables, `customers` then `orders`, written as described in the module docstring.

    `notes` adds a free-text column whose every cell names a person and keeps it through
    `truncate`, so an NER post-scan finds it (a `warning`, or `fail` under `ner_findings: fail`).
    """
    (root / "masked").mkdir(exist_ok=True)
    rows = 30
    customers: dict[str, list[Any]] = {
        "id": list(range(rows)),
        "email": [f"user{i}@example.invalid" for i in range(rows)],
    }
    if notes:
        customers["notes"] = [
            f"Called {NAMES[i % len(NAMES)]} about the renewal of the contract today"
            for i in range(rows)
        ]
    pd.DataFrame(customers).to_csv(root / "customers.csv", index=False)
    pd.DataFrame({"id": range(5), "code": ["A1", "B2", "C3", "D4", "E5"]}).to_csv(
        root / "orders.csv", index=False
    )
    email: dict[str, Any] = {"name": "email", "strategy": "redact"}
    if vault:
        email = {"name": "email", "strategy": "hash", "namespace": "em", "vault": True}
    columns = [{"name": "id", "strategy": "passthrough"}, email]
    if notes:
        columns.append({"name": "notes", "strategy": "truncate", "provider_config": {"length": 60}})
    masked = root / "masked"
    settings: dict[str, Any] = {"seed": 7}
    if vault:
        settings["mask_secret_ref"] = TEST_MASK_SECRET_REF
    cfg: dict[str, Any] = {
        "version": 2,
        "global_settings": settings,
        "sources": {
            "customers": csv_source(root / "customers.csv"),
            "orders": csv_source(root / "orders.csv"),
        },
        "tables": [
            {"name": "customers", "columns": columns},
            {
                "name": "orders",
                "columns": [
                    {"name": "id", "strategy": "passthrough"},
                    {"name": "code", "strategy": "redact"},
                ],
            },
        ],
        "targets": {
            table: {"type": "file", "format": "csv", "path": path}
            for table, path in (
                (
                    "customers",
                    "masked/customers.csv" if relative else str(masked / "customers.csv"),
                ),
                ("orders", "other/orders.csv" if relative else str(masked / "orders.csv")),
            )
        },
    }
    if post is not None:
        cfg["post_scan"] = post
    text = yaml.safe_dump(cfg, sort_keys=False).replace("\n", newline)
    path = root / name
    path.write_bytes(text.encode("utf-8"))
    return path


def default_report(root: Path, name: str = "pipeline.yaml") -> Path:
    """`<directory of the first target>/<config stem>.post-scan.json` (plan 4.7) for the
    absolute targets."""
    return root / "masked" / f"{Path(name).stem}.post-scan.json"


def ner_report(*, severity: str = "fail") -> dict[str, Any]:
    """The value-free report of a run an NER finding blocks."""
    from decoy_engine.verification.postmask import SCHEMA_VERSION

    finding = {
        "table": "customers",
        "column": "notes",
        "detector_id": "person_name",
        "match_rate": 1.0,
        "severity": severity,
        "configured_strategy": "truncate",
        "sample_match_count": 30,
        "message": "ner found person_name in >=50% of the scanned cells.",
        "source_identity_rate": None,
        "source_compared": False,
        "source": "ner",
        "model": dict(MODEL),
        "band": None,
        "dismissed": False,
        "promoted": severity == "fail",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": "2026-11-16T00:00:00+00:00",
        "residual_pii": [finding],
        "fk_preservation": [],
        "policy_validation": [],
        "pass_count": 3,
        "warning_count": 0,
        "fail_count": 1,
        "error_count": 0,
        "pass_failed_with": None,
        "detectors": [{"source": "regex", "model": None}, {"source": "ner", "model": dict(MODEL)}],
        "tables_checked": ["customers", "orders"],
        "config_sha256": None,
        "keys": [],
    }


def blocked_error(*, leak: str | None = None) -> Exception:
    """A real `PostScanBlockedError` over `ner_report()`. `leak` replaces its text, so a test can
    prove the CLI prints the registry's fixed summary and never `str(error)`."""
    from decoy_engine.verification.postmask import PostScanBlockedError, post_scan_verdict

    report = ner_report()
    error = PostScanBlockedError(report, post_scan_verdict(report, ner_findings="fail"))
    if leak is not None:
        error.args = (leak,)
        error.message = leak
    return error
