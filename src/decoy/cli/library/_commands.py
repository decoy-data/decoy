"""The `decoy library` command group (plan 4.15): `path`, `fsck` (L1c.2), the read commands
`list`, `show`, `diff`, `ref` (L4a, in `_read`), and `prune`, `clean` (in `_destructive`) and
`export` (in `_export`) (L4b). This module imports nothing from the record engine at import
time, so registering the group in `decoy.__main__` keeps `decoy --help` and `--version` free of
the engine import; each command loads the library when it runs.
"""

from __future__ import annotations

from pathlib import Path

import typer

from decoy.cli.exit_codes import EXIT_FINDINGS, EXIT_OK
from decoy.cli.library._cli import SOURCE, library_option, start
from decoy.cli.library._destructive import clean_command, prune_command
from decoy.cli.library._export import export_command
from decoy.cli.library._read import diff_command, list_command, ref_command, show_command
from decoy.ui.theme import error, hint, success, warn

__all__ = ["library_app"]

library_app = typer.Typer(
    name="library",
    help="The project's local record library: where it lives, and whether it is sound.",
    no_args_is_help=True,
)


@library_app.command("path")
def path_command(library: Path | None = library_option()) -> None:
    """Print the library root, where it came from, and whether it runs in degraded mode."""
    cmd = start("library path")
    state = cmd.state
    root = cmd.root(library)
    opened = cmd.library(root.path)
    # A path is printed whole (no wrap at the terminal width) and never read as Rich markup.
    state.console.print("root:", str(root.path), soft_wrap=True, markup=False, highlight=False)
    state.console.print("from:", SOURCE[root.source])
    state.console.print("records:", "on" if root.records else "off (DECOY_LIBRARY=off)")
    if opened.degraded is None:
        state.console.print("mode:", "normal")
    else:
        why = opened.degraded + (f" ({opened.filesystem})" if opened.filesystem else "")
        state.console.print("mode:", warn("degraded"), why)
        state.console.print(
            " ", hint("hint:"), "records are still written; ref updates refuse until it is fixed."
        )
    raise typer.Exit(code=EXIT_OK)


@library_app.command("fsck")
def fsck_command(
    repair: bool = typer.Option(
        False,
        "--repair",
        help=(
            "Quarantine corrupt records, delete stale temp files, remove refs to missing "
            "records and rebuild the index. Never deletes a valid record."
        ),
    ),
    library: Path | None = library_option(),
) -> None:
    """Check every record, ref, link, the index, temp files, modes and job logs.

    Exit 0 when clean, 4 when there are findings (warnings and notes do not count).
    """
    from decoy.cli.library import LibraryError, check_root_budget, fsck_check, fsck_repair

    cmd = start("library fsck")
    state = cmd.state
    root = cmd.root(library)
    caught: LibraryError | None = None
    try:
        check_root_budget(root.path)
        if repair:
            actions, report = fsck_repair(root.path)
        else:
            actions, report = (), fsck_check(root.path)
    except LibraryError as exc:
        caught = exc
    if caught is not None:
        cmd.fail_library(caught)
    state.console.print("library:", str(root.path))
    for action in actions:
        state.console.print(success("repaired"), action.code, action.target)
    for item in report.items:
        label = {"finding": error("finding"), "warning": warn("warning"), "note": hint("note")}
        state.console.print(label[item.level], item.code, item.target)
    count = {
        level: sum(f.level == level for f in report.items)
        for level in ("finding", "warning", "note")
    }
    state.console.print(
        f"{report.objects} records checked: {count['finding']} findings, "
        f"{count['warning']} warnings, {count['note']} notes"
    )
    raise typer.Exit(code=EXIT_OK if report.clean else EXIT_FINDINGS)


library_app.command("list")(list_command)
library_app.command("show")(show_command)
library_app.command("diff")(diff_command)
library_app.command("ref")(ref_command)
library_app.command("prune")(prune_command)
library_app.command("clean")(clean_command)
library_app.command("export")(export_command)
