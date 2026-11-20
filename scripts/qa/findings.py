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

from scripts.qa.io import publish_private_once
from scripts.qa.sweep import RefusalSet, hits, read_needles

SCHEMA_VERSION = 1
STR_FIELDS = (
    "id", "layer", "persona", "group", "platform", "cli_version", "engine_version",
    "bundle_digest", "corpus_item", "command", "config", "expected", "actual", "repro",
    "proposed_tier", "coordinate",
)  # fmt: skip
OPTIONAL = {"coordinate", "triage"}
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


def _check_record(record: Mapping[str, object], tester: str | None) -> None:
    unknown = set(record) - set(STR_FIELDS) - {"exit", "confusing", "schema_version", "triage"}
    if unknown:
        raise Refused("the record has a field the template does not define")
    for name in STR_FIELDS:
        if name in record and type(record[name]) is not str:
            raise Refused(f"{name} must be a string")
        if name not in record and name not in OPTIONAL:
            raise Refused(f"{name} is missing")
    if type(record.get("exit")) is not int or type(record.get("confusing")) is not bool:
        raise Refused("exit must be an integer and confusing a boolean")
    ident = str(record["id"])
    if ID.fullmatch(ident) is None or (tester and not ident.startswith(f"{tester}-")):
        raise Refused("id is not a tester-scoped id")
    for name in ("id", "coordinate"):
        if MARKER_PREFIX in str(record.get(name, "")).lower():
            raise Refused(f"{name} holds marker text")
        if name == "coordinate" and COORDINATE.fullmatch(str(record.get(name) or "n")) is None:
            raise Refused("coordinate is not an opaque id")


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
        if type(value) is str:
            _guard(value, name, needles, refusal)
    for name, blob in artifacts.items():
        if ARTIFACT.fullmatch(name) is None:
            raise Refused("an artifact name is not valid")
        _guard(blob.decode("utf-8", "replace"), f"artifact {name}", needles, refusal)
    target = Path(root) / pass_id / f"{record['id']}.toml"
    publish_private_once(target, _render(record))
    for name, blob in artifacts.items():
        publish_private_once(target.with_name(f"{record['id']}.{name}"), blob)
    return target


def read_record(text: str) -> dict[str, object]:
    """Strict reader: version 1 only, exact primitive types, unknown extra members allowed."""
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        doc = None
    if doc is None:
        raise ReaderError("not valid TOML")
    version = doc.get("schema_version")
    if type(version) is not int:
        raise ReaderError("schema_version is missing or not an integer")
    if version != SCHEMA_VERSION:
        raise ReaderError("unsupported schema_version")
    for name in STR_FIELDS:
        if name in doc and type(doc[name]) is not str:
            raise ReaderError(f"{name} must be a string")
        if name not in doc and name not in OPTIONAL:
            raise ReaderError(f"{name} is missing")
    if type(doc.get("exit")) is not int or type(doc.get("confusing")) is not bool:
        raise ReaderError("exit must be an integer and confusing a boolean")
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
    found = [
        read_record(p.read_text(encoding="utf-8"))
        for p in sorted((Path(root) / pass_id).glob("*.toml"))
    ]
    rows = [
        f"| {r['id']} | {r['group']} | {r['proposed_tier']} | {r.get('triage', 'untriaged')} |"
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
    publish_private_once(target, record_text.encode("utf-8"))
    if notify is not None:
        notify(slack)
    return target


def _slack(text: str) -> None:
    script = os.environ.get("QA_SLACK_SCRIPT")
    if script:
        subprocess.run([script, "manual", text], check=False, timeout=30)


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
    args = ap.parse_args(argv)
    needles = read_needles(args.needles.read_text(encoding="utf-8"))
    refusal = RefusalSet.loads(args.refusal.read_text(encoding="utf-8"))
    try:
        if args.action == "publish":
            publish(args.root, args.pass_id, needles, refusal, notify=_slack)
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
