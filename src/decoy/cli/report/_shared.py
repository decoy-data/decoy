"""Helpers every ``decoy report`` subcommand shares: the report writer and the manifest loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from decoy._atomic import WriteMode, write_local_target
from decoy.cli.evidence import (
    ManifestError,
    read_manifest,
)
from decoy.cli.exit_codes import EXIT_USAGE
from decoy.cli.io import ReportTarget
from decoy.ui.output import (
    OutputMode,
    OutputState,
    emit_json,
)
from decoy.ui.summary import (
    announce_report,
)
from decoy.ui.theme import code, error, hint


def _write_out(state: OutputState, target: ReportTarget, text: str) -> Path | None:
    """Write a report file (owner-only); a typed target refuses on failure, a default only warns."""
    with target.recording():
        for path in target.paths:
            write_local_target(path, text.encode("utf-8"), WriteMode.REPLACE)
    return announce_report(state, target)


def _load_manifest(
    path: Path, state: OutputState, command: str, project: Path | None = None
) -> dict[str, Any]:
    """Read a manifest through the shared strict reader. Exit with EXIT_USAGE on a refusal."""
    try:
        return read_manifest(path, project)
    except ManifestError as exc:
        msg, missing = exc.message, exc.kind == "missing"
    if state.mode is OutputMode.json:
        emit_json(state, {"command": command, "status": "error", "error": msg})
    else:
        state.err_console.print(error("error:"), msg)
        if missing:
            how = code("decoy run pipeline.yaml --evidence-out evidence.json")
            state.err_console.print(" ", hint("hint:"), "produce an evidence file with", how)
    raise typer.Exit(code=EXIT_USAGE)
