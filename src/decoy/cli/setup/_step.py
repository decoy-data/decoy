"""The shape of a `decoy setup` step: a section that acts instead of storing a value.

A settings section (`_sections.Section`) owns one object of settings.json. A step owns none: it
reports `status()` and does its work in `run(prompter, answers)`. Steps run after the settings
are written, in `STEPS` order.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class SetupAnswers:
    """What the flags already answered. `ner` is "install", "skip", or None when not given."""

    yes: bool
    ner: str | None = None
    ner_from: Path | None = None


class Prompter(Protocol):
    def confirm(self, text: str) -> bool:
        """Ask a yes/no question; the default is no."""

    def say(self, text: str) -> None:
        """One line of progress for a person; silent under --json and --quiet."""


class Step(Protocol):
    name: str
    title: str

    def status(self) -> Any:
        """What this step would report before it runs."""

    def run(self, prompter: Prompter, answers: SetupAnswers) -> dict[str, Any]:
        """Do the step; return its JSON object. Raises the step's own error on failure."""
