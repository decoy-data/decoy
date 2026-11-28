"""``decoy report diff``: compare two manifests, and their data when the files exist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from decoy.cli.exit_codes import EXIT_USAGE
from decoy.cli.report._compare import compare_data, compare_manifests
from decoy.cli.report._shared import _load_manifest
from decoy.safe_url import display_path, display_safe
from decoy.ui.output import (
    OutputMode,
    emit_json,
    setup_output,
)
from decoy.ui.theme import accent, code, error, hint, info, success, warn

_DIFF_EPILOG = """\
Examples:

  decoy report diff a.json b.json
    Compare two evidence manifests. Always runs the manifest/fingerprint-level
    comparison (pipeline + per-table fingerprints + row-count deltas +
    warnings). If the referenced output files still exist, ALSO runs the
    data-level comparison (row/column counts read from the CSV/Parquet).

  decoy report diff a.json b.json --json
    Emit structured JSON: manifest-level fields always, plus any_data_change +
    table_deltas when the output files were present.

  decoy report diff a.json b.json --require-data
    Hard-fail (exit 1) if any referenced output file is missing, instead of
    degrading to manifest-level only. For scripted callers that need the
    data-level comparison to have run.

What diff compares at the MANIFEST level (always):
  - Pipeline fingerprint change.
  - Per-table input/output fingerprint changes (added/removed/changed).
  - Row count deltas per table.
  - Warnings added or removed.

What diff compares at the DATA level (when output files exist):
  - Row counts per table (from the actual data files).
  - Schema: columns added/removed/type-changed.
  - Per column: null-count delta, unique-count delta.

What diff does NOT compare:
  - Raw row or cell values (never -- evidence-safe by design).
  - Platform-managed state, audit logs, or remote job history.

Missing output files are a NOTE, not a failure: the manifest-level comparison
still runs. Pass --require-data to restore the strict hard-fail.

Methodology: pandas.Series.nunique() / .isnull().sum() for column-level
counts (pandas v2.x). No novel statistical method is used.
"""


def _diff(
    evidence_file_a: Path = typer.Argument(
        ...,
        exists=False,
        dir_okay=False,
        help="Path to the first evidence manifest JSON.",
    ),
    evidence_file_b: Path = typer.Argument(
        ...,
        exists=False,
        dir_okay=False,
        help="Path to the second evidence manifest JSON.",
    ),
    require_data: bool = typer.Option(
        False,
        "--require-data",
        help=(
            "Hard-fail (EXIT_USAGE) when a referenced output file is missing, "
            "instead of degrading to manifest-level only."
        ),
    ),
    json_: bool = typer.Option(False, "--json", help="Emit structured JSON."),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress stdout. Errors still go to stderr."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug-level logs."),
) -> None:
    """Compare two evidence manifests: fingerprints always, data when present.

    A lossless superset of the former `report diff` (data-level) and `report
    compare` (manifest-level). It ALWAYS runs the manifest/fingerprint-level
    comparison (works even when output files are gone). It ADDITIONALLY runs
    the data-level comparison (reading the CSV/Parquet the manifests
    reference) when those output files exist; when a file is missing it prints
    a note and reports manifest-level only -- unless --require-data is set,
    which restores the strict hard-fail.

    EVIDENCE-SAFE: only aggregate counts are reported -- no raw values.
    Reads only the files it is given; never connects to a server or catalog.
    """
    state = setup_output(json_, quiet, verbose)

    manifest_a = _load_manifest(evidence_file_a, state, "report diff")
    manifest_b = _load_manifest(evidence_file_b, state, "report diff")

    # --- Manifest/fingerprint-level comparison (always) ---
    manifest_diff = display_safe(compare_manifests(manifest_a, manifest_b))

    # --- Data-level comparison (when the referenced output files exist) ---
    data_result: dict[str, Any] | None = None
    data_dep_error: str | None = None
    try:
        data_result = compare_data(
            manifest_a,
            manifest_b,
            manifest_file_a=evidence_file_a,
            manifest_file_b=evidence_file_b,
        )
    except RuntimeError as _dep_err:
        # pandas (or a parquet reader) is not installed. Treat the data level
        # as unavailable rather than failing the whole comparison.
        data_dep_error = str(_dep_err)

    missing_files: list[str] = list(data_result["missing_files"]) if data_result else []
    refused = _refusal_text(data_result["refusals"]) if data_result else None
    data_available = data_result is not None and not missing_files

    # --require-data: restore the strict hard-fail when the data level could
    # not run (missing output files, or no pandas).
    if require_data and not data_available:
        if missing_files:
            msg = "Output files are missing or unreadable and cannot be compared: " + ", ".join(
                missing_files
            )
            if refused:
                msg += "; " + refused
        else:
            msg = data_dep_error or "data-level comparison is unavailable."
        if state.mode is OutputMode.json:
            emit_json(state, {"command": "report diff", "status": "error", "error": msg})
        else:
            state.err_console.print(error("error:"), msg)
            state.err_console.print(
                " ",
                hint("note:"),
                "output files may have been moved, deleted, or corrupted after "
                "the run completed; drop --require-data for manifest-level only.",
            )
        raise typer.Exit(code=EXIT_USAGE)

    # --- JSON envelope: manifest-level fields always, data-level when ran ---
    if state.mode is OutputMode.json:
        payload: dict[str, Any] = {
            "command": "report diff",
            "status": "ok",
            "evidence_file_a": display_path(evidence_file_a),
            "evidence_file_b": display_path(evidence_file_b),
        }
        payload.update(manifest_diff)
        if data_available and data_result is not None:
            payload["data_level"] = "compared"
            payload["any_data_change"] = data_result["any_data_change"]
            payload["table_deltas"] = data_result["table_deltas"]
        else:
            payload["data_level"] = "skipped"
            payload["any_data_change"] = None
            payload["table_deltas"] = []
            payload["missing_files"] = missing_files
            if data_dep_error or refused:
                payload["data_note"] = data_dep_error or refused
        emit_json(state, payload)
        return

    if state.mode is OutputMode.quiet:
        return

    # --- Human-readable: manifest level first, then data level ---
    manifest_changed = manifest_diff["any_change"]
    data_changed = bool(data_available and data_result and data_result["any_data_change"])

    if not manifest_changed and not data_changed:
        state.console.print(
            success("ok"),
            "no changes detected between the two evidence manifests.",
        )
        state.console.print(
            " ",
            hint("note:"),
            "pipeline fingerprint, input/output fingerprints, row counts, "
            "and warnings are identical.",
        )
    else:
        state.console.print(
            warn("changes detected"),
            "between",
            code(display_path(evidence_file_a)),
            "and",
            code(display_path(evidence_file_b)),
        )
        state.console.print("")
        if manifest_changed:
            state.console.print(accent("Manifest level:"))
            _render_manifest_compare(state, manifest_diff)

    # Data-level section (only when it ran).
    if data_available and data_result is not None:
        state.console.print("")
        state.console.print(accent("Data level:"))
        if not data_result["any_data_change"]:
            state.console.print(
                success("ok"),
                "row counts, schema, and column-level stats are identical.",
            )
        else:
            _render_data_diff(state, data_result)
        state.console.print(
            " ",
            hint("scope:"),
            "aggregate counts only; raw values not included.",
        )
    else:
        # Degraded: the output files are gone. Note, not failure.
        state.console.print("")
        note = (
            "output files missing"
            + (" or refused" if refused else "")
            + " ("
            + ", ".join(missing_files)
            + ")"
            + (f"; {refused}" if refused else "")
            if missing_files
            else (data_dep_error or "data-level comparison unavailable")
        )
        state.err_console.print(
            " ",
            hint("note:"),
            f"data-level comparison skipped: {note}; reported manifest-level "
            "only. Pass --require-data to hard-fail instead.",
        )


def _refusal_text(refusals: list[tuple[str, str]]) -> str | None:
    """The fixed `refused: code: message` text for refused outputs, or None when none were."""
    if not refusals:
        return None
    return "refused: " + "; ".join(f"{code}: {message}" for code, message in refusals)


def _render_data_diff(state: Any, diff_result: dict[str, Any]) -> None:
    """Render a `compare_data` result to the terminal (per-table deltas)."""
    from decoy.ui.table import make_table

    for td in diff_result["table_deltas"]:
        tname = td["table"]
        row_delta = td.get("row_count_delta")
        added = td.get("columns_added") or []
        removed = td.get("columns_removed") or []
        col_deltas = td.get("column_deltas") or []

        if (row_delta is not None and row_delta != 0) or added or removed or col_deltas:
            state.console.print(warn(f"table: {tname}"))
            if row_delta is not None and row_delta != 0:
                sign = "+" if row_delta > 0 else ""
                state.console.print(
                    " ",
                    hint("row count:"),
                    code(str(td.get("row_count_a"))),
                    "->",
                    code(str(td.get("row_count_b"))),
                    hint(f"({sign}{row_delta})"),
                )
            if added:
                state.console.print(" ", hint("columns added:"), code(", ".join(added)))
            if removed:
                state.console.print(" ", hint("columns removed:"), code(", ".join(removed)))
            if col_deltas:
                t = make_table(
                    "Column",
                    "Null Count Delta",
                    "Unique Count Delta",
                    "Dtype Changed",
                    title=f"{tname} column deltas",
                )
                for cd in col_deltas:
                    nc_d = str(cd.get("null_count_delta", ""))
                    uc_d = str(cd.get("unique_count_delta", ""))
                    dtype_ch = "yes" if cd.get("dtype_changed") else "no"
                    t.add_row(cd["column"], nc_d, uc_d, dtype_ch)
                state.console.print(t)


def _render_manifest_compare(state: Any, diff: dict[str, Any]) -> None:
    """Render a `compare_manifests` result to the terminal (shared helper).

    Prints the pipeline-fingerprint change, per-table input/output fingerprint
    changes, row-count deltas, and warnings added/removed. Caller decides the
    headline and whether any change was found.
    """
    from decoy.ui.table import make_table

    # Pipeline fingerprint
    if diff["pipeline_fingerprint_changed"]:
        state.console.print(warn("Pipeline fingerprint changed:"))
        state.console.print("  old:", code(_fp_short(diff["old_pipeline_fingerprint"])))
        state.console.print("  new:", code(_fp_short(diff["new_pipeline_fingerprint"])))
        state.console.print("")

    # Input fingerprints
    in_ch = diff["input_fingerprint_changes"]
    if in_ch["changed"] or in_ch["added"] or in_ch["removed"]:
        t = make_table(
            "Table", "Change", "Old Fingerprint", "New Fingerprint", title="Input fingerprints"
        )
        for c in in_ch["changed"]:
            t.add_row(c["table"], "changed", _fp_short(c["old"]), _fp_short(c["new"]))
        for a in in_ch["added"]:
            t.add_row(a["table"], "added", "(none)", _fp_short(a["fingerprint"]))
        for r in in_ch["removed"]:
            t.add_row(r["table"], "removed", _fp_short(r["fingerprint"]), "(none)")
        state.console.print(t)

    # Output fingerprints
    out_ch = diff["output_fingerprint_changes"]
    if out_ch["changed"] or out_ch["added"] or out_ch["removed"]:
        t = make_table(
            "Table", "Change", "Old Fingerprint", "New Fingerprint", title="Output fingerprints"
        )
        for c in out_ch["changed"]:
            t.add_row(c["table"], "changed", _fp_short(c["old"]), _fp_short(c["new"]))
        for a in out_ch["added"]:
            t.add_row(a["table"], "added", "(none)", _fp_short(a["fingerprint"]))
        for r in out_ch["removed"]:
            t.add_row(r["table"], "removed", _fp_short(r["fingerprint"]), "(none)")
        state.console.print(t)

    # Row count deltas
    if diff["row_count_deltas"]:
        t = make_table("Table", "Old", "New", "Delta", title="Row count deltas")
        for d in diff["row_count_deltas"]:
            delta_str = str(d["delta"]) if d["delta"] is not None else "?"
            if isinstance(d["delta"], int) and d["delta"] > 0:
                delta_str = f"+{delta_str}"
            t.add_row(d["table"], str(d["old"]), str(d["new"]), delta_str)
        state.console.print(t)

    # Warnings diff
    if diff["warnings_added"]:
        state.console.print(warn(f"{len(diff['warnings_added'])} warning(s) added:"))
        for w in diff["warnings_added"]:
            if isinstance(w, dict):
                state.console.print(
                    "  +",
                    code(w.get("code", "?")),
                    info(f"col={w.get('column') or '(none)'}"),
                )
            else:
                state.console.print("  +", code(str(w)))

    if diff["warnings_removed"]:
        state.console.print(success(f"{len(diff['warnings_removed'])} warning(s) removed:"))
        for w in diff["warnings_removed"]:
            if isinstance(w, dict):
                state.console.print(
                    "  -",
                    code(w.get("code", "?")),
                    info(f"col={w.get('column') or '(none)'}"),
                )
            else:
                state.console.print("  -", code(str(w)))


def _fp_short(fp: str | None) -> str:
    """Return a shortened fingerprint for display (prefix + ellipsis)."""
    if not fp:
        return "(none)"
    return (fp[:23] + "...") if len(fp) > 23 else fp
