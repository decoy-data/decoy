"""The evidence manifest of `decoy run`: the `--evidence-out` file and the library record."""

import contextlib
import json as _json
from collections.abc import Callable
from pathlib import Path

from rich.text import Text

from decoy._atomic import AtomicWriteError, WriteMode, describe, write_local_target
from decoy._version import __version__ as _cli_version
from decoy.cli.io import INTEGRITY_WRITE_FAILED, LayoutError, find_project, write_run_report
from decoy.cli.run._context import (
    EvidenceWriteRefusal,
    IntegrityWriteRefusal,
    RunContext,
    library_choice,
    library_label,
)
from decoy.ui.output import OutputMode
from decoy.ui.theme import warn


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


def _attempt_name(ctx: RunContext, final: Path) -> Path:
    """The sibling an attempt is written to: same folder, so the later replace is one rename."""
    return final.with_name(f".{final.name}.{ctx.invocation_id}.attempt")


def _manifest(ctx: RunContext, staged_file: Callable[[str], Path] | None) -> dict | None:
    """The manifest, or None when this run keeps no evidence. Fingerprints read the staged
    bytes, which the bind publishes unchanged; the recorded paths stay the final ones."""
    # Chunked runs have no row_counts/timings/warnings (see the --evidence-out help).
    # A --duckdb-source input is a transient snapshot with no defined fingerprint, so such a run
    # stores no evidence record (and refuses --evidence-out before it starts).
    store = not ctx.no_library and not ctx.duckdb_source
    if ctx._ev_config_dict is None or (ctx.evidence_out is None and not store):
        return None
    from decoy.cli.evidence import build_manifest

    return build_manifest(
        pipeline_path=ctx.config,
        config_dict=ctx._ev_config_dict,
        run_result={"row_counts": ctx._ev_row_counts or {}},
        cli_version=_cli_version,
        engine_version=ctx._ev_engine_version or "unknown",
        key_label=ctx.key_label,
        run_id=ctx.invocation_id,
        place_target=ctx.layout.place_target if ctx.layout is not None else None,
        read_target=staged_file,
        project_root=_marked_project_root(ctx.config),
        evidence_path=ctx.evidence_out,
        timings=ctx._ev_timings,
        engine_warnings=ctx._ev_engine_warnings,
    )


def write_evidence(ctx: RunContext) -> None:
    """The route with no delivery stage (`--chunked`): write the attempts, then publish them."""
    write_attempts(ctx, None)
    publish_attempts(ctx)


def write_attempts(ctx: RunContext, staged_file: Callable[[str], Path] | None) -> None:
    """Before the visibility point: write the evidence manifest and an explicit
    `--integrity-out` report under attempt names. Nothing live changes.

    A failed write raises the typed refusal (exit 3) and nothing is delivered.
    """
    ctx._manifest = _manifest(ctx, staged_file)
    # The publish after delivery cannot fail the run, so what it would refuse is refused now.
    failed = _blocked(ctx.evidence_out) if ctx.evidence_out is not None else None
    if failed is not None:
        raise EvidenceWriteRefusal(failed)
    if ctx.integrity_out is not None and ctx.integrity_out.is_dir():
        failed = write_run_report(ctx._post_scan, ctx.integrity_out, ctx.config_sha256)
        if failed is not None:
            raise IntegrityWriteRefusal(failed, code=INTEGRITY_WRITE_FAILED)
    if ctx._manifest is not None and ctx.evidence_out is not None:
        attempt = _attempt_name(ctx, ctx.evidence_out)
        failed = None
        try:
            _put(attempt, _json.dumps(ctx._manifest, indent=2).encode("utf-8"))
        except AtomicWriteError as exc:
            failed = describe(exc)
        if failed is not None:
            # Outside the block: the refusal has no context. `_errors.refused` prints and exits.
            raise EvidenceWriteRefusal(failed)
        ctx._attempts.append((attempt, ctx.evidence_out))
    if ctx.integrity_out is not None:
        attempt = _attempt_name(ctx, ctx.integrity_out)
        failed = write_run_report(ctx._post_scan, attempt, ctx.config_sha256)
        if failed is not None:
            raise IntegrityWriteRefusal(failed, code=INTEGRITY_WRITE_FAILED)
        if ctx._post_scan is not None:
            ctx._attempts.append((attempt, ctx.integrity_out))


def publish_attempts(ctx: RunContext) -> None:
    """After a delivered receipt: replace the live files with the attempts, then store the
    library record. The library store never changes the exit code (plan 4.17)."""
    published: list[Path] = []
    while ctx._attempts:
        attempt, final = ctx._attempts[0]
        _replace(ctx, attempt, final)
        published.append(final)
        del ctx._attempts[0]
        attempt.unlink()
    if ctx._manifest is None:
        _record_skipped(ctx)
        return
    if (
        ctx.evidence_out in published
        and ctx.state.mode is not OutputMode.json
        and ctx.state.mode is not OutputMode.quiet
    ):
        from decoy.ui.theme import success as _success

        ctx.state.console.print(_success("Evidence:"), str(ctx.evidence_out))
    from decoy.cli.library import store_evidence

    store = not ctx.no_library and not ctx.duckdb_source
    choice = library_choice(ctx)
    if choice.code is not None:
        return  # the root fault was warned about once, where it was found
    label = library_label(ctx.config)
    ctx.library_outcome = (
        store_evidence(
            ctx._manifest,
            root=choice.root,
            label=label,
            invocation_id=ctx.invocation_id,
            enabled=store,
        )
        if isinstance(label, str)
        else label
    )
    # Not gated on --quiet: a warning about a lost record is not chatter.
    if ctx.library_outcome.status == "failed":
        ctx.state.err_console.print(
            warn("warning:"),
            Text(
                f"{ctx.library_outcome.code}: the run's evidence record was not stored in the "
                "library; the run's result is unchanged."
            ),
        )


def _put(path: Path, data: bytes) -> None:
    """The one atomic write of this module: an attempt file, and its later replacement of the
    live file."""
    write_local_target(path, data, WriteMode.REPLACE)


def _blocked(final: Path) -> str | None:
    """The writer's own refusal text when `final` is a folder, which a later replace would hit."""
    if not final.is_dir():
        return None
    try:
        _put(final, b"")
    except AtomicWriteError as exc:
        return describe(exc)
    return None


def _replace(ctx: RunContext, attempt: Path, final: Path) -> None:
    """Replace one live file with its attempt. A failure is the typed refusal: exit 3 on the tail
    route (`--chunked`, a fixed folder), and one cleanup warning inside the strict stage."""
    failed = None
    try:
        _put(final, attempt.read_bytes())
    except AtomicWriteError as exc:
        failed = describe(exc)
    if failed is None:
        return
    if final == ctx.integrity_out:
        raise IntegrityWriteRefusal(failed, code=INTEGRITY_WRITE_FAILED)
    raise EvidenceWriteRefusal(failed)


def discard_attempts(ctx: RunContext) -> None:
    """Remove the attempt files that remain. Live files are never touched."""
    leftover, ctx._attempts[:] = list(ctx._attempts), []
    for attempt, _final in leftover:
        with contextlib.suppress(FileNotFoundError):
            attempt.unlink()


def _record_skipped(ctx: RunContext) -> None:
    from decoy.cli.library import StoreOutcome

    if ctx.library_outcome is None or ctx.library_outcome.status != "failed":
        ctx.library_outcome = StoreOutcome("skipped")
