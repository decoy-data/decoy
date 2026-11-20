"""Finding records: the tester's one way to submit a finding, and the one publisher (plan 5.6, 5.7).

    python -m scripts.qa.findings write --root DIR --pass ID --needles F --refusal F --record R
    python -m scripts.qa.findings publish --root DIR --pass ID --needles F --refusal F

`write` refuses a record that holds a needle or any scalar from the pass's refusal set, in any
field or attached artifact, and an id that holds marker text. Nothing is written on a refusal. The
record goes through `scripts/qa/io.py`, so the id is create-once: a second writer of the same id
loses, and a killed writer leaves no partial record.

`publish` is the only QA code that writes under `docs/records` or posts to Slack. It sweeps the
pass record and the Slack text first. A hit stops publication.

Every refusal is a `Refused` with a fixed message that names the field and never the value. It is
raised outside any handler, so it has no `__cause__` and no `__context__` that could carry text.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from scripts.qa.io import publish_or_same, publish_private_once
from scripts.qa.sweep import RefusalSet, hits, read_needles

SCHEMA_VERSION = 1
# The one descriptor of a record. The writer and the reader both validate through it, so they
# cannot drift. Policy for members it does not list: the writer refuses them (a tester may not
# invent fields), the reader keeps them (a later minor version may add some).
FIELDS: dict[str, type] = {
    **dict.fromkeys(
        (
            "id", "layer", "persona", "group", "platform", "cli_version", "engine_version",
            "bundle_digest", "corpus_item", "command", "config", "expected", "actual", "repro",
            "proposed_tier", "coordinate",
        ),
        str,
    ),
    "exit": int,
    "confusing": bool,
}  # fmt: skip
OPTIONAL = {"coordinate"}
# The triager's vocabulary. A tester never writes a verdict on their own finding.
TRIAGE = ("confirmed", "not-reproduced", "duplicate", "v1", "v2-log", "docs-only")
ID = re.compile(r"[a-z0-9][a-z0-9-]{2,63}")
COORDINATE = re.compile(r"[a-z0-9][a-z0-9/-]{0,63}")
PASS_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
ARTIFACT = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
MARKER_PREFIX = "qamark"
RECORDS = Path(__file__).resolve().parents[2] / "docs/records"


class Refused(ValueError):
    """A record or text was refused. The message never holds the offending text."""


class ReaderError(ValueError):
    """A stored record is malformed or from another major version."""


def _guard(text: str, where: str, needles: Sequence[bytes], refusal: RefusalSet | None) -> None:
    if hits(text.encode("utf-8"), needles) or (refusal is not None and refusal.found_in(text)):
        raise Refused(f"{where} holds a needle or a scalar from the input")


class _Invalid(ValueError):
    """Internal: the descriptor check failed. Wrapped as `Refused` or `ReaderError`."""


def _validate(doc: Mapping[str, object], *, reading: bool, tester: str | None = None) -> None:
    version = doc.get("schema_version")
    if version is None and not reading:
        pass  # the writer stamps the version itself
    elif type(version) is not int or version != SCHEMA_VERSION:
        raise _Invalid("schema_version must be the integer 1")
    for name, kind in FIELDS.items():
        if name not in doc:
            if name not in OPTIONAL:
                raise _Invalid(f"{name} is missing")
        elif type(doc[name]) is not kind:
            raise _Invalid(f"{name} has the wrong type")
    if not reading and set(doc) - set(FIELDS) - {"schema_version"}:
        raise _Invalid("the record has a field the template does not define")
    ident = str(doc["id"])
    if ID.fullmatch(ident) is None or (tester and not ident.startswith(f"{tester}-")):
        raise _Invalid("id is not a tester-scoped id")
    for name in ("id", "coordinate"):
        if MARKER_PREFIX in str(doc.get(name, "")).lower():
            raise _Invalid(f"{name} holds marker text")
    if "coordinate" in doc and COORDINATE.fullmatch(str(doc["coordinate"])) is None:
        raise _Invalid("coordinate is not an opaque id")


def _check_record(record: Mapping[str, object], tester: str | None) -> None:
    bad = None
    try:
        _validate(record, reading=False, tester=tester)
    except _Invalid as exc:
        bad = str(exc)
    if bad is not None:  # raised outside the handler so no __context__ rides along
        raise Refused(bad)


def _strings(value: object) -> list[str]:
    """Every string inside a value, however deeply nested."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [t for k, v in value.items() for t in _strings(k) + _strings(v)]
    if isinstance(value, list | tuple | set):
        return [t for v in value for t in _strings(v)]
    return []


def _render(record: Mapping[str, object]) -> bytes:
    lines = [f"schema_version = {SCHEMA_VERSION}"]
    for name, value in record.items():
        if name == "schema_version":
            continue
        text = json.dumps(value).replace("\x7f", "\\u007f")
        lines.append(f"{name} = {text}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def write(
    root: Path,
    pass_id: str,
    record: Mapping[str, object],
    needles: Sequence[bytes],
    refusal: RefusalSet | None,
    *,
    tester: str | None = None,
    artifacts: Mapping[str, bytes] | None = None,
) -> Path:
    """Publish `root/<pass>/<id>.toml`, then each artifact as `<id>.<name>`."""
    artifacts = artifacts or {}
    if PASS_ID.fullmatch(pass_id) is None:
        raise Refused("the pass id is not valid")
    _check_record(record, tester)
    for name, value in record.items():
        for text in _strings(value):
            _guard(text, name, needles, refusal)
    for name, blob in artifacts.items():
        if ARTIFACT.fullmatch(name) is None or name.endswith(".toml"):  # a record or verdict name
            raise Refused("an artifact name is not valid")
        # Needles are matched on the raw bytes, so a non-UTF-8 needle is still found.
        _guard(blob.decode("utf-8", "replace"), f"artifact {name}", (), refusal)
        if hits(blob, needles):
            raise Refused(f"artifact {name} holds a needle or a scalar from the input")
    target = Path(root) / pass_id / f"{record['id']}.toml"
    for name, blob in artifacts.items():
        publish_or_same(target.with_name(f"{record['id']}.{name}"), blob)
    # The record goes last: it is the commit marker. A retry after a kill finds identical
    # artifacts already there and finishes; an id that has a record is used for good.
    publish_private_once(target, _render(record))
    return target


def write_triage(root: Path, pass_id: str, finding_id: str, verdict: str) -> Path:
    """The triager's verdict as `<id>.triage.toml`: one fixed word, create-once."""
    if PASS_ID.fullmatch(pass_id) is None or ID.fullmatch(finding_id) is None:
        raise Refused("the pass id or finding id is not valid")
    if verdict not in TRIAGE:
        raise Refused("the verdict is not in the triage vocabulary")
    target = Path(root) / pass_id / f"{finding_id}.triage.toml"
    text = f'schema_version = {SCHEMA_VERSION}\nid = "{finding_id}"\ntriage = "{verdict}"\n'
    publish_private_once(target, text.encode("utf-8"))
    return target


def read_record(text: str) -> dict[str, object]:
    """Strict reader: version 1 only, exact primitive types, unknown extra members allowed."""
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        doc = None
    if doc is None:
        raise ReaderError("not valid TOML")
    bad = None
    try:
        _validate(doc, reading=True)
    except _Invalid as exc:
        bad = str(exc)
    if bad is not None:
        raise ReaderError(bad)
    return doc


def publish(
    root: Path,
    pass_id: str,
    needles: Sequence[bytes],
    refusal: RefusalSet | None,
    *,
    records_dir: Path = RECORDS,
    notify: Callable[[str], None] | None = None,
    today: datetime.date | None = None,
) -> Path:
    """Write the pass record under `docs/records`, then send the Slack text (counts and ids)."""
    if PASS_ID.fullmatch(pass_id) is None:
        raise Refused("the pass id is not valid")
    folder = Path(root) / pass_id
    # Only `<id>.toml` is a record: an artifact or a verdict has a dot in its stem.
    found = [
        read_record(p.read_text(encoding="utf-8"))
        for p in sorted(folder.glob("*.toml"))
        if ID.fullmatch(p.stem)
    ]
    verdicts = {}
    for p in sorted(folder.glob("*.triage.toml")):
        doc = tomllib.loads(p.read_text(encoding="utf-8"))
        if doc.get("triage") in TRIAGE and doc.get("id") == p.name.removesuffix(".triage.toml"):
            verdicts[doc["id"]] = doc["triage"]
    rows = [
        f"| {r['id']} | {r['group']} | {r['proposed_tier']} | {verdicts.get(str(r['id']), 'untriaged')} |"
        for r in found
    ]
    body = [f"# QA-BETA pass {pass_id}", "", f"Findings: {len(found)}", ""]
    if rows:
        body += ["| Id | Group | Proposed tier | Triage |", "|---|---|---|---|", *rows]
    record_text = "\n".join(body) + "\n"
    slack = f"QA-BETA pass {pass_id}: {len(found)} findings. Ids: " + ", ".join(
        str(r["id"]) for r in found
    )
    _guard(record_text, "the pass record", needles, refusal)
    _guard(slack, "the Slack text", needles, refusal)
    day = (today or datetime.date.today()).isoformat()
    target = Path(records_dir) / f"{day}-qa-beta-{pass_id}.md"
    publish_or_same(target, record_text.encode("utf-8"))  # a rerun finds it done
    if notify is not None:
        notify(slack)
    return target


def _slack(text: str) -> str:
    """Post and say what happened: `posted`, `skipped (...)` or `failed`."""
    script = os.environ.get("QA_SLACK_SCRIPT")
    if not script:
        return "skipped (QA_SLACK_SCRIPT is not set)"
    try:
        done = subprocess.run([script, "manual", text], check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return "failed"
    return "posted" if done.returncode == 0 else "failed"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("action", choices=("write", "publish"))
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--pass", dest="pass_id", required=True)
    ap.add_argument("--needles", type=Path, required=True)
    ap.add_argument("--refusal", type=Path, required=True)
    ap.add_argument("--record", type=Path)
    ap.add_argument("--tester")
    ap.add_argument("--artifact", action="append", default=[], metavar="NAME=PATH")
    ap.add_argument("--records-dir", type=Path, default=RECORDS)
    ap.add_argument("--no-slack", action="store_true", help="publish without posting to Slack")
    args = ap.parse_args(argv)
    needles = read_needles(args.needles.read_text(encoding="utf-8"))
    refusal = RefusalSet.loads(args.refusal.read_text(encoding="utf-8"))
    try:
        if args.action == "publish":
            # Fail closed: a pass nobody was told about is a pass that did not happen.
            if not args.no_slack and not os.environ.get("QA_SLACK_SCRIPT"):
                sys.stderr.write("refused: QA_SLACK_SCRIPT is not set (use --no-slack)\n")
                return 1
            status: list[str] = []
            notify = None if args.no_slack else lambda t: status.append(_slack(t))
            publish(
                args.root,
                args.pass_id,
                needles,
                refusal,
                records_dir=args.records_dir,
                notify=notify,
            )
            sys.stdout.write(f"slack: {'not sent' if args.no_slack else status[0]}\n")
            if not args.no_slack and status[0] != "posted":
                return 1
        else:
            record = read_record(args.record.read_text(encoding="utf-8"))
            files = dict(a.split("=", 1) for a in args.artifact)
            arts = {n: Path(p).read_bytes() for n, p in files.items()}
            write(
                args.root,
                args.pass_id,
                record,
                needles,
                refusal,
                tester=args.tester,
                artifacts=arts,
            )
    except (Refused, ReaderError, FileExistsError) as exc:
        sys.stderr.write(f"refused: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
