"""The Markdown renderer for one evidence manifest (pure: a manifest dict in, a string out)."""

from __future__ import annotations

import json as _json
from typing import Any

from decoy.safe_url import redacted_location


def render_markdown(manifest: dict[str, Any]) -> str:
    """Render a manifest dict to a plain Markdown report.

    EVIDENCE-SAFE: builds entirely from the manifest dict. Does NOT read any
    source CSV, output CSV, or pipeline YAML file from disk.

    Returns a Markdown string suitable for writing to a .md file.
    """
    run_id = manifest.get("run_id", "?")
    run_ts = manifest.get("run_timestamp", "?")
    schema_v = manifest.get("schema_version", "?")
    producer = manifest.get("producer", "?")
    cli_v = manifest.get("cli_version", "?")
    eng_v = manifest.get("engine_version", "?")
    pipeline_path = manifest.get("pipeline_path", "?")
    pipeline_fp = manifest.get("pipeline_fingerprint") or "(none)"
    key_label = manifest.get("key_label") or "(none)"

    warnings_list: list[Any] = manifest.get("warnings") or []
    timings_list: list[Any] = manifest.get("timings") or []
    strategies_list: list[Any] = manifest.get("strategies") or []
    input_fps: dict[str, Any] = manifest.get("input_fingerprints") or {}
    output_fps: dict[str, Any] = manifest.get("output_fingerprints") or {}
    row_counts: dict[str, Any] = manifest.get("row_counts") or {}

    lines: list[str] = []
    lines.append("# Decoy Evidence Report")
    lines.append("")

    # --- Run Summary ---
    lines.append("## Run Summary")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    for label, val in [
        ("Schema Version", schema_v),
        ("Producer", producer),
        ("Run ID", run_id),
        ("Run Timestamp", run_ts),
        ("CLI Version", cli_v),
        ("Engine Version", eng_v),
        ("Key Label", key_label),
    ]:
        lines.append(f"| {label} | {val} |")
    lines.append("")

    # --- Pipeline Identity ---
    lines.append("## Pipeline Identity")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Pipeline Path | {pipeline_path} |")
    lines.append(f"| Pipeline Fingerprint | `{pipeline_fp}` |")
    lines.append("")

    # --- Input Fingerprints ---
    if input_fps:
        lines.append("## Input Fingerprints")
        lines.append("")
        lines.append("| Table | Path | Fingerprint | Method | Size (bytes) |")
        lines.append("|---|---|---|---|---|")
        for tname, info_val in input_fps.items():
            if not isinstance(info_val, dict):
                continue
            fp = info_val.get("fingerprint") or "(none)"
            method = info_val.get("fingerprint_method") or "?"
            size = str(info_val.get("size_bytes") or "?")
            path_v = redacted_location(str(info_val.get("path") or "?"))
            lines.append(f"| {tname} | {path_v} | `{fp}` | {method} | {size} |")
        lines.append("")

    # --- Output Fingerprints ---
    if output_fps:
        lines.append("## Output Fingerprints")
        lines.append("")
        lines.append("| Table | Path | Fingerprint | Method | Size (bytes) |")
        lines.append("|---|---|---|---|---|")
        for tname, info_val in output_fps.items():
            if not isinstance(info_val, dict):
                continue
            fp = info_val.get("fingerprint") or "(none)"
            method = info_val.get("fingerprint_method") or "?"
            size = str(info_val.get("size_bytes") or "?")
            path_v = redacted_location(str(info_val.get("path") or "?"))
            lines.append(f"| {tname} | {path_v} | `{fp}` | {method} | {size} |")
        lines.append("")

    # --- Row Counts ---
    if row_counts:
        lines.append("## Row Counts")
        lines.append("")
        lines.append("| Table | Rows |")
        lines.append("|---|---|")
        for tname, count in row_counts.items():
            lines.append(f"| {tname} | {count} |")
        lines.append("")

    # --- Masking Strategies ---
    if strategies_list:
        lines.append("## Masking Strategies")
        lines.append("")
        lines.append("| Table | Column | Strategy |")
        lines.append("|---|---|---|")
        for s in strategies_list:
            if not isinstance(s, dict):
                continue
            lines.append(
                f"| {s.get('table', '?')} | {s.get('column', '?')} | {s.get('strategy', '?')} |"
            )
        lines.append("")

    # --- Node Timings ---
    if timings_list:
        lines.append("## Node Timings")
        lines.append("")
        lines.append("| Column | Strategy | Elapsed (ms) | Peak Mem Delta (KB) |")
        lines.append("|---|---|---|---|")
        for t in timings_list:
            if not isinstance(t, dict):
                continue
            lines.append(
                f"| {t.get('column', '?')} | {t.get('strategy_type', '?')} "
                f"| {t.get('elapsed_ms', '?')} | {t.get('peak_memory_delta_kb', '?')} |"
            )
        lines.append("")

    # --- Warnings ---
    warn_count = len(warnings_list)
    lines.append("## Warnings")
    lines.append("")
    if warn_count == 0:
        lines.append("No warnings recorded.")
    else:
        lines.append(f"{warn_count} warning(s) recorded.")
        lines.append("")
        lines.append("| # | Code | Provider | Column | Detail |")
        lines.append("|---|---|---|---|---|")
        for i, w in enumerate(warnings_list, start=1):
            if isinstance(w, dict):
                wcode = w.get("code", "?")
                wprov = w.get("provider", "?")
                wcol = w.get("column") or "(none)"
                wdet = _json.dumps(w.get("detail") or {})
                lines.append(f"| {i} | {wcode} | {wprov} | {wcol} | {wdet} |")
            else:
                lines.append(f"| {i} | {w} | | | |")
    lines.append("")

    # --- Footer / omission disclaimer ---
    lines.append("---")
    lines.append("")
    lines.append(
        "*Report generated from evidence-safe data only. "
        "Raw row/cell values are intentionally excluded. "
        "The evidence manifest records strategy names, fingerprints, and metadata only. "
        "Data correctness and masking quality are not verified by this report.*"
    )
    lines.append("")

    return "\n".join(lines)
