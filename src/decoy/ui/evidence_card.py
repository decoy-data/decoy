"""The `decoy report show` evidence manifest summary card."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from decoy.ui.card import render_card
from decoy.ui.table import make_table
from decoy.ui.theme import warn


def render_manifest_card(
    state: Any,
    manifest: dict[str, Any],
    shown: dict[str, Any],
    evidence_file: Path,
    *,
    hash_ok: bool,
) -> None:
    """Human-readable evidence manifest summary card.

    `manifest` is the recorded manifest, `shown` its redacted copy for the path tables, and
    `hash_ok` the caller's `manifest_hash` check (informational only).
    """

    schema_v = manifest.get("schema_version", "?")
    run_id = manifest.get("run_id", "?")
    run_ts = manifest.get("run_timestamp", "?")
    cli_v = manifest.get("cli_version", "?")
    eng_v = manifest.get("engine_version", "?")
    pipeline_path = manifest.get("pipeline_path", "?")
    pipeline_fp = manifest.get("pipeline_fingerprint") or ""
    key_label = manifest.get("key_label") or "(none)"
    warnings_list = manifest.get("warnings") or []
    timings_list = manifest.get("timings") or []
    hash_status = "ok (unkeyed integrity check)" if hash_ok else "MISMATCH (manifest may be edited)"

    facts: list[tuple[str, str]] = [
        ("Schema version", schema_v),
        ("Producer", manifest.get("producer", "?")),
        ("Run ID", run_id[:16] + "..." if len(run_id) > 16 else run_id),
        ("Run timestamp", run_ts),
        ("CLI version", cli_v),
        ("Engine version", eng_v),
        ("Pipeline", pipeline_path),
        ("Pipeline fingerprint", pipeline_fp[:23] + "..." if pipeline_fp else "(none)"),
        ("Key label", key_label),
        ("Manifest hash", hash_status),
        ("Warnings", str(len(warnings_list))),
        ("Timings recorded", str(len(timings_list))),
    ]

    render_card(
        state,
        command="decoy report show",
        facts=facts,
        next_hint=f"decoy report verify {evidence_file}",
        status="ok" if hash_ok else "warn",
    )

    # The tables show the redacted copy.
    for group, title in (("input_fingerprints", "Input"), ("output_fingerprints", "Output")):
        entries = shown.get(group) or {}
        if not entries:
            continue
        t = make_table(
            "Table", "Path", "Fingerprint (prefix)", "Method", "Size", title=f"{title} fingerprints"
        )
        for tname, info in entries.items():
            if not isinstance(info, dict):
                continue
            fp = (info.get("fingerprint") or "")[:23] + "..."
            method = info.get("fingerprint_method") or "?"
            size = str(info.get("size_bytes") or "?")
            t.add_row(tname, str(info.get("path", "?")), fp, method, size)
        state.console.print(t)

    # Strategies table
    strategies = manifest.get("strategies") or []
    if strategies:
        t = make_table("Table", "Column", "Strategy", title="Masking strategies")
        for s in strategies:
            if not isinstance(s, dict):
                continue
            t.add_row(s.get("table", "?"), s.get("column", "?"), s.get("strategy", "?"))
        state.console.print(t)

    if not hash_ok:
        state.err_console.print(
            warn("warning:"),
            "manifest_hash does not match the manifest body. "
            "The manifest file may have been edited. "
            "Run `decoy report verify` for a full fingerprint check.",
        )
