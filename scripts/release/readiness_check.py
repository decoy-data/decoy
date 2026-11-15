#!/usr/bin/env python3
"""Check a release-readiness instance (docs/release/release-readiness.md, plan REL-GATE 5.5, 5.6).

    readiness_check.py INSTANCE [--release] [--candidate candidate.json] [--engine-repo PATH]

The check validates structure and identity, not truth: whether a row's criterion was met
comes from running the command the row names. It always checks that every template row is
present once, that each result is ``pass``, ``fail`` or ``accepted-known-limit``, that a
``pass`` row cites evidence and an ``accepted-known-limit`` row names V2-LOG ids. With
``--candidate`` the G7 identity must equal the candidate record field for field. With
``--engine-repo`` every ``accepted-known-limit`` cell in the CLI and engine frozen-surface
maps must be listed by an instance row. ``--release`` adds: no ``fail`` row, a complete
identity that did not drift from G3 (and G5 for the digest) unless a rerun is recorded,
the sign-off block, and the licensor checks over the fixed license-file list.

Exit 0 complete, 1 any finding, 2 usage. Fail closed: unreadable or malformed input is a
FAIL line for that step, never a traceback. Output is reason codes and step names only,
never file contents, ids or exception text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROW_IDS = tuple(str(i) for i in range(1, 19))
# Rows whose evidence is a person's check, not a link (no tool reads decoy-web's proof sync
# or the worker-bootstrap gates today).
MANUAL_ROWS = frozenset({"12", "14"})
RESULTS = ("pass", "fail", "accepted-known-limit")
CANDIDATE_SCHEMA = "decoy-release-candidate/v1"
IDENTITY_FIELDS = {
    "cli_sha": re.compile(r"[0-9a-f]{40}"),
    "engine_tag": re.compile(r"v\d+\.\d+\.\d+"),
    "engine_commit": re.compile(r"[0-9a-f]{40}"),
    "sha256sums_sha256": re.compile(r"[0-9a-f]{64}"),
}
G3_FIELDS = ("cli_sha", "engine_tag", "engine_commit")
KEYS = (
    [f"g3.{f}" for f in G3_FIELDS]
    + ["g5.sha256sums_sha256"]
    + [f"g7.{f}" for f in IDENTITY_FIELDS]
    + [f"rerun.{f}" for f in IDENTITY_FIELDS]
    + ["licensor", "signoff.owner", "signoff.date", "signoff.decision"]
)
LEGAL_FILES = {
    "cli": ("LICENSE.md", "NOTICE", "LICENSING.md", "TRADEMARKS.md", "CONTRIBUTING.md"),
    "engine": ("LICENSE", "NOTICE", "TRADEMARKS.md", "CONTRIBUTING.md", "README.md"),
}
MAX_BYTES = 2_000_000

_KEY_LINE = re.compile(r"^- ([a-z0-9_.]+):[ \t]*(.*?)[ \t]*$")
_MARKER_LINE = re.compile(r"^- (cli|engine):(\S+) (TODO\S*) => (release-blocking|carry-forward)$")
_MARKER = re.compile(r"TODO(?:\([^)\s]*\)|:)?")
# Leading whitespace, quote marks and markdown emphasis, the (c) and the copyright sign are all
# forms a license file may use; a form this misses would let a stale licensor pass.
_LICENSOR_LINE = re.compile(
    r"^[\s>*_]*(?:(?:Copyright\b\s*(?:\([cC]\)|\u00a9)?|\u00a9|\([cC]\))\s*\d{4}(?:\s*-\s*\d{4})?[\s*_]*,?"
    r"|Licensor[\s*_]*:[\s*_]*)\s*(\S.*?)[\s*_]*$",
    re.IGNORECASE,
)
# The placeholder family in the license files: a sentence naming the entity, not only a
# copyright line, must follow the licensor value.
# It runs over the whole file text, so a line break or markdown emphasis between the words
# does not hide a mention.
_ENTITY = re.compile(
    r"Decoy[\s*_]+Labs[\s*_,]*(?:L\.?L\.?C|Incorporated|Inc|Corporation|Corp|Limited|Ltd"
    r"|Company|GmbH|Co)\b\.?",
    re.IGNORECASE,
)
_RIGHTS = re.compile(r"[\s,.;]*all rights reserved\W*$", re.IGNORECASE)
_SUFFIX = {"incorporated": "inc", "corporation": "corp", "limited": "ltd", "company": "co"}
_PLACEHOLDER_OWNERS = frozenset({"tbd", "n/a", "na", "none", "owner", "-"})
_VERSION_LINE = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)
_URL = re.compile(r"https://\S+")
_PATH = re.compile(r"[\w.-]+(?:/[\w.-]+)+")
_SHA = re.compile(r"[0-9a-f]{7,64}")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_HEX_WORD = re.compile(r"\b[0-9a-f]{7,40}\b")
# A digit is required so prose such as "see notes" is not read as an id.
_LIMIT_ID = re.compile(r"(?=.*\d)[A-Za-z0-9][A-Za-z0-9 ._-]*")
_LIMIT_CELL = re.compile(r"accepted-known-limit:(.*)$")


class Refusal(Exception):
    """Input that cannot be parsed at all; carries only a step and a reason code."""

    def __init__(self, step: str, code: str) -> None:
        super().__init__(code)
        self.step, self.code = step, code


def _read(path: Path, step: str, code: str) -> str:
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_BYTES:
            raise ValueError
        return raw.decode("utf-8")
    except (OSError, ValueError):  # UnicodeDecodeError is a ValueError
        raise Refusal(step, code) from None


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_rows(text: str) -> list[dict[str, str]]:
    """Rows of the readiness table; a malformed row has an empty ``id`` and stays visible."""
    names = ("id", "gate", "command", "criterion", "result", "evidence", "owner")
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if cells[0] == "id" or all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        if len(cells) != len(names):
            rows.append({n: "" for n in names})
            continue
        rows.append(dict(zip(names, cells)))
    return rows


def parse_keys(text: str) -> dict[str, str]:
    keys: dict[str, str] = {}
    for line in text.splitlines():
        m = _KEY_LINE.match(line)
        if m and m.group(1) in KEYS:
            if m.group(1) in keys:
                raise Refusal(m.group(1), "readiness_duplicate_key")
            keys[m.group(1)] = m.group(2)
    return keys


def _evidence_ok(row_id: str, evidence: str) -> bool:
    if row_id in MANUAL_ROWS:
        return bool(_DATE.search(evidence) and _HEX_WORD.search(evidence))
    return any(p.fullmatch(evidence) for p in (_URL, _PATH, _SHA))


def _limit_ids(evidence: str) -> list[str]:
    return [p.strip() for p in evidence.split(";")]


def check_rows(rows: list[dict[str, str]], release: bool) -> tuple[list[tuple[str, str]], set[str]]:
    found: list[tuple[str, str]] = []
    limit_ids: set[str] = set()
    seen: set[str] = set()
    for row in rows:
        rid = row["id"]
        if rid not in ROW_IDS:
            found.append(("row ?", "readiness_row_unknown"))  # never echo an unvetted id
            continue
        if rid in seen:
            found.append((f"row {rid}", "readiness_row_duplicate"))
            continue
        seen.add(rid)
        step, result, evidence = f"row {rid}", row["result"], row["evidence"]
        if result not in RESULTS:
            found.append((step, "readiness_result_invalid"))
        elif result == "pass" and not _evidence_ok(rid, evidence):
            found.append((step, "readiness_evidence_missing"))
        elif result == "accepted-known-limit":
            ids = _limit_ids(evidence)
            if evidence and all(_LIMIT_ID.fullmatch(i) for i in ids):
                limit_ids.update(ids)
            else:
                found.append((step, "readiness_known_limit_id_missing"))
        elif result == "fail" and release:
            found.append((step, "readiness_row_failed"))
    found += [(f"row {rid}", "readiness_row_missing") for rid in ROW_IDS if rid not in seen]
    return found, limit_ids


def _valid(field: str, value: str) -> bool:
    return bool(IDENTITY_FIELDS[field].fullmatch(value))


def check_identity(keys: dict[str, str], release: bool) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    pairs = [(f"g3.{f}", f"g7.{f}", f) for f in G3_FIELDS]
    pairs.append(("g5.sha256sums_sha256", "g7.sha256sums_sha256", "sha256sums_sha256"))
    for early, late, field in pairs:
        for key in (early, late):
            value = keys.get(key, "")
            if (value or release) and not _valid(field, value):
                found.append((key, "readiness_identity_missing"))
        a, b = keys.get(early, ""), keys.get(late, "")
        rerun = keys.get(f"rerun.{field}", "")
        if release and a and b and a != b and rerun != b:
            found.append((late, "readiness_identity_drift"))
    return found


def check_signoff(keys: dict[str, str]) -> list[tuple[str, str]]:
    owner = keys.get("signoff.owner", "")
    ok = {
        "signoff.owner": bool(owner)
        and not owner.startswith("<")
        and owner.casefold() not in _PLACEHOLDER_OWNERS,
        "signoff.date": bool(_DATE.fullmatch(keys.get("signoff.date", ""))),
        "signoff.decision": keys.get("signoff.decision") == "go",
    }
    return [(k, "readiness_signoff_missing") for k, good in ok.items() if not good]


def load_candidate(path: Path) -> dict[str, str]:
    def no_dupes(pairs):
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ValueError
        return dict(pairs)

    text = _read(path, "candidate", "readiness_candidate_invalid")
    try:
        doc = json.loads(text, object_pairs_hook=no_dupes)
    except (ValueError, RecursionError):
        raise Refusal("candidate", "readiness_candidate_invalid") from None
    fields = {"schema", "cli_version", *IDENTITY_FIELDS}
    if (
        not isinstance(doc, dict)
        or set(doc) != fields
        or doc["schema"] != CANDIDATE_SCHEMA
        or not all(isinstance(doc[f], str) for f in fields)
    ):
        raise Refusal("candidate", "readiness_candidate_invalid")
    return doc


def read_version(cli_root: Path) -> str:
    """The version the candidate must carry: the CLI's own literal, not a constant here."""
    text = _read(
        cli_root / "src" / "decoy" / "_version.py", "version", "readiness_version_unreadable"
    )
    m = _VERSION_LINE.search(text)
    if not m:
        raise Refusal("version", "readiness_version_unreadable")
    return m.group(1)


def normalize_entity(name: str) -> str:
    """One comparison form: case, commas, periods, emphasis, spacing and suffix spelling folded."""
    words = re.sub(r"[*_,]", " ", name.casefold().replace(".", "")).split()
    return " ".join(_SUFFIX.get(w, w) for w in words)


def check_row_text(rows: list[dict[str, str]], cli_root: Path) -> list[tuple[str, str]]:
    """Result and evidence are the filler's; every other cell must equal the template's."""
    try:
        template = _read(
            cli_root / "docs" / "release" / "release-readiness.md",
            "template",
            "readiness_template_unreadable",
        )
    except Refusal as exc:
        return [(exc.step, exc.code)]
    template_rows = parse_rows(template)
    if tuple(r["id"] for r in template_rows) != ROW_IDS:
        return [("template", "readiness_template_unreadable")]
    want = {r["id"]: r for r in template_rows}
    cols = ("gate", "command", "criterion", "owner")
    return [
        (f"row {r['id']}", "readiness_row_text_changed")
        for r in rows
        if r["id"] in want and any(r[c] != want[r["id"]][c] for c in cols)
    ]


def check_candidate(
    keys: dict[str, str], cand: dict[str, str], version: str
) -> list[tuple[str, str]]:
    found = [
        (f"g7.{f}", "readiness_candidate_mismatch")
        for f in IDENTITY_FIELDS
        if keys.get(f"g7.{f}", "") != cand[f]
    ]
    if cand["cli_version"] != version:
        found.append(("candidate.cli_version", "readiness_candidate_mismatch"))
    return found


def _map_limits(path: Path, label: str) -> tuple[set[str], list[tuple[str, str]]]:
    step = f"map {label}"
    try:
        text = _read(path, step, "readiness_map_unreadable")
    except Refusal as exc:
        return set(), [(exc.step, exc.code)]
    ids: set[str] = set()
    for line in text.splitlines():
        cells = _cells(line) if line.startswith("|") else []
        hit = next((c for c in cells if "accepted-known-limit" in c), None)
        if len(cells) < 4 or hit is None:
            continue
        m = _LIMIT_CELL.search(hit.replace("`", ""))
        limit = m.group(1).strip() if m else ""
        if not _LIMIT_ID.fullmatch(limit):
            return set(), [(step, "readiness_map_malformed")]
        ids.add(limit)
    return ids, []


def check_known_limits(
    cli_root: Path, engine_root: Path, listed: set[str]
) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for label, path in (
        ("cli", cli_root / "docs" / "release" / "frozen-surfaces.md"),
        ("engine", engine_root / "docs" / "frozen-surfaces.md"),
    ):
        ids, bad = _map_limits(path, label)
        found += bad
        if ids - listed:
            found.append((f"map {label}", "readiness_known_limit_missing"))
    return found


def check_legal(keys: dict[str, str], text: str, roots: dict[str, Path]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    licensor = keys.get("licensor", "")
    if not licensor or licensor.startswith("<") or licensor.upper() == "TBD":
        found.append(("licensor", "readiness_licensor_missing"))
        licensor = ""
    classes = {
        (m.group(1) + ":" + m.group(2), m.group(3)): m.group(4)
        for m in map(_MARKER_LINE.match, text.splitlines())
        if m
    }
    present: set[tuple[str, str]] = set()
    lines_seen = 0
    for repo, root in roots.items():
        for name in LEGAL_FILES[repo]:
            label = f"{repo}:{name}"
            try:
                body = _read(root / name, f"file {label}", "readiness_file_unreadable")
            except Refusal as exc:
                found.append((exc.step, exc.code))
                continue
            step = f"file {label}"
            for token in sorted(set(_MARKER.findall(body))):
                present.add((label, token))
                cls = classes.get((label, token))
                if cls is None:
                    found.append((step, "readiness_marker_unclassified"))
                elif cls == "release-blocking":
                    found.append((step, "readiness_marker_blocking"))
            names = [m.group(1) for m in map(_LICENSOR_LINE.match, body.splitlines()) if m]
            lines_seen += len(names)
            names = [_RIGHTS.sub("", n) for n in names] + _ENTITY.findall(body)
            if licensor and any(normalize_entity(n) != normalize_entity(licensor) for n in names):
                found.append((step, "readiness_licensor_mismatch"))
    if not lines_seen:
        found.append(("licensor", "readiness_licensor_lines_absent"))
    checked = {f"{repo}:" for repo in roots}
    stale = [k for k in classes if k not in present and k[0].split(":")[0] + ":" in checked]
    found += [("markers", "readiness_marker_stale")] * bool(stale)
    return found


def run(args: argparse.Namespace) -> list[tuple[str, str]]:
    text = _read(Path(args.instance), "instance", "readiness_unreadable")
    keys = parse_keys(text)
    found, listed = check_rows(parse_rows(text), args.release)
    found += check_identity(keys, args.release)
    found += check_row_text(parse_rows(text), Path(args.cli_root))
    if args.candidate:
        found += check_candidate(
            keys, load_candidate(Path(args.candidate)), read_version(Path(args.cli_root))
        )
    cli_root = Path(args.cli_root)
    if args.engine_repo:
        found += check_known_limits(cli_root, Path(args.engine_repo), listed)
    if args.release:
        found += check_signoff(keys)
        roots = {"cli": cli_root}
        if args.engine_repo:
            roots["engine"] = Path(args.engine_repo)
        found += check_legal(keys, text, roots)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="readiness_check.py", description=__doc__.split("\n")[0])
    parser.add_argument("instance")
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--candidate")
    parser.add_argument("--engine-repo")
    # Tests point this at a fixture tree; the default is the checkout the script lives in.
    parser.add_argument("--cli-root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args(argv)
    if args.release and not args.candidate:
        parser.error("--release requires --candidate")
    try:
        found = run(args)
    except Refusal as exc:
        found = [(exc.step, exc.code)]
    for step, code in found:
        print(f"FAIL {step}: {code}")
    if not found:
        print("PASS readiness")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
