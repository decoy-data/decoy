"""I6: the exit code means what the registry says (plan 15.2.1).

Reads the live registry (`decoy.cli.exit_codes`, public names), so a change there shows up in the
tests instead of as drift. `classify` returns a `Verdict`. Its `reason` is a fixed word, never a
piece of the command's output.

`expect` is what the docs say should happen: success, refusal, warnings, usage, findings or
interrupted. `cell` names an injected fault (readonly, disk, quota, memory) for the exits that
pass only there. `atomic_ok` says the cell's atomicity checks found no partial output.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from decoy.cli.exit_codes import (
    EXIT_CAPACITY,
    EXIT_FINDINGS,
    EXIT_OK,
    EXIT_PARTIAL,
    EXIT_RUNTIME,
    EXIT_USAGE,
    EXIT_WARNINGS,
)

INTERRUPTED = 130
# The product's crash form, with and without `--verbose` (src/decoy/__main__.py:154 and :187).
_CRASH = re.compile(r"error: internal error \(\w+\)")
_REFUSAL = re.compile(r"error: \S")
FAULT_CELLS = {"readonly", "disk", "quota"}


@dataclass(frozen=True)
class Verdict:
    kind: str  # ok, refusal, crash, warning, findings, runtime, capacity, partial, interrupted, unknown
    finding: bool
    reason: str


def _is_crash(stderr: str) -> bool:
    return (
        _CRASH.search(stderr) is not None
        or "Traceback (most recent call last)" in stderr
        or _REFUSAL.search(stderr) is None  # a failure with no reason is not a refusal
    )


def classify(
    code: int,
    stdout: str,
    stderr: str,
    *,
    expect: str = "success",
    cell: str | None = None,
    atomic_ok: bool = False,
    json_text: str | None = None,
    validate: Callable[[object], bool] | None = None,
) -> Verdict:
    """`validate` checks a parsed `--json` document against its schema, when the caller has one."""
    if json_text is not None:
        try:
            doc = json.loads(json_text)
        except ValueError:
            return Verdict("unknown", True, "invalid-json")
        if validate is not None and not validate(doc):
            return Verdict("unknown", True, "schema-mismatch")
    if code == EXIT_OK:
        return Verdict(
            "ok", expect != "success", "unexpected-success" if expect != "success" else ""
        )
    if code == EXIT_USAGE:
        if _is_crash(stderr):
            return Verdict("crash", True, "crash")
        return Verdict(
            "refusal", expect != "refusal", "" if expect == "refusal" else "unexpected-refusal"
        )
    if code == EXIT_WARNINGS:
        return Verdict("warning", expect not in {"warnings", "usage"}, "")
    if code == EXIT_RUNTIME:
        ok = cell in FAULT_CELLS and atomic_ok
        return Verdict("runtime", not ok, "" if ok else "runtime-outside-fault-cell")
    if code == EXIT_FINDINGS:
        ok = expect == "findings" and bool(stdout.strip() or stderr.strip())
        return Verdict("findings", not ok, "" if ok else "unexpected-findings")
    if code == EXIT_CAPACITY:
        ok = cell == "memory"
        return Verdict("capacity", not ok, "" if ok else "capacity-outside-memory-cell")
    if code == EXIT_PARTIAL:
        return Verdict("partial", True, "reserved-exit")
    if code == INTERRUPTED:
        return Verdict("interrupted", expect != "interrupted", "")
    return Verdict("unknown", True, "unknown-exit")
