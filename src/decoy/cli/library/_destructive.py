"""`decoy library prune` and `decoy library clean` (plan 4.7, 4.15; L4b).

The destructive-operation rule: resolve the exact targets read-only first and print them; delete
only with `--yes`. `prune` touches record objects (and their index rows) only; `clean` touches
`.decoy/scratch/` only. Neither ever reaches a vault file, key, target, `out/` run folder or
anything outside the library root. A file that cannot be removed (held open on Windows) is listed
as left behind and the command exits 4 (`EXIT_FINDINGS`).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import typer

from decoy.cli.exit_codes import EXIT_FINDINGS, EXIT_OK
from decoy.cli.library._cli import LibraryCommand, library_option, start
from decoy.ui.output import OutputMode, OutputState

__all__ = ["clean_command", "prune_command"]

_DURATION = re.compile(r"([0-9]{1,6})([dhm])")
_UNIT = {"d": "days", "h": "hours", "m": "minutes"}


def _say(state: OutputState, *parts: object) -> None:
    if state.mode is OutputMode.default:
        state.console.print(*parts, soft_wrap=True, markup=False, highlight=False)


def _duration(cmd: LibraryCommand, text: str) -> timedelta:
    found = _DURATION.fullmatch(text)
    if found is None:
        cmd.fail("--older-than takes a number and d, h or m, for example 90d")
    return timedelta(**{_UNIT[found.group(2)]: int(found.group(1))})


def prune_command(
    kind: str | None = typer.Option(None, "--kind", metavar="K", help="Only records of this kind."),
    keep_last: int | None = typer.Option(
        None, "--keep-last", metavar="N", help="Keep the newest N records of each kind."
    ),
    older_than: str | None = typer.Option(
        None, "--older-than", metavar="D", help="Only records older than D (90d, 12h, 30m)."
    ),
    yes: bool = typer.Option(
        False, "--yes", help="Delete. Without it, prune only shows what it would delete."
    ),
    library: Path | None = library_option(),
) -> None:
    """Delete records you no longer keep. Never one a ref or a kept record links to, one younger
    than an hour, or one of a kind this Decoy does not know. With no options, applies the
    `keep_last` rules in `.decoy/library.yaml`."""
    from decoy.cli.library import LibraryError, PruneRule, policy_rules, prune_apply, prune_preview

    cmd = start("library prune")
    state = cmd.state
    if keep_last is not None and keep_last < 0:
        cmd.fail("--keep-last takes 0 or more")
    age = None if older_than is None else _duration(cmd, older_than)
    root = cmd.root(library)
    opened = cmd.library(root.path)
    caught: LibraryError | None = None
    present = False
    try:
        present = opened.present
    except LibraryError as exc:
        caught = exc
    if caught is not None:
        cmd.fail_library(caught)
    if not present:
        _say(state, "no library at", str(root.path))
        raise typer.Exit(code=EXIT_OK)
    rules: list = []
    try:
        if kind is None and keep_last is None and age is None:
            rules = policy_rules(root.path)
        else:
            rules = [PruneRule(kind=kind, keep_last=keep_last, older_than=age)]
    except LibraryError as exc:
        caught = exc
    if caught is not None:
        cmd.fail_library(caught)
    if not rules:
        _say(state, "nothing to prune: the policy keeps every record")
        raise typer.Exit(code=EXIT_OK)
    now = datetime.now(timezone.utc)
    try:
        if not yes:
            plan = prune_preview(opened, rules, now=now)
        else:
            report = prune_apply(opened, rules, now=now)
    except LibraryError as exc:
        caught = exc
    if caught is not None:
        cmd.fail_library(caught)
    if not yes:
        for rid in plan.delete:
            _say(state, "would delete", rid)
        _say(
            state,
            f"{len(plan.delete)} to delete, {len(plan.protected)} kept by a ref or a link, "
            f"{len(plan.young)} younger than an hour; rerun with --yes to delete",
        )
        if plan.unexplained:
            _say(
                state,
                f"{plan.unexplained} entries prune cannot account for; --yes refuses until "
                "`decoy library fsck` explains or repairs them",
            )
        raise typer.Exit(code=EXIT_OK)
    for rid in report.deleted:
        _say(state, "deleted", rid)
    for rid in report.left:
        _say(state, "left behind", rid)
    _say(state, f"{len(report.deleted)} deleted, {len(report.left)} left behind")
    raise typer.Exit(code=EXIT_FINDINGS if report.left else EXIT_OK)


def clean_command(
    yes: bool = typer.Option(
        False, "--yes", help="Delete. Without it, clean only shows what it would delete."
    ),
    library: Path | None = library_option(),
) -> None:
    """Delete everything in `.decoy/scratch/` (sample output and staging). Records, logs and
    anything outside the library are never touched."""
    from decoy.cli.library import LibraryError, clean_all, clean_preview

    cmd = start("library clean")
    state = cmd.state
    root = cmd.root(library)
    opened = cmd.library(root.path)
    caught: LibraryError | None = None
    entries: list = []
    try:
        entries = clean_preview(opened)
    except LibraryError as exc:
        caught = exc
    if caught is not None:
        cmd.fail_library(caught)
    if not entries:
        _say(state, "scratch is empty")
        raise typer.Exit(code=EXIT_OK)
    if not yes:
        for entry in entries:
            _say(state, "would delete", f"scratch/{entry.name}")
        _say(state, f"{len(entries)} to delete; rerun with --yes to delete")
        raise typer.Exit(code=EXIT_OK)
    results: list = []
    try:
        results = clean_all(opened)
    except LibraryError as exc:
        caught = exc
    if caught is not None:
        cmd.fail_library(caught)
    left = 0
    for name, report in results:
        _say(state, "deleted", f"scratch/{name}", f"({report.removed} files)")
        for skipped in report.skipped:
            left += 1
            _say(state, "left behind", f"scratch/{name}/{skipped}")
    raise typer.Exit(code=EXIT_FINDINGS if left else EXIT_OK)
