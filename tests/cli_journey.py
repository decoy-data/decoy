"""The CLI V1 journey document, read by tests (roadmap row 75).

One place per fact: `docs/qa/cli-v1-journey.md` holds each step's command and exit codes, and this
module is the only reader of it. Tests take exits from here, never from a copy. The allowed exit
set comes from `decoy.cli.exit_codes`, so no integer is copied into a test or into this module.

Pattern: requirement-id markers (jamb, pytest-mark-ac) without a plugin. A test carries a step id
through `journey_step`, and `tests/sentry/release/test_journey_ids.py` checks both directions.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

import pytest

JOURNEY_DOC = Path(__file__).resolve().parents[1] / "docs" / "qa" / "cli-v1-journey.md"

STAGES = (
    "install",
    "project",
    "source",
    "subset",
    "pre-scan",
    "mask",
    "post-scan",
    "delivery",
    "evidence",
    "vault",
    "refusal",
)
# The V1 pipeline baseline stages: a journey that drops one has stopped checking the baseline.
BASELINE_STAGES = ("source", "subset", "pre-scan", "mask", "post-scan", "delivery", "vault")
LABELS = ("Stage", "Command", "Exit", "Expected", "Lands with")

_HEADING = re.compile(r"### (CJ-\d{2}): (\S.*)")
_LABEL_LINE = re.compile(r"\*\*([^*:]+):\*\* ?(.*)")
_EXIT_VALUE = re.compile(r"\d+(?:, \d+)*")
_LANDS_VALUE = re.compile(r"main|row \d+[a-z]?")
_SPAN = re.compile(r"`([^`\n]+)`")
_DECOY_COMMAND = re.compile(r"decoy(?: \S.*)?")
# The installer forms of checklist group 1: optional NAME=value assignments, then the script.
_INSTALLER_COMMAND = re.compile(
    r"(?:[A-Z_][A-Z0-9_]*=\S+ )*(?:sh install\.sh|install\.ps1)(?: \S.*)?"
)


class JourneyDocError(ValueError):
    """The journey document breaks its own format. The text names the line, never a value."""


@dataclass(frozen=True)
class JourneyStep:
    id: str
    title: str
    stage: str
    commands: tuple[str, ...]
    exits: tuple[int, ...]
    expected: str
    lands_with: str

    @property
    def on_main(self) -> bool:
        return self.lands_with == "main"


@dataclass
class _Block:
    id: str
    title: str
    fields: dict[str, str] = field(default_factory=dict)


def parse_commands(text: str, *, installer: bool = False) -> list[str]:
    """The commands in `text`: backtick spans that full-match the command grammar, in order.

    A span is a command only when the whole span is `decoy` with optional arguments (and, with
    `installer`, the `sh install.sh` or `install.ps1` forms). `decoyx run`, flags, file names and
    YAML keys are other spans and are not counted.
    """
    found = []
    for span in _SPAN.findall(text):
        if _DECOY_COMMAND.fullmatch(span) or (installer and _INSTALLER_COMMAND.fullmatch(span)):
            found.append(span)
    return found


def allowed_exit_codes() -> frozenset[int]:
    """Every exit integer the CLI documents: the exported `EXIT_` names and `RUN_EXIT_MAP`."""
    from decoy.cli import exit_codes

    named = {getattr(exit_codes, n) for n in exit_codes.__all__ if n.startswith("EXIT_")}
    return frozenset(named | set(exit_codes.RUN_EXIT_MAP.values()))


def parse_journey(text: str) -> tuple[JourneyStep, ...]:
    """Parse the journey document; refuse an unknown or repeated label, a stray line or a bad value."""
    blocks: list[_Block] = []
    for number, line in enumerate(text.splitlines(), start=1):
        heading = _HEADING.fullmatch(line)
        if heading:
            step_id, title = heading.groups()
            blocks.append(_Block(step_id, title))
            continue
        if line.startswith("### "):
            raise JourneyDocError(f"line {number}: a level-3 heading must be '### CJ-NN: title'")
        if not blocks or not line.strip():
            continue
        label = _LABEL_LINE.fullmatch(line)
        if label is None:
            raise JourneyDocError(f"line {number}: a step holds only labelled lines")
        name, value = label.groups()
        if name not in LABELS:
            raise JourneyDocError(f"line {number}: unknown label {name!r}")
        if name in blocks[-1].fields:
            raise JourneyDocError(f"line {number}: label {name!r} appears twice in {blocks[-1].id}")
        blocks[-1].fields[name] = value.strip()
    return tuple(_step(block.id, block.title, block.fields) for block in blocks)


def _step(step_id: str, title: str, fields: dict[str, str]) -> JourneyStep:
    missing = [name for name in LABELS if not fields.get(name)]
    if missing:
        raise JourneyDocError(f"{step_id}: missing or empty label {missing[0]!r}")
    if fields["Stage"] not in STAGES:
        raise JourneyDocError(f"{step_id}: stage is not one of the known stages")
    if not _EXIT_VALUE.fullmatch(fields["Exit"]):
        raise JourneyDocError(f"{step_id}: Exit must be integers separated by ', '")
    if not _LANDS_VALUE.fullmatch(fields["Lands with"]):
        raise JourneyDocError(f"{step_id}: Lands with must be 'main' or 'row <N>'")
    commands = tuple(parse_commands(fields["Command"]))
    if not commands:
        raise JourneyDocError(f"{step_id}: Command holds no `decoy ...` span")
    return JourneyStep(
        step_id,
        title,
        fields["Stage"],
        commands,
        tuple(int(code) for code in fields["Exit"].split(", ")),
        fields["Expected"],
        fields["Lands with"],
    )


@functools.lru_cache(maxsize=None)
def read_journey(path: Path = JOURNEY_DOC) -> tuple[JourneyStep, ...]:
    return parse_journey(path.read_text(encoding="utf-8"))


def step_by_id(step_id: str) -> JourneyStep:
    for step in read_journey():
        if step.id == step_id:
            return step
    raise KeyError(f"{step_id} is not in the journey document")


F = TypeVar("F", bound=Callable[..., object])


def journey_step(step_id: str) -> Callable[[F], F]:
    """Cite journey step `step_id` on a test. A step that is not on main is a strict xfail.

    Strict xfail fails the run once the behaviour lands, which forces the change that lands it to
    set the step's `Lands with` to `main`.
    """
    step = step_by_id(step_id)

    def mark(test: F) -> F:
        test.__journey_step__ = step_id  # type: ignore[attr-defined]
        if not step.on_main:
            return pytest.mark.xfail(strict=True, reason=f"lands with {step.lands_with}")(test)
        return test

    return mark
