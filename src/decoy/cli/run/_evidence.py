"""The `--evidence-out` manifest of `decoy run`."""

import json as _json
from pathlib import Path

import typer

from decoy._atomic import AtomicWriteError, WriteMode, describe, write_local_target
from decoy._version import __version__ as _cli_version
from decoy.cli.exit_codes import EXIT_RUNTIME
from decoy.cli.io import LayoutError, find_project
from decoy.cli.run._context import RunContext
from decoy.ui.output import OutputMode
from decoy.ui.theme import error, warn


def _marked_project_root(config: Path) -> Path | None:
    """The root of the project holding the YAML when it has a marker; None otherwise.

    Paths are recorded project-relative only under a marker, which a verifier can find again
    from the manifest's folder. Without one they are recorded absolute.
    """
    try:
        found = find_project(config.resolve().parent, None)
    except LayoutError:
        return None
    return None if found.implicit else found.root


def write_evidence(ctx: RunContext) -> None:
    """Build the run's evidence manifest once, write it when `--evidence-out` is set (a failed
    write exits EXIT_RUNTIME), and store it as the run's library record (LIB L3a, plan 4.16; a
    failed store only warns, plan 4.17)."""
    # For plain and chunked runs; chunked runs have no row_counts/timings/warnings (see the flag
    # help). A --duckdb-source run fingerprints a transient snapshot, so it records nothing.
    if ctx._ev_config_dict is None:
        return
    from decoy.cli.evidence import build_manifest
    from decoy.cli.library import StoreReport, store_evidence

    if ctx.duckdb_source:
        ctx.library_report = StoreReport("off")
        return
    manifest = build_manifest(
        pipeline_path=ctx.config,
        config_dict=ctx._ev_config_dict,
        run_result={"row_counts": ctx._ev_row_counts or {}},
        cli_version=_cli_version,
        engine_version=ctx._ev_engine_version or "unknown",
        key_label=ctx.key_label,
        run_id=ctx.invocation_id,
        place_target=ctx.layout.place_target if ctx.layout is not None else None,
        project_root=_marked_project_root(ctx.config),
        evidence_path=ctx.evidence_out,
        timings=ctx._ev_timings,
        engine_warnings=ctx._ev_engine_warnings,
    )
    if ctx.evidence_out is not None:
        try:
            write_local_target(
                ctx.evidence_out, _json.dumps(manifest, indent=2).encode("utf-8"), WriteMode.REPLACE
            )
        except AtomicWriteError as exc:
            ctx.state.err_console.print(error("error:"), describe(exc), markup=False)
            raise typer.Exit(code=EXIT_RUNTIME)
        if ctx.state.mode is not OutputMode.json and ctx.state.mode is not OutputMode.quiet:
            from decoy.ui.theme import success as _success

            ctx.state.console.print(_success("Evidence:"), str(ctx.evidence_out))
    ctx.library_report = store_evidence(
        manifest,
        pipeline=ctx.config,
        invocation_id=ctx.invocation_id,
        enabled=not ctx.no_library,
        producer={
            "name": "decoy-cli",
            "version": _cli_version,
            "engine_version": ctx._ev_engine_version or "unknown",
        },
    )
    if ctx.library_report.status == "failed":
        # Plan 4.17: a library that cannot be written never fails a run that worked.
        ctx.state.err_console.print(
            warn("warning:"),
            f"the run's evidence record was not stored ({ctx.library_report.code})",
            markup=False,
        )
