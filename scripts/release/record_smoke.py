"""Append one canonical-smoke row to `docs/release/smoke-log.md` (REL-GATE design note 6).

    python scripts/release/record_smoke.py summary.json --candidate dist/candidate.json \\
        --run https://github.com/decoy-data/decoy/actions/runs/123 --note "first 1.0.0 candidate"

The summary is what `packaging_tools/smoke_install.py --from-dist` printed. A row is written only
when the summary is green, its schema major is known, every field has its exact type, and it
names the same CLI version, engine and `SHA256SUMS` digest as `candidate.json`. The log is
append-only: the file must still start with its committed text at `--base-ref`, and anything
after that may only be canonical rows, so a row is never rewritten.

Exit 0 appended, 1 refused (the code is the first word on stderr), 2 usage.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packaging_tools.candidate import (  # noqa: E402
    GATED_TARGETS,
    SMOKE_STEPS,
    SUMMARY_SCHEMA,
    read_candidate,
    strict_json,
)

from decoy.distribution.targets import SUPPORTED_TARGETS  # noqa: E402

LOG = ROOT / "docs" / "release" / "smoke-log.md"
CANONICAL_HEADING = "## Release candidate smoke"
ROW_CELLS = 7
_SCHEMA = re.compile(r"decoy-release-smoke/v(\d+)")
_SUMMARY_KEYS = {
    "schema",
    "platform",
    "cli_version",
    "engine_version",
    "sha256sums_sha256",
    "steps",
    "seconds",
}
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_URL = re.compile(r"https://[A-Za-z0-9.-]+(?:/[A-Za-z0-9._~%/-]*)?")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# The log is public and a summary is untrusted input: a platform cell is a supported,
# ungated target tag, never a host or user name.
PLATFORMS = frozenset(SUPPORTED_TARGETS) - frozenset(GATED_TARGETS)


class Refused(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def check_summary(summary: Any) -> dict[str, Any]:
    """The summary when its schema major is 1 and every field has its exact type."""
    schema = summary.get("schema") if isinstance(summary, dict) else None
    match = _SCHEMA.fullmatch(schema) if type(schema) is str else None
    if match is None or f"decoy-release-smoke/v{match.group(1)}" != SUMMARY_SCHEMA:
        raise Refused("smoke_schema_unknown")
    if set(summary) != _SUMMARY_KEYS:
        raise Refused("smoke_field_type", "fields")
    for key in ("platform", "cli_version", "engine_version", "sha256sums_sha256"):
        if type(summary[key]) is not str:
            raise Refused("smoke_field_type", key)
    seconds = summary["seconds"]
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
        raise Refused("smoke_field_type", "seconds")
    steps = summary["steps"]
    if type(steps) is not dict or any(v not in ("pass", "fail") for v in steps.values()):
        raise Refused("smoke_field_type", "steps")
    if summary["platform"] not in PLATFORMS:
        raise Refused("smoke_field_type", "platform")
    return summary


def check_green(summary: dict[str, Any]) -> None:
    # Every step by name, not by order: the smoke prints its summary with sorted keys.
    steps = summary["steps"]
    if set(steps) != set(SMOKE_STEPS) or any(v != "pass" for v in steps.values()):
        raise Refused("smoke_not_green")


def check_match(summary: dict[str, Any], record: dict[str, str]) -> None:
    if (
        summary["cli_version"] != record["cli_version"]
        or summary["sha256sums_sha256"] != record["sha256sums_sha256"]
        or f"v{summary['engine_version']}" != record["engine_tag"]
    ):
        raise Refused("smoke_candidate_mismatch")


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_row(line: str) -> bool:
    return line.startswith("| ") and line.endswith(" |") and len(_cells(line)) == ROW_CELLS


def check_log(current: str, committed: str) -> None:
    """Refuse unless ``current`` is ``committed`` plus canonical rows, with that table last."""
    if not current.startswith(committed) or not committed.endswith("\n"):
        raise Refused("smoke_log_edited", "committed text changed")
    if committed.count(CANONICAL_HEADING) != 1:
        raise Refused("smoke_log_edited", "canonical table missing")
    table = committed.split(CANONICAL_HEADING, 1)[1].splitlines()
    separator = next((i for i, line in enumerate(table) if line.startswith("|---")), None)
    if separator is None or not all(_is_row(line) for line in table[separator + 1 :] if line):
        raise Refused("smoke_log_edited", "canonical table is not the last section")
    if not all(_is_row(line) for line in current[len(committed) :].splitlines()):
        raise Refused("smoke_log_edited", "uncommitted lines are not rows")


def committed_text(log: Path, base_ref: str) -> str:
    shown = subprocess.run(
        ["git", "-C", str(log.parent), "show", f"{base_ref}:./{log.name}"],
        capture_output=True,
        text=True,
    )
    if shown.returncode != 0:
        raise Refused("smoke_log_edited", f"{log.name} is not committed at {base_ref}")
    return shown.stdout


def row(summary: dict[str, Any], record: dict[str, str], *, date: str, run: str, note: str) -> str:
    cells = [
        date,
        record["cli_sha"],
        record["engine_tag"],
        summary["platform"],
        record["sha256sums_sha256"][:16],
        run,
        note or "-",
    ]
    return "| " + " | ".join(cells) + " |\n"


def _usage(args: argparse.Namespace) -> str | None:
    if not (_URL.fullmatch(args.run) or _LABEL.fullmatch(args.run)):
        return "--run must be an https URL or a host label"
    # splitlines() covers every line boundary a Markdown row can be split on.
    if "|" in args.note or args.note.splitlines() not in ([], [args.note]) or len(args.note) > 200:
        return "--note must be one line of at most 200 characters with no '|'"
    if args.date is not None and not _DATE.fullmatch(args.date):
        return "--date must be YYYY-MM-DD"
    # Empty would make `git show` read the index, so a staged edit would pass as committed.
    if not args.base_ref or args.base_ref.startswith("-"):
        return "--base-ref must be a commit, not an option or empty"
    return None


def record(args: argparse.Namespace) -> str:
    try:
        summary = strict_json(Path(args.summary).read_bytes())
    except (OSError, ValueError):
        raise Refused("smoke_field_type", "summary is not strict JSON")
    summary = check_summary(summary)
    check_green(summary)
    try:
        candidate = read_candidate(Path(args.candidate))
    except (OSError, ValueError):
        raise Refused("smoke_candidate_mismatch", "candidate.json is not a valid record")
    check_match(summary, candidate)
    log = Path(args.log)
    current = log.read_text(encoding="utf-8")
    check_log(current, committed_text(log, args.base_ref))
    date = args.date or _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%d")
    line = row(summary, candidate, date=date, run=args.run, note=args.note)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return line


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="record_smoke", description=__doc__.splitlines()[0])
    ap.add_argument("summary", help="the smoke summary JSON")
    ap.add_argument("--candidate", required=True, help="candidate.json of the smoked set")
    ap.add_argument("--run", required=True, help="the CI run URL or a host label")
    ap.add_argument("--note", default="", help="one line, no '|'")
    ap.add_argument("--log", default=str(LOG), help="the smoke log")
    ap.add_argument("--base-ref", default="HEAD", help="the commit holding the committed log")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today, UTC)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    problem = _usage(args)
    if problem:
        print(f"record_smoke: usage: {problem}", file=sys.stderr)
        return 2
    try:
        line = record(args)
    except Refused as refusal:
        detail = f" ({refusal.detail})" if refusal.detail else ""
        print(f"{refusal.code}{detail}", file=sys.stderr)
        return 1
    print(f"record_smoke: appended {line.strip()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
