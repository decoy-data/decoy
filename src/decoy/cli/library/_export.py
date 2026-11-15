"""`decoy library export`: write the library as `decoy-library-export/v1` (plan 4.11, 4.3a; L4b).

The engine owns the codec (`decoy_engine.records.export_lines` and each kind's `export_rule`) so
the platform importer reads exactly what is written: path fields reduced to file names, link
remapping, recomputed ids, the `source_id` wrapper and the header are all the engine's. The CLI
only chooses the records, hands over their raw verified envelopes (`Library.get(...).raw`, never
a typed view) in link order (every link target before the record that links to it), names the
refs, and writes the lines through the atomic writer's user-path form (0600).

Owner decision (2026-11-12): the codec's behavior is accepted. A default export withholds the
records this version cannot strip (an unknown kind, or a payload with fields this version does
not know) and names them in the header's `withheld_records`; `--keep-paths` exports every record
byte for byte. Scratch is never read. Job logs do not exist until L5b, so `--include-logs`
exports none for now.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer

from decoy.cli.exit_codes import EXIT_OK
from decoy.cli.library._cli import library_option, start
from decoy.ui.output import OutputMode, OutputState
from decoy.ui.theme import warn

__all__ = ["export_command"]


def _say(state: OutputState, *parts: object) -> None:
    if state.mode is OutputMode.default:
        state.console.print(*parts, soft_wrap=True, markup=False, highlight=False)


def _notice(state: OutputState, *parts: object) -> None:
    state.err_console.print(warn("notice:"), *parts, markup=False, highlight=False)


def export_command(
    out: Path = typer.Option(
        ..., "--output", "-o", metavar="FILE", help="Write the export here (0600)."
    ),
    kind: str | None = typer.Option(None, "--kind", metavar="K", help="Only records of this kind."),
    since: str | None = typer.Option(
        None,
        "--since",
        metavar="D",
        help="Only records made at or after D (YYYY-MM-DD or ISO time).",
    ),
    ref: str | None = typer.Option(
        None,
        "--ref",
        metavar="R",
        help="Only R (a ref, id or KIND/latest) and every record it links to.",
    ),
    include_logs: bool = typer.Option(
        False, "--include-logs", help="Add the job logs of the exported runs (none exist yet)."
    ),
    keep_paths: bool = typer.Option(
        False,
        "--keep-paths",
        help="Keep paths as recorded and export every record byte for byte. Without it, paths are "
        "reduced to file names and records this version cannot strip are withheld.",
    ),
    library: Path | None = library_option(),
) -> None:
    """Export records as one self-verifying JSON Lines file the platform can import."""
    from decoy_engine.records import RecordError

    from decoy.cli.library import (
        LibraryError,
        TargetError,
        check_destination,
        export_lines,
        export_select,
        resolve_target,
        write_user_file,
    )
    from decoy.cli.library._read import _instant as parse_instant

    cmd = start("library export")
    state = cmd.state
    cutoff: datetime | None = None
    if since is not None:
        try:
            cutoff = parse_instant(since)
        except ValueError:
            cutoff = None
        if cutoff is None:
            cmd.fail("--since takes a date (YYYY-MM-DD) or an ISO time")
    if ref is not None and (kind is not None or since is not None):
        cmd.fail("--ref exports what the ref reaches; it cannot be combined with --kind or --since")
    root = cmd.root(library)
    opened = cmd.library(root.path)
    caught: Exception | None = None
    try:
        check_destination(root.path, out)
        present = opened.present
    except LibraryError as exc:
        caught = exc
    if caught is not None:
        cmd.fail_library(caught)
    if not present:
        cmd.fail("there is no library to export here")
    target: str | None = None
    if ref is not None:
        problem: str | None = None
        try:
            target = resolve_target(opened, ref)
        except TargetError as exc:
            problem = str(exc)
        if problem is not None:
            cmd.fail(problem)
    lines: list[bytes] = []
    try:
        ids, refs = export_select(opened, kind=kind, since=cutoff, ref=ref, target=target)
        lines = export_lines(opened, ids, refs, keep_paths)
        write_user_file(out, b"".join(lines))
    except (LibraryError, RecordError) as exc:
        caught = exc
    if caught is not None:
        cmd.fail_library(caught)
    header = json.loads(lines[0])
    withheld = header.get("withheld_records") or []
    if withheld:
        _notice(
            state,
            f"withheld {len(withheld)} record(s) this version cannot strip: {', '.join(withheld)};",
            "rerun with --keep-paths to include them byte for byte",
        )
    if include_logs:
        _notice(state, "no job logs exist yet; none exported")
    _say(state, f"exported {header['record_count']} records to {out}")
    raise typer.Exit(code=EXIT_OK)
