"""``decoy report show``: the union card, or a rendered report."""

from __future__ import annotations

from pathlib import Path

import typer

from decoy.cli import evidence
from decoy.cli.exit_codes import EXIT_USAGE
from decoy.cli.io import ReportTarget
from decoy.cli.report._html import render_html
from decoy.cli.report._markdown import render_markdown
from decoy.cli.report._shared import _load_manifest, _write_out
from decoy.safe_url import display_path
from decoy.ui.evidence_card import render_manifest_card
from decoy.ui.output import (
    OutputMode,
    emit_json,
    setup_output,
)
from decoy.ui.theme import code, error, success

_SHOW_EPILOG = """\
Examples:

  decoy report show evidence.json
    Print a summary of the evidence manifest to the terminal.

  decoy report show evidence.json --format html --output report.html
    Write a full HTML report from the evidence manifest.

  decoy report show evidence.json --json
    Emit the display copy of the evidence manifest as structured JSON.

The terminal card is the UNION of the former `report summarize` + `evidence
show`: run metadata + manifest_hash integrity status, input/output fingerprint
tables, masking strategies, and row counts.

Requirements:
  - An evidence manifest JSON produced by `decoy run --evidence-out`.

See also: decoy report render, decoy report verify.
"""


def _show(
    evidence_file: Path = typer.Argument(
        ...,
        exists=False,
        dir_okay=False,
        help="Path to an evidence manifest JSON (from `decoy run --evidence-out`).",
    ),
    format_: str = typer.Option(
        None,
        "--format",
        help=(
            "Output format when --output is given: 'html' or 'markdown'. "
            "Without --output, prints a terminal summary."
        ),
    ),
    out: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the report to this file path (requires --format).",
    ),
    json_: bool = typer.Option(False, "--json", help="Emit the evidence manifest as JSON."),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress stdout. Errors still go to stderr."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug-level logs."),
) -> None:
    """Render the evidence report from an evidence manifest file.

    Loads the evidence manifest at the given path and renders the UNION card
    (the former `report summarize` + `evidence show`): run metadata +
    manifest_hash integrity status, input/output fingerprint tables, masking
    strategies, and row counts. With --format + --output it instead writes an
    HTML or Markdown report (like `decoy report render`).

    Reads only the file it is given; never connects to a server or catalog.
    """
    state = setup_output(json_, quiet, verbose)
    manifest = _load_manifest(evidence_file, state, "report show")
    # The one display copy: JSON, the card and the written reports all print it.
    shown = evidence.display_manifest(manifest)

    # --json: emit the full manifest
    if state.mode is OutputMode.json:
        emit_json(
            state,
            {
                "command": "report show",
                "status": "ok",
                "evidence_file": display_path(evidence_file),
                "manifest": shown,
            },
        )
        return

    if state.mode is OutputMode.quiet:
        return

    # --format + --output: write file report
    if out is not None:
        fmt = (format_ or "html").lower().strip()
        if fmt not in ("html", "markdown", "md"):
            state.err_console.print(
                error("error:"),
                f"unknown format {format_!r}; use 'html' or 'markdown'.",
            )
            raise typer.Exit(code=EXIT_USAGE)
        if fmt in ("markdown", "md"):
            content = render_markdown(shown)
        else:
            content = render_html(shown)
        _write_out(state, ReportTarget(out, False), content)
        fmt_label = "Markdown" if fmt in ("markdown", "md") else "HTML"
        state.console.print(
            success("ok"), f"{fmt_label} report written to", code(display_path(out))
        )
        return

    # Default: the union card (fingerprints, strategies, manifest_hash status, row counts).
    hash_ok = evidence.manifest_hash_ok(manifest)
    render_manifest_card(state, shown, evidence_file, hash_ok=hash_ok)
