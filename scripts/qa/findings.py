"""Finding records: the tester's one way to submit a finding, and the one publisher (plan 5.6, 5.7).

    python -m scripts.qa.findings write --root DIR --pass ID --needles F --refusal F --record R
    python -m scripts.qa.findings publish --root DIR --pass ID --needles F --refusal F

`write` refuses a record that holds a needle or any scalar from the pass's refusal set, in any
field or attached artifact, and an id that holds marker text. `--tester` is required: an id must
start with its tester's name, so two testers cannot collide. Nothing is written on a refusal. A
bundle (the artifacts and the record) is published under one exclusive per-id claim
(`io.exclusive_claim`), artifacts first and the record last as the commit marker. Two writers of
one id take turns: the second finds the record and loses. A killed writer's leftover artifacts
are finished by a retry with the same artifact names; a retry that names others is refused, so a
record is never published beside another writer's files.

`publish` is the only QA code that writes under `docs/records` or posts to Slack. It sweeps the
pass record and the Slack text first. A hit stops publication. It also refuses a pass whose
findings are not all triaged, and a triage record with no finding, so it can be run again after
triage and a pass record never commits an `untriaged` row.

Every refusal is a `Refused` with a fixed message that names the field and never the value. It is
raised outside any handler, so it has no `__cause__` and no `__context__` that could carry text.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from scripts.qa.corpus.manifest import load_manifest
from scripts.qa.io import AlreadyPublished, exclusive_claim, publish_or_same, publish_private_once
from scripts.qa.sweep import (
    NothingRead,
    RefusalSet,
    RefusalSetError,
    hits,
    read_needles,
    require_input,
)

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


def _corpus_ids() -> frozenset[str]:
    """The closed vocabulary of `corpus_item`: the ids in the corpus manifest."""
    return frozenset(item.id for item in load_manifest(MANIFEST))


def _pattern(text: str) -> Callable[[str], bool]:
    compiled = re.compile(text)
    return lambda value: compiled.fullmatch(value) is not None


# Harness-filled structural fields: typed metadata like the plan's metric fields. Each has a strict
# grammar (an anchored pattern or a closed vocabulary), is refused when it does not fit, and then
# skips the refusal-set lookup, because a version such as `1.0.0` would otherwise collide with a
# corpus value `0`. The needles scan still runs on every one. Free text (`command`, `config`,
# `expected`, `actual`, `repro`, `coordinate`) keeps the full lookup.
STRUCTURAL: dict[str, Callable[[str], bool]] = {
    "id": _pattern(r"[a-z0-9][a-z0-9-]{2,63}"),
    "layer": _pattern(r"L[1-4]"),
    "persona": _pattern(r"|P[1-9][0-9]?"),
    "group": _pattern(r"[A-Z][A-Z0-9-]{0,15}"),
    "platform": _pattern(r"[a-z0-9][a-z0-9_.-]{0,31}"),
    "cli_version": _pattern(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+.][0-9A-Za-z.-]{1,31})?"),
    "engine_version": _pattern(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+.][0-9A-Za-z.-]{1,31})?"),
    "bundle_digest": _pattern(r"sha256:[0-9a-f]{2,64}"),
    "proposed_tier": lambda value: value in {"V1", "V2-LOG"},
    "corpus_item": lambda value: value in _corpus_ids(),
}
# The triager's vocabulary. A tester never writes a verdict on their own finding.
TRIAGE = ("confirmed", "not-reproduced", "duplicate", "v1", "v2-log", "docs-only")
# The verdict file's descriptor. A verdict is written and read through it, as a record is.
VERDICT_FIELDS: dict[str, type] = {"id": str, "triage": str}
ID = re.compile(r"[a-z0-9][a-z0-9-]{2,63}")
COORDINATE = re.compile(r"[a-z0-9][a-z0-9/-]{0,63}")
PASS_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
ARTIFACT = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
MARKER_PREFIX = "qamark"
RECORDS = Path(__file__).resolve().parents[2] / "docs/records"
MANIFEST = Path(__file__).resolve().parents[2] / "docs/qa/corpus/manifest.toml"


class Refused(ValueError):
    """A record or text was refused. The message never holds the offending text."""


class ReaderError(ValueError):
    """A stored record is malformed or from another major version."""


def _decodings(blob: bytes) -> list[str]:
    """The ways a byte string can read as text.

    UTF-8, plus Latin-1 when it is not valid UTF-8, plus UTF-32 or UTF-16 when a BOM says so (and
    UTF-16 either way round when it holds NULs).
    """
    try:
        texts = [blob.decode("utf-8")]
    except UnicodeDecodeError:
        texts = [blob.decode("utf-8", "replace"), blob.decode("latin-1")]
    if blob[:4] in (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"):
        texts.append(blob.decode("utf-32", "replace"))
    elif blob[:2] in (b"\xff\xfe", b"\xfe\xff"):
        texts.append(blob.decode("utf-16", "replace"))
    elif b"\x00" in blob:
        texts += [blob.decode("utf-16-le", "replace"), blob.decode("utf-16-be", "replace")]
    return texts


def _guard(text: str, where: str, needles: Sequence[bytes], refusal: RefusalSet | None) -> None:
    if _unencodable(text):
        raise Refused(f"{where} is not valid text")
    if hits(text.encode("utf-8"), needles) or (refusal is not None and refusal.found_in(text)):
        raise Refused(f"{where} holds a needle or a scalar from the input")


def _unencodable(text: str) -> bool:
    """True for text that cannot be stored as UTF-8 (a lone surrogate)."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return False


class _Invalid(ValueError):
    """Internal: the descriptor check failed. Wrapped as `Refused` or `ReaderError`."""


@dataclass(frozen=True)
class Schema:
    """One descriptor for a stored file: the writer and the reader both check through it."""

    fields: Mapping[str, type]
    optional: frozenset[str] = frozenset()

    def check(self, doc: Mapping[str, object], *, reading: bool) -> None:
        version = doc.get("schema_version")
        if version is None and not reading:
            pass  # the writer stamps the version itself
        elif type(version) is not int or version != SCHEMA_VERSION:
            raise _Invalid("schema_version must be the integer 1")
        for name, kind in self.fields.items():
            if name not in doc:
                if name not in self.optional:
                    raise _Invalid(f"{name} is missing")
            elif type(doc[name]) is not kind:
                raise _Invalid(f"{name} has the wrong type")
        if not reading and set(doc) - set(self.fields) - {"schema_version"}:
            raise _Invalid("the record has a field the template does not define")


RECORD = Schema(FIELDS, frozenset(OPTIONAL))
VERDICT = Schema(VERDICT_FIELDS)


def _validate(doc: Mapping[str, object], *, reading: bool, tester: str | None = None) -> None:
    RECORD.check(doc, reading=reading)
    for name, fits in STRUCTURAL.items():
        if name in doc and not fits(str(doc[name])):
            raise _Invalid(f"{name} does not fit its grammar")
    ident = str(doc["id"])
    if ID.fullmatch(ident) is None or (tester is not None and not ident.startswith(f"{tester}-")):
        raise _Invalid("id is not a tester-scoped id")
    for name in ("id", "coordinate"):
        if MARKER_PREFIX in str(doc.get(name, "")).lower():
            raise _Invalid(f"{name} holds marker text")
    if "coordinate" in doc and COORDINATE.fullmatch(str(doc["coordinate"])) is None:
        raise _Invalid("coordinate is not an opaque id")


def _validate_verdict(doc: Mapping[str, object], *, reading: bool) -> None:
    VERDICT.check(doc, reading=reading)
    if ID.fullmatch(str(doc["id"])) is None or doc["triage"] not in TRIAGE:
        raise _Invalid("a verdict needs a finding id and a word from the triage vocabulary")


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


_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def _toml_value(value: object) -> str:
    """A TOML basic string, integer or boolean. Non-BMP text is written as it is (UTF-8), never
    as a JSON surrogate pair, which TOML cannot read."""
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if type(value) is not str:
        raise Refused("a value has a type the record cannot hold")
    out = []
    for ch in value:
        if ch in _ESCAPES:
            out.append(_ESCAPES[ch])
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _render(doc: Mapping[str, object]) -> bytes:
    lines = [f"schema_version = {SCHEMA_VERSION}"]
    lines += [f"{name} = {_toml_value(v)}" for name, v in doc.items() if name != "schema_version"]
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
    require_input(needles, refusal)  # an empty input set would let everything through
    _check_record(record, tester)
    for name, value in record.items():
        for text in _strings(value):
            # Structural fields passed their grammar above; only free text gets the scalar lookup.
            _guard(text, name, needles, None if name in STRUCTURAL else refusal)
    for name, blob in artifacts.items():
        # `<id>.toml` is the record itself, so a name that ends the file in `.toml` is refused.
        if ARTIFACT.fullmatch(name) is None or f"{record['id']}.{name}".endswith(".toml"):
            raise Refused("an artifact name is not valid")
        # Needles are matched on the raw bytes, so a non-UTF-8 needle is still found; each text
        # reading (UTF-8, UTF-16) is then checked for needles and scalars too.
        for text in _decodings(blob):
            _guard(text, f"artifact {name}", needles, refusal)
        if hits(blob, needles):
            raise Refused(f"artifact {name} holds a needle or a scalar from the input")
    target = Path(root) / pass_id / f"{record['id']}.toml"
    prefix = f"{record['id']}."
    with exclusive_claim(target):
        # The record is the commit marker: an id that has one is used for good, whoever wrote it.
        if os.path.lexists(target):
            raise AlreadyPublished(f"already exists: {target}")
        # Files left by a killed writer are finished by a retry with the same names. Any other
        # name beside this id is another bundle's, and the record must not join the two.
        stray = (
            {p.name for p in target.parent.glob(f"{prefix}*") if p.name.startswith(prefix)}
            - {f"{prefix}{n}" for n in artifacts}
            - {target.name}
        )
        if stray:
            raise Refused("the pass folder holds artifacts of an unfinished write of this id")
        for name, blob in artifacts.items():
            publish_or_same(target.with_name(f"{prefix}{name}"), blob)
        publish_private_once(target, _render(record))
    return target


def write_triage(root: Path, pass_id: str, finding_id: str, verdict: str) -> Path:
    """The triager's verdict as `<id>.triage.toml`: one fixed word, create-once, for a finding
    that exists. A verdict with no finding is an orphan and is refused."""
    doc = {"id": finding_id, "triage": verdict}
    bad = None
    try:
        _validate_verdict(doc, reading=False)
    except _Invalid as exc:
        bad = str(exc)
    if bad is not None or PASS_ID.fullmatch(pass_id) is None:
        raise Refused(bad or "the pass id is not valid")
    folder = Path(root) / pass_id
    if not os.path.isfile(folder / f"{finding_id}.toml"):
        raise Refused("there is no finding record for this verdict")
    target = folder / f"{finding_id}.triage.toml"
    publish_private_once(target, _render(doc))
    return target


def _read(text: str, check: Callable[[dict[str, object]], None]) -> dict[str, object]:
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        doc = None
    if doc is None:
        raise ReaderError("not valid TOML")
    bad = None
    try:
        check(doc)
    except _Invalid as exc:
        bad = str(exc)
    if bad is not None:
        raise ReaderError(bad)
    return doc


def read_triage(text: str) -> dict[str, object]:
    """Strict reader for a verdict: version 1, exact types, a word from the vocabulary."""
    return _read(text, lambda d: _validate_verdict(d, reading=True))


def read_record(text: str) -> dict[str, object]:
    """Strict reader: version 1 only, exact primitive types, unknown extra members allowed."""
    return _read(text, lambda d: _validate(d, reading=True))


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
    require_input(needles, refusal)
    folder = Path(root) / pass_id
    # Only `<id>.toml` is a record: an artifact or a verdict has a dot in its stem.
    found = []
    for p in sorted(folder.glob("*.toml")):
        if ID.fullmatch(p.stem):
            record = read_record(p.read_text(encoding="utf-8"))
            if record["id"] != p.stem:
                raise ReaderError("a record's id does not match its file name")
            found.append(record)
    verdicts = {}
    for p in sorted(folder.glob("*.triage.toml")):
        doc = read_triage(p.read_text(encoding="utf-8"))
        if doc["id"] != p.name.removesuffix(".triage.toml"):
            raise ReaderError("a verdict's id does not match its file name")
        verdicts[str(doc["id"])] = str(doc["triage"])
    ids = {str(r["id"]) for r in found}
    if set(verdicts) - ids:
        raise Refused("a verdict has no finding record")
    if ids - set(verdicts):
        raise Refused("some findings are not triaged yet; publish after triage")
    rows = [
        f"| {r['id']} | {r['group']} | {r['proposed_tier']} | {verdicts[str(r['id'])]} |"
        for r in found
    ]
    body = [f"# QA-BETA pass {pass_id}", "", f"Findings: {len(found)}", ""]
    if rows:
        body += ["| Id | Group | Proposed tier | Triage |", "|---|---|---|---|", *rows]
    record_text = "\n".join(body) + "\n"
    slack = f"QA-BETA pass {pass_id}: {len(found)} findings. Ids: " + ", ".join(
        str(r["id"]) for r in found
    )
    # Both texts hold only grammar-checked fields and counts, so a corpus number such as `1` would
    # collide with a count: needles only. Free text was checked when each record was written.
    _guard(record_text, "the pass record", needles, None)
    _guard(slack, "the Slack text", needles, None)
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
    try:
        needles = read_needles(args.needles.read_text(encoding="utf-8"))
        refusal = RefusalSet.loads(args.refusal.read_text(encoding="utf-8"))
        if args.action == "publish":
            return _publish_cli(args, needles, refusal)
        return _write_cli(args, needles, refusal)
    except NothingRead as exc:
        sys.stderr.write(f"not run: {exc}\n")
        return 2
    except OSError as exc:
        if isinstance(exc, FileExistsError):
            sys.stderr.write(f"refused: {exc}\n")
            return 1
        sys.stderr.write("not run: an input file could not be read\n")
        return 2
    except (Refused, ReaderError, RefusalSetError) as exc:
        sys.stderr.write(f"refused: {exc}\n")
        return 1


def _publish_cli(args: argparse.Namespace, needles: Sequence[bytes], refusal: RefusalSet) -> int:
    # Fail closed: a pass nobody was told about is a pass that did not happen.
    if not args.no_slack and not os.environ.get("QA_SLACK_SCRIPT"):
        sys.stderr.write("refused: QA_SLACK_SCRIPT is not set (use --no-slack)\n")
        return 1
    status: list[str] = []
    notify = None if args.no_slack else lambda t: status.append(_slack(t))
    publish(args.root, args.pass_id, needles, refusal, records_dir=args.records_dir, notify=notify)
    sys.stdout.write(f"slack: {'not sent' if args.no_slack else status[0]}\n")
    return 1 if not args.no_slack and status[0] != "posted" else 0


def _write_cli(args: argparse.Namespace, needles: Sequence[bytes], refusal: RefusalSet) -> int:
    """The submission entry point. The tester is required: it scopes every id to its owner."""
    if not args.tester or PASS_ID.fullmatch(args.tester) is None:
        sys.stderr.write("refused: write needs --tester, the issued tester name\n")
        return 1
    if args.record is None:
        sys.stderr.write("refused: write needs --record\n")
        return 1
    names = [a.partition("=")[0] for a in args.artifact]
    if any("=" not in a for a in args.artifact) or len(set(names)) != len(names):
        sys.stderr.write("refused: each --artifact is NAME=PATH and each name appears once\n")
        return 1
    record = read_record(args.record.read_text(encoding="utf-8"))
    arts = {n: Path(p).read_bytes() for n, _, p in (a.partition("=") for a in args.artifact)}
    write(args.root, args.pass_id, record, needles, refusal, tester=args.tester, artifacts=arts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
