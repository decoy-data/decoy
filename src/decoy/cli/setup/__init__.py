"""`decoy setup`: write this box's settings (`$DECOY_HOME/settings.json`)."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

import typer

from decoy import _resources as host
from decoy._atomic import AtomicWriteError, describe
from decoy.cli.exit_codes import EXIT_RUNTIME, EXIT_USAGE
from decoy.cli.setup._sections import SECTIONS, STEPS
from decoy.cli.setup._step import SetupAnswers
from decoy.distribution import lock
from decoy.ui.output import OutputMode, emit_error, emit_json, setup_output
from decoy.ui.theme import accent, hint, success

SETTINGS_LOCK = ".settings.lock"
# Only an unreadable or non-JSON/non-object file is replaced; anything else is the user's data.
_UNUSABLE = frozenset({"unreadable", "invalid"})


def _busy() -> Exception:
    return host.ResourceError("settings.json", "busy")


SETUP_EPILOG = """\
Examples:

  decoy setup                 Confirm each value, then write the settings file.

  decoy setup --yes           Write this host's detected values without asking.

  decoy setup --yes --json    Same, with a machine-readable result.

  decoy setup --ner install --yes   Also install spaCy and the NER model.

  decoy setup --ner install --ner-from wheels/ --yes   The same, offline from copied wheels.
"""


class NerAnswer(str, Enum):
    install = "install"
    skip = "skip"


class _Prompter:
    """The two-method prompt shim the steps use (`typer.confirm` behind it)."""

    def __init__(self, state: Any) -> None:
        self._state = state

    def confirm(self, text: str) -> bool:
        return typer.confirm(text, default=False)

    def say(self, text: str) -> None:
        if self._state.mode is OutputMode.default:
            self._state.console.print(text, markup=False)


def _run_steps(state: Any, answers: SetupAnswers) -> dict[str, Any]:
    """Run each step in order; the first failure ends setup with that step's code."""
    from decoy.cli.models import ModelsError, fail

    done: dict[str, Any] = {}
    prompter = _Prompter(state)
    for step in STEPS:
        if state.mode is OutputMode.default and not answers.yes:
            state.console.print(accent(step.title))
        failure: ModelsError | None = None
        try:
            done[step.name] = step.run(prompter, answers)
        except ModelsError as exc:
            failure = exc
        if failure is not None:
            fail(state, "setup", failure)
    return done


def _prompt(label: str, default: str, check: Callable[[str], Any]) -> Any:
    return typer.prompt(label, default=default, value_proc=check)


def _version(existing: dict[str, Any] | None) -> str:
    """Our schema version, unless the file already holds a higher minor of major 1."""
    stored = (existing or {}).get("schema_version", "")
    if stored and int(stored.split(".")[1]) > int(host.SCHEMA_VERSION.split(".")[1]):
        return stored
    return host.SCHEMA_VERSION


def setup_command(
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Accept the detected or stored values; do not prompt."
    ),
    json_: bool = typer.Option(False, "--json", help="Emit a JSON result instead of text."),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress stdout. Errors still go to stderr."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logs on stderr."),
    ner: NerAnswer | None = typer.Option(
        None, "--ner", help="Install spaCy and the NER model, or skip it, without asking."
    ),
    ner_from: Path | None = typer.Option(
        None,
        "--ner-from",
        help="Install NER from this model .whl or directory of .whl files (offline; trusted).",
    ),
) -> None:
    """Set this box's max memory and threads for `decoy run`, and offer the NER model.

    Shows what this host reports, asks you to confirm or change it, and writes
    $DECOY_HOME/settings.json (default ~/.decoy/settings.json). Other sections and keys
    already in the file are kept. A flag or environment variable on a single run still
    wins over the file. The models step then offers `decoy models install ner`; it stores
    nothing, and --yes alone never installs it.
    """
    state = setup_output(json_, quiet, verbose)
    if not yes and not sys.stdin.isatty():
        emit_error(state, "setup", "setup needs a terminal; pass --yes to accept.")
        raise typer.Exit(code=EXIT_USAGE)
    if ner is NerAnswer.skip and ner_from is not None:
        emit_error(state, "setup", "--ner-from needs --ner install, not --ner skip.")
        raise typer.Exit(code=EXIT_USAGE)
    answers = SetupAnswers(yes, None if ner is None else ner.value, ner_from)
    try:
        stored = host.read_settings()
    except host.ResourceError:
        stored = {}
    written: dict[str, Any] = {}
    replaced = False
    try:
        proposals = []
        for section in SECTIONS:
            proposed = section.propose(stored)
            if not yes:
                state.console.print(accent(section.title))
            values = proposed if yes else section.ask(proposed, _prompt)
            written[section.name] = values
            proposals.append((section, values))
        # The file is read again under the lock, so a change made while the user answered
        # the prompts is merged, not lost. The lock serializes decoy processes only; an
        # editor or another tool writing the file is outside its reach.
        with lock.exclusive(host.decoy_home(), SETTINGS_LOCK, _busy):
            try:
                existing = host.load_document()
            except host.ResourceError as exc:
                if exc.code not in _UNUSABLE:
                    raise  # a readable document we do not understand is refused, never replaced
                existing, replaced = None, True
            doc: dict[str, Any] = dict(existing or {})
            doc["schema_version"] = _version(existing)
            for section, values in proposals:
                # Keys this section does not own, and other top-level sections, stay as they were.
                owned = doc.get(section.name)
                rendered = section.render(values)
                doc[section.name] = {**(owned if isinstance(owned, dict) else {}), **rendered}
            path = host.write_settings(json.dumps(doc, indent=2) + "\n")
    except host.ResourceError as exc:
        # `ResourceError` text is the setting key and a fixed reason, never a value.
        emit_error(state, "setup", str(exc), code=f"setup_{exc.code}")
        raise typer.Exit(code=EXIT_USAGE) from None
    except AtomicWriteError as exc:
        emit_error(
            state,
            "setup",
            f"settings not written: {describe(exc)}",
            hint="check the directory is writable.",
        )
        raise typer.Exit(code=EXIT_RUNTIME) from None
    except OSError:
        # Creating the settings lock (or its folder) failed; nothing was written.
        emit_error(
            state,
            "setup",
            "settings not written: the settings lock could not be created",
            hint="check the directory is writable.",
        )
        raise typer.Exit(code=EXIT_RUNTIME) from None
    if state.mode is OutputMode.default:
        if replaced:
            state.console.print(hint("note:"), "the existing settings file was unusable; replaced.")
        state.console.print(success("Wrote"), str(path))
    steps = _run_steps(state, answers)
    if state.mode is OutputMode.json:
        emit_json(
            state,
            {
                "command": "setup",
                "status": "ok",
                "settings_path": str(path),
                "schema_version": doc["schema_version"],
                "sections": written,
                "replaced_unusable_file": replaced,
                **steps,
            },
        )
