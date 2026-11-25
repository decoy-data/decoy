"""The HTML renderer for one evidence manifest (pure: a manifest dict in, a string out)."""

from __future__ import annotations

import html as _html_mod
import json as _json
from typing import Any

_HTML_CSS = """\
body { font-family: monospace; max-width: 900px; margin: 2em auto; background: #111; color: #e0e0e0; }
h1 { color: #00d4aa; border-bottom: 1px solid #333; padding-bottom: 0.3em; }
h2 { color: #00d4aa; margin-top: 1.5em; }
table { border-collapse: collapse; width: 100%; margin: 0.5em 0 1em 0; }
th { background: #1e1e1e; color: #00d4aa; text-align: left; padding: 0.4em 0.8em; border: 1px solid #333; }
td { padding: 0.4em 0.8em; border: 1px solid #333; word-break: break-all; }
tr:nth-child(even) td { background: #1a1a1a; }
.badge-ok { color: #00d4aa; }
.badge-warn { color: #f0a500; }
.badge-none { color: #666; }
.fp { font-size: 0.85em; color: #aaa; }
footer { margin-top: 2em; border-top: 1px solid #333; padding-top: 0.8em; font-size: 0.85em; color: #666; }
"""


def _esc(value: Any) -> str:
    """HTML-escape a value for safe embedding in attributes and text."""
    return _html_mod.escape(str(value) if value is not None else "")


def render_html(manifest: dict[str, Any]) -> str:
    """Render a manifest dict to a self-contained, offline HTML report.

    EVIDENCE-SAFE: builds entirely from the manifest dict. Does NOT read any
    source CSV, output CSV, or pipeline YAML file from disk. The manifest
    itself never contains raw row values (see build_manifest in evidence.py).

    Returns a complete HTML document as a string.
    """
    run_id = _esc(manifest.get("run_id", "?"))
    run_ts = _esc(manifest.get("run_timestamp", "?"))
    schema_v = _esc(manifest.get("schema_version", "?"))
    producer = _esc(manifest.get("producer", "?"))
    cli_v = _esc(manifest.get("cli_version", "?"))
    eng_v = _esc(manifest.get("engine_version", "?"))
    pipeline_path = _esc(manifest.get("pipeline_path", "?"))
    pipeline_fp = manifest.get("pipeline_fingerprint") or ""
    pipeline_fp_esc = _esc(pipeline_fp)
    key_label = _esc(manifest.get("key_label") or "(none)")

    warnings_list: list[Any] = manifest.get("warnings") or []
    timings_list: list[Any] = manifest.get("timings") or []
    strategies_list: list[Any] = manifest.get("strategies") or []
    input_fps: dict[str, Any] = manifest.get("input_fingerprints") or {}
    output_fps: dict[str, Any] = manifest.get("output_fingerprints") or {}
    row_counts: dict[str, Any] = manifest.get("row_counts") or {}

    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en">')
    parts.append("<head>")
    parts.append('<meta charset="UTF-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append("<title>Decoy Evidence Report</title>")
    parts.append(f"<style>{_HTML_CSS}</style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append("<h1>Decoy Evidence Report</h1>")

    # --- Run Summary ---
    parts.append("<h2>Run Summary</h2>")
    parts.append("<table>")
    parts.append("<tr><th>Field</th><th>Value</th></tr>")
    for label, val in [
        ("Schema Version", schema_v),
        ("Producer", producer),
        ("Run ID", run_id),
        ("Run Timestamp", run_ts),
        ("CLI Version", cli_v),
        ("Engine Version", eng_v),
        ("Key Label", key_label),
    ]:
        parts.append(f"<tr><td>{label}</td><td>{val}</td></tr>")
    parts.append("</table>")

    # --- Pipeline Identity ---
    parts.append("<h2>Pipeline Identity</h2>")
    parts.append("<table>")
    parts.append("<tr><th>Field</th><th>Value</th></tr>")
    parts.append(f"<tr><td>Pipeline Path</td><td>{pipeline_path}</td></tr>")
    parts.append(f'<tr><td>Pipeline Fingerprint</td><td class="fp">{pipeline_fp_esc}</td></tr>')
    parts.append("</table>")

    # --- Input Fingerprints ---
    if input_fps:
        parts.append("<h2>Input Fingerprints</h2>")
        parts.append("<table>")
        parts.append(
            "<tr><th>Table</th><th>Path</th><th>Fingerprint</th><th>Method</th><th>Size (bytes)</th></tr>"
        )
        for tname, info_val in input_fps.items():
            if not isinstance(info_val, dict):
                continue
            fp = _esc(info_val.get("fingerprint") or "(none)")
            method = _esc(info_val.get("fingerprint_method") or "?")
            size = _esc(info_val.get("size_bytes") or "?")
            path_v = _esc(info_val.get("path") or "?")
            parts.append(
                f"<tr><td>{_esc(tname)}</td><td>{path_v}</td>"
                f'<td class="fp">{fp}</td><td>{method}</td><td>{size}</td></tr>'
            )
        parts.append("</table>")

    # --- Output Fingerprints ---
    if output_fps:
        parts.append("<h2>Output Fingerprints</h2>")
        parts.append("<table>")
        parts.append(
            "<tr><th>Table</th><th>Path</th><th>Fingerprint</th><th>Method</th><th>Size (bytes)</th></tr>"
        )
        for tname, info_val in output_fps.items():
            if not isinstance(info_val, dict):
                continue
            fp = _esc(info_val.get("fingerprint") or "(none)")
            method = _esc(info_val.get("fingerprint_method") or "?")
            size = _esc(info_val.get("size_bytes") or "?")
            path_v = _esc(info_val.get("path") or "?")
            parts.append(
                f"<tr><td>{_esc(tname)}</td><td>{path_v}</td>"
                f'<td class="fp">{fp}</td><td>{method}</td><td>{size}</td></tr>'
            )
        parts.append("</table>")

    # --- Row Counts ---
    if row_counts:
        parts.append("<h2>Row Counts</h2>")
        parts.append("<table>")
        parts.append("<tr><th>Table</th><th>Rows</th></tr>")
        for tname, count in row_counts.items():
            parts.append(f"<tr><td>{_esc(tname)}</td><td>{_esc(count)}</td></tr>")
        parts.append("</table>")

    # --- Masking Strategies ---
    if strategies_list:
        parts.append("<h2>Masking Strategies</h2>")
        parts.append("<table>")
        parts.append("<tr><th>Table</th><th>Column</th><th>Strategy</th></tr>")
        for s in strategies_list:
            if not isinstance(s, dict):
                continue
            parts.append(
                f"<tr><td>{_esc(s.get('table', '?'))}</td>"
                f"<td>{_esc(s.get('column', '?'))}</td>"
                f"<td>{_esc(s.get('strategy', '?'))}</td></tr>"
            )
        parts.append("</table>")

    # --- Node Timings ---
    if timings_list:
        parts.append("<h2>Node Timings</h2>")
        parts.append("<table>")
        parts.append(
            "<tr><th>Column</th><th>Strategy</th><th>Elapsed (ms)</th><th>Peak Mem Delta (KB)</th></tr>"
        )
        for t in timings_list:
            if not isinstance(t, dict):
                continue
            parts.append(
                f"<tr><td>{_esc(t.get('column', '?'))}</td>"
                f"<td>{_esc(t.get('strategy_type', '?'))}</td>"
                f"<td>{_esc(t.get('elapsed_ms', '?'))}</td>"
                f"<td>{_esc(t.get('peak_memory_delta_kb', '?'))}</td></tr>"
            )
        parts.append("</table>")

    # --- Warnings ---
    warn_count = len(warnings_list)
    parts.append("<h2>Warnings</h2>")
    if warn_count == 0:
        parts.append('<p class="badge-ok">No warnings recorded.</p>')
    else:
        parts.append(f'<p class="badge-warn">{_esc(warn_count)} warning(s) recorded.</p>')
        parts.append("<table>")
        parts.append(
            "<tr><th>#</th><th>Code</th><th>Provider</th><th>Column</th><th>Detail</th></tr>"
        )
        for i, w in enumerate(warnings_list, start=1):
            if isinstance(w, dict):
                wcode = _esc(w.get("code", "?"))
                wprov = _esc(w.get("provider", "?"))
                wcol = _esc(w.get("column", "(none)"))
                wdet = _esc(_json.dumps(w.get("detail") or {}))
                parts.append(
                    f"<tr><td>{i}</td><td>{wcode}</td><td>{wprov}</td>"
                    f"<td>{wcol}</td><td>{wdet}</td></tr>"
                )
            else:
                parts.append(f'<tr><td>{i}</td><td colspan="4">{_esc(w)}</td></tr>')
        parts.append("</table>")

    # --- Footer / omission disclaimer ---
    parts.append("<footer>")
    parts.append(
        "<p>Report generated from evidence-safe data only. "
        "Raw row/cell values are intentionally excluded from this report. "
        "The evidence manifest records strategy names, fingerprints, and metadata only. "
        "Data correctness and masking quality are not verified by this report.</p>"
    )
    parts.append("</footer>")
    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)
