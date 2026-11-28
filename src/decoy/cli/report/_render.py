"""``decoy report render``: write an HTML or Markdown report file."""

from __future__ import annotations

from pathlib import Path

import typer

from decoy._atomic import AtomicWriteError, WriteMode, describe, write_local_target
from decoy.cli.exit_codes import EXIT_USAGE
from decoy.cli.report._html import render_html
from decoy.cli.report._markdown import render_markdown
from decoy.cli.report._shared import _load_manifest
from decoy.safe_url import display_path
from decoy.ui.output import (
    OutputMode,
    emit_json,
    setup_output,
)
from decoy.ui.theme import code, error, hint, success

_RENDER_EPILOG = """\
Examples:

  decoy report render evidence.json --output report.html
    Render the manifest as a self-contained offline HTML report.

  decoy report render evidence.json --format markdown --output report.md
    Render the manifest as a plain Markdown report.

What the report includes:
  Run summary, pipeline identity (fingerprint), input/output fingerprints,
  row counts, masking strategies (names only), node timings, and warnings.

What the report intentionally excludes:
  Raw row values, PII samples, scan profile internals, diagnostic values.
  The evidence manifest records strategy names and fingerprints only; the
  report renders that safe subset.

See also: decoy report show, decoy report diff, decoy report verify.
"""


def _render(
    evidence_file: Path = typer.Argument(
        ...,
        exists=False,
        dir_okay=False,
        help="Path to a local evidence manifest JSON (produced by decoy run --evidence-out).",
    ),
    out: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Output file path (e.g. report.html or report.md).",
    ),
    format_: str = typer.Option(
        "html",
        "--format",
        help="Output format: 'html' (default) or 'markdown'.",
    ),
    json_: bool = typer.Option(
        False,
        "--json",
        help="Emit a JSON record of what was written instead of the human summary.",
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress stdout. Errors still go to stderr."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug-level CLI logs on stderr."
    ),
) -> None:
    """Render an evidence manifest to an HTML or Markdown report file.

    The report is built from the manifest only (evidence-safe). Raw row
    values, PII, and scan profile internals are never included.

    HTML output is self-contained and offline-capable (no CDN/external JS).
    Markdown output is plain text.
    """
    state = setup_output(json_, quiet, verbose)
    manifest = _load_manifest(evidence_file, state, "report render")

    fmt = format_.lower().strip()
    if fmt not in ("html", "markdown", "md"):
        msg = f"unknown format {format_!r}; use 'html' or 'markdown'."
        if state.mode is OutputMode.json:
            emit_json(state, {"command": "report render", "status": "error", "error": msg})
        else:
            state.err_console.print(error("error:"), msg)
        raise typer.Exit(code=EXIT_USAGE)

    if fmt in ("markdown", "md"):
        content = render_markdown(manifest)
    else:
        content = render_html(manifest)

    try:
        write_local_target(out, content.encode("utf-8"), WriteMode.REPLACE)
    except AtomicWriteError as exc:
        msg = f"could not write {out}: {describe(exc)}"
        if state.mode is OutputMode.json:
            emit_json(state, {"command": "report render", "status": "error", "error": msg})
        else:
            state.err_console.print(error("error:"), msg)
        raise typer.Exit(code=EXIT_USAGE)

    fmt_label = "Markdown" if fmt in ("markdown", "md") else "HTML"

    if state.mode is OutputMode.json:
        emit_json(
            state,
            {
                "command": "report render",
                "status": "ok",
                "evidence_file": display_path(evidence_file),
                "output": str(out),
                "format": fmt_label.lower(),
            },
        )
        return

    if state.mode is not OutputMode.quiet:
        state.console.print(
            success("ok"),
            f"{fmt_label} report written to",
            code(str(out)),
        )
        state.console.print(
            " ",
            hint("note:"),
            "report contains evidence-safe data only (no raw values).",
        )
