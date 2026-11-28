"""``decoy report verify``: re-hash recorded files and report drift."""

from __future__ import annotations

from pathlib import Path

import typer

from decoy.cli.evidence import (
    ManifestError,
    verify_manifest,
)
from decoy.cli.exit_codes import EXIT_FINDINGS, EXIT_USAGE
from decoy.cli.report._shared import _load_manifest
from decoy.safe_url import display_file_name, display_path
from decoy.ui.output import (
    OutputMode,
    emit_json,
    setup_output,
)
from decoy.ui.theme import error, hint, success

_VERIFY_EPILOG = """\
Examples:

  decoy report verify evidence.json
    Check all fingerprints (pipeline, inputs, outputs, manifest integrity).
    Exits 0 when all match; non-zero when any changed.

  decoy report verify evidence.json --json
    Emit a structured JSON result with the list of issues found.

What verify checks:
  - manifest_hash: detects edits to the manifest JSON file.
  - pipeline_fingerprint: detects changes to pipeline.yaml.
  - input_fingerprints: detects changes to source data files.
  - output_fingerprints: detects changes to masked/generated output files.

What verify does NOT check:
  - Whether the output was produced by the declared pipeline.
  - Data correctness or masking quality.
  - Platform audit logs, RBAC, or schedule history.
  - Network, vault, or secrets accessibility.

Integrity limit: manifest_hash is an UNKEYED SHA-256 check. It detects
accidental drift; it does NOT detect a motivated tamperer who can edit the
manifest and recompute the hash. Keyed signing is platform R4 territory.

Exit codes: 0 clean; 4 fingerprint drift detected; 1 bad input.

See also: decoy report show, decoy run --evidence-out.
"""


def _verify(
    evidence_file: Path = typer.Argument(
        ...,
        exists=False,  # checked via _load_manifest for a cleaner error
        dir_okay=False,
        help="Path to a local evidence manifest JSON.",
    ),
    json_: bool = typer.Option(
        False,
        "--json",
        help="Emit a structured JSON result instead of human-readable output.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress stdout. Errors still go to stderr; exit code carries the result.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug-level CLI logs on stderr."
    ),
    project: Path | None = typer.Option(
        None, "--project", help="Project root for a manifest's project-relative paths."
    ),
) -> None:
    """Verify a local evidence manifest's fingerprints against current files.

    Re-hashes the pipeline config, input files, and output files and
    compares against the fingerprints recorded in the manifest. Also checks
    manifest_hash to detect edits to the manifest file itself.

    Exits 0 when all fingerprints match (no drift). Exits non-zero
    (EXIT_FINDINGS) when any fingerprint has changed.

    Distinct from `report integrity` (post-mask residual-PII / FK / policy on
    a masked file plus `--source`): verify is manifest fingerprint-drift.

    Integrity limit: manifest_hash is an UNKEYED SHA-256 check. It detects
    accidental drift (file changes since the run), NOT a motivated tamperer
    who can edit the manifest and recompute the hash. Keyed signing (R4) is
    required for adversarial authenticity guarantees.
    """
    state = setup_output(json_, quiet, verbose)
    manifest = _load_manifest(evidence_file, state, "report verify", project)
    refusal = None
    try:
        issues = verify_manifest(manifest, manifest_file=evidence_file, project=project)
    except ManifestError as exc:
        refusal, issues = exc.message, []
    if refusal is not None:
        if state.mode is OutputMode.json:
            emit_json(state, {"command": "report verify", "status": "error", "error": refusal})
        else:
            state.err_console.print(error("error:"), refusal)
        raise typer.Exit(code=EXIT_USAGE)

    if state.mode is OutputMode.json:
        emit_json(
            state,
            {
                "command": "report verify",
                "status": "ok" if not issues else "fingerprint_mismatch",
                "evidence_file": display_path(evidence_file),
                "issues": issues,
                "issue_count": len(issues),
            },
        )
        if issues:
            raise typer.Exit(code=EXIT_FINDINGS)
        return

    if state.mode is OutputMode.quiet:
        if issues:
            raise typer.Exit(code=EXIT_FINDINGS)
        return

    if not issues:
        state.console.print(
            success("OK"),
            f"All fingerprints match. ({display_file_name(evidence_file)})",
        )
        return

    state.err_console.print(
        error("INTEGRITY CHECK FAILED: fingerprint mismatch"),
        f"{len(issues)} fingerprint(s) changed in {display_file_name(evidence_file)}",
    )
    for issue in issues:
        state.err_console.print(" ", hint("-"), issue)
    state.err_console.print(
        " ",
        hint("hint:"),
        "files may have changed since the evidence was recorded, "
        "or the manifest file may have been edited.",
    )
    state.err_console.print(
        " ",
        hint("note:"),
        "manifest_hash is an UNKEYED SHA-256 check; it detects accidental "
        "drift, not adversarial edits. Keyed signing is platform R4 territory.",
    )
    raise typer.Exit(code=EXIT_FINDINGS)
