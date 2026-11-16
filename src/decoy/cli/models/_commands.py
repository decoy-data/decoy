"""`decoy models list` and `decoy models install ner`: flags, prompts and output only.

The engine is imported inside the commands, never at module import, so `decoy --help` and
`decoy ci` (which silences the engine's logger before its first import) stay engine-free.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from decoy.cli.models._errors import DP_NOTE, ModelsError
from decoy.ui.output import OutputMode, OutputState, emit_error, emit_json, setup_output
from decoy.ui.theme import accent, hint, success

if TYPE_CHECKING:
    from decoy.cli.models._install import InstallPlan, InstallResult

LIST_EPILOG = """\
Examples:

  decoy models list           One line per model: available, version, or why not.

  decoy models list --json    The same rows as JSON.

  decoy models list --model en_core_web_md   Check another installed spaCy model.
"""

INSTALL_EPILOG = """\
Examples:

  decoy models install ner                       spaCy and the pinned en_core_web_sm wheel.

  decoy models install ner --from wheels/ --yes  Offline, from a directory of wheels.

  decoy models install ner --from en_core_web_sm-3.8.0-py3-none-any.whl
                                                 Only the model; spaCy must already be installed.
"""


class ModelKind(str, Enum):
    ner = "ner"


def list_command(
    model: str | None = typer.Option(
        None, "--model", help="The spaCy model package to check [default: en_core_web_sm]."
    ),
    json_: bool = typer.Option(False, "--json", help="Emit a JSON result instead of text."),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress stdout. Errors still go to stderr."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logs on stderr."),
) -> None:
    """Show each detector model: available here, its version, or the reason and the fix."""
    from decoy_engine.detection.ner import DEFAULT_NER_MODEL

    from decoy.cli.models._install import model_name_error
    from decoy.cli.models._status import describe, model_rows

    state = setup_output(json_, quiet, verbose)
    bad_name = model_name_error(model or DEFAULT_NER_MODEL)
    if bad_name is not None:
        fail(state, "models list", bad_name)
    rows = model_rows(model or DEFAULT_NER_MODEL)
    if state.mode is OutputMode.json:
        emit_json(
            state, {"command": "models list", "status": "ok", "models": rows, "note": DP_NOTE}
        )
        return
    if state.mode is OutputMode.quiet:
        return
    for r in rows:
        state.console.print(describe(r), markup=False)
        if r["hint"]:
            state.console.print(" ", hint("hint:"), r["hint"], markup=False)
    state.console.print(hint("note:"), DP_NOTE, markup=False)


def plan_lines(plan: InstallPlan) -> list[str]:
    """What an install will do, printed before it asks. Names and paths only, no index URL."""
    where = (
        "the wheels passed with --from. --from content is trusted: a wheel can ship a .pth file "
        "that runs at every interpreter start"
        if plan.offline
        else "the package index, with the model wheel pinned by SHA-256"
    )
    return [
        f"Install for NER: {', '.join(plan.packages)} (model {plan.model} {plan.version})",
        f"  from: {where}",
        f"  into: {plan.interpreter} ({plan.installer})",
        f"  note: {DP_NOTE}",
    ]


def confirmer(state: OutputState, yes: bool) -> Any:
    """Print the plan in text mode; ask unless `--yes`."""

    def confirm(plan: InstallPlan) -> bool:
        if state.mode is OutputMode.default:
            for line in plan_lines(plan):
                state.console.print(line, markup=False)
        return yes or typer.confirm("Install these packages?", default=False)

    return confirm


def progress(state: OutputState) -> Any:
    def say(text: str) -> None:
        if state.mode is OutputMode.default:
            state.console.print(accent(text), markup=False)

    return say


def result_doc(result: InstallResult) -> dict[str, Any]:
    from decoy.cli.models._status import dp_certified

    return {
        "model": {"id": result.model, "version": result.version},
        "installed": list(result.installed),
        "installer": result.installer,
        "already_installed": result.already_installed,
        "dp_certified_environment": dp_certified()[0],
    }


def fail(state: OutputState, command: str, err: ModelsError) -> None:
    emit_error(state, command, err.message, code=err.code, hint=err.hint, context=err.context)
    raise typer.Exit(code=err.exit_code)


def interactive(state: OutputState) -> bool:
    return state.mode is not OutputMode.json and sys.stdin.isatty()


def install_command(
    kind: ModelKind = typer.Argument(..., help="What to install: ner (spaCy and a model)."),
    model: str | None = typer.Option(
        None, "--model", help="The spaCy model package [default: en_core_web_sm]."
    ),
    from_: Path | None = typer.Option(
        None,
        "--from",
        help="A model .whl, or a directory of .whl files (offline; trusted input).",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Install without asking."),
    json_: bool = typer.Option(False, "--json", help="Emit a JSON result instead of text."),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress stdout. Errors still go to stderr."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logs on stderr."),
) -> None:
    """Install spaCy and an NER model into this Python environment.

    Online it installs the model wheel pinned by SHA-256; --from installs from wheels you copied,
    with no network. Installed packages never change version. NER takes this environment off a
    certified DP row.
    """
    from decoy_engine.detection.ner import DEFAULT_NER_MODEL

    from decoy.cli.models._install import install_ner

    state = setup_output(json_, quiet, verbose)
    if not yes and not interactive(state):
        emit_error(state, "models install", "models install needs a terminal to ask; pass --yes.")
        raise typer.Exit(code=1)
    failure: ModelsError | None = None
    try:
        result = install_ner(
            model=model or DEFAULT_NER_MODEL,
            source=from_,
            confirm=confirmer(state, yes),
            progress=progress(state),
        )
    except ModelsError as exc:
        failure = exc
    if failure is not None:
        fail(state, "models install", failure)
    doc = result_doc(result)
    if state.mode is OutputMode.json:
        emit_json(state, {"command": "models install", "status": "ok", **doc})
    elif state.mode is OutputMode.default:
        what = "already installed" if result.already_installed else "installed"
        state.console.print(
            success(f"{result.model} {result.version} {what}"),
            f"(spaCy {result.runtime_version}).",
            markup=False,
        )
        if not doc["dp_certified_environment"]:
            state.console.print(hint("note:"), DP_NOTE, markup=False)
