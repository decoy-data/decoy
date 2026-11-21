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
# The CLI has no one printed form for exit 4 or for a blocking warning, so the documented forms are
# listed here, each from a command's real output (`report verify`, `report integrity`,
# `library fsck` and `prune`, `validate`). A bare word such as `changed`, `failed` or `error` is not
# a form: it appears in refusals and crash text too. Lines that start `error:` are refusals and are
# never read as a finding or a warning.
_FINDING_FORMS = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bINTEGRITY CHECK FAILED\b",
        r"\b[1-9]\d*\s+(fail(ed|ures?)?|errors?|findings?|left behind)\b",
        r"\b(fail|error|issue)(_count)?\W{0,3}[:=]\s*[1-9]",
        r"^\W*check \S+:\s*(fail|error)\b",
        r"\bfingerprints?\s+(changed|mismatch(ed)?)\b|\bfingerprint_mismatch\b",
        r'"drift"\s*:\s*true',
    )
)
_WARNING_FORMS = tuple(
    re.compile(p, re.I)
    for p in (
        r"^\W*warn(ing)?\b",
        r'"severity"\s*:\s*"warning"',
        r"\b[1-9]\d*\s+warnings?\b",
        r"^\W*check \S+:\s*warn(ing)?\b",
    )
)
# A report that says there is nothing, or a crash dump that happens to contain the word `fail`.
_NO_FINDINGS = re.compile(r"\b(no|0)\s+findings?\b", re.I)
_USAGE_FORM = re.compile(r"^Usage:", re.M)
FAULT_CELLS = {"readonly", "disk", "quota"}


@dataclass(frozen=True)
class Verdict:
    kind: str  # ok, refusal, crash, warning, findings, runtime, capacity, partial, interrupted, unknown
    finding: bool
    reason: str


def _has_form(text: str, forms: tuple[re.Pattern[str], ...]) -> bool:
    """True when a line that is not an `error:` refusal matches one of the documented forms."""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().lower().startswith("error:")]
    return any(form.search(ln) for ln in lines for form in forms)


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
        both = stdout + "\n" + stderr
        if expect == "usage":  # Click's own usage error also exits 2
            ok = _USAGE_FORM.search(stderr) is not None
            return Verdict("warning", not ok, "" if ok else "no-usage-form")
        if expect != "warnings":
            return Verdict("warning", True, "unexpected-warning")
        ok = _has_form(both, _WARNING_FORMS) and "Traceback (most recent call last)" not in both
        return Verdict("warning", not ok, "" if ok else "no-warning-form")
    if code == EXIT_RUNTIME:
        ok = cell in FAULT_CELLS and atomic_ok
        return Verdict("runtime", not ok, "" if ok else "runtime-outside-fault-cell")
    if code == EXIT_FINDINGS:
        both = stdout + "\n" + stderr
        ok = (
            expect == "findings"
            and _has_form(both, _FINDING_FORMS)
            and _NO_FINDINGS.search(both) is None
            and "Traceback (most recent call last)" not in both
        )
        return Verdict("findings", not ok, "" if ok else "unexpected-findings")
    if code == EXIT_CAPACITY:
        ok = cell == "memory"
        return Verdict("capacity", not ok, "" if ok else "capacity-outside-memory-cell")
    if code == EXIT_PARTIAL:
        return Verdict("partial", True, "reserved-exit")
    if code == INTERRUPTED:
        return Verdict("interrupted", expect != "interrupted", "")
    return Verdict("unknown", True, "unknown-exit")
