"""The one needles sweep and the refusal set (plan 4, 5.2, 5.5).

    python -m scripts.qa.sweep --needles data/markers.txt <captured file>...

It keeps the checklist's exit meanings: 1 is a pass (no needle found), 0 is a finding, 2 means the
check did not run (a file is missing or nothing was read). A sweep that read nothing never passes:
a silent no-op is the bug this guards against.

Needles are markers and secrets, one per line in a node-local file. A secret given as hex also
matches as its raw bytes, as the first-user journey does. The refusal set holds salted hashes of
canonical scalar forms, so an arbitrary input or output value (a number, a date, a two-word name)
can be recognised in text without keeping the value itself. Every canonical scalar is indexed,
however short (`F`, `CA`, `0`, `-1` are real data). A scalar matches only as whole tokens, never
as part of a longer word or number, so `CA` is not found in `CAT` and `0` is not found in `10`. A
number is one token with its sign and decimal point.

A leak is reported as a surface id, a name and an opaque coordinate. The coordinate is a needle
index, so it carries no marker text and no text taken from the data.

Standard library only; reads the surface registry from `docs/qa/surfaces.toml`.
"""

from __future__ import annotations

import argparse
import datetime
import decimal
import hashlib
import json
import re
import secrets
import sys
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from scripts.qa.io import publish_private_once

SURFACES = Path(__file__).resolve().parents[2] / "docs/qa/surfaces.toml"
CHECKS = ("cells", "needles", "needles-encrypted")
# Every scalar is indexed. A match is always on whole tokens (`words`), so a short value such as
# `CA` or `0` is found as its own token and not inside `CAT` or `10`. A number token keeps its sign
# and decimal point. Indexing and lookup share the one normalization.
# Only a line this long is read as a hex secret; a short hex-looking marker stays text.
MIN_HEX = 32
# A number is one token (`-7.25`, `3.5`); anything else is a run of word characters. The sign is
# part of the number only when no word character or dot comes before it, so `123-4567` stays two
# tokens.
_TOKEN = re.compile(r"(?<![\w.])[+-]?\d+(?:\.\d+)?(?!\w)|\w+")
_NUMBER = re.compile(r"[+-]?\d+(?:\.\d+)?")
_SALT_BYTES = 16
REFUSAL_VERSION = 1


class RegistryError(ValueError):
    """The surface registry is malformed."""


class NothingRead(RuntimeError):
    """The sweep was given nothing to read, so a clean result would mean nothing."""


class RefusalSetError(ValueError):
    """A stored refusal set is malformed, from another version, or inconsistent. Never read as clean."""


@dataclass(frozen=True)
class Surface:
    id: str
    check: str
    # False on the run summary: its own row counts collide with sequential key values, so a
    # match made only of numbers is not a leak there (plan 5.2, rev 3.3).
    numeric_matches: bool = True


@dataclass(frozen=True)
class Registry:
    surfaces: dict[str, Surface]
    exceptions: dict[str, tuple[str, ...]]  # exception id -> surfaces it applies to


@dataclass(frozen=True)
class Leak:
    surface: str
    name: str
    coordinate: str  # `n<index>` for a needle, `s<index>` for a refusal-set hit


def load_registry(path: Path = SURFACES) -> Registry:
    doc = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    if type(doc.get("schema_version")) is not int or doc["schema_version"] != 1:
        raise RegistryError("surfaces.toml schema_version must be the integer 1")
    surfaces = {}
    for raw in doc.get("surface", []):
        ident, check = raw.get("id"), raw.get("check")
        numeric = raw.get("numeric_matches", True)
        if type(ident) is not str or check not in CHECKS or ident in surfaces:
            raise RegistryError("a surface needs a unique id and a known check")
        if type(numeric) is not bool:
            raise RegistryError("numeric_matches must be true or false")
        surfaces[ident] = Surface(ident, check, numeric)
    exceptions = {}
    for raw in doc.get("exception", []):
        applies = tuple(raw.get("applies_to", ()))
        if not set(applies) <= set(surfaces):
            raise RegistryError(f"exception {raw.get('id')!r} names an unknown surface")
        exceptions[raw["id"]] = applies
    if not surfaces:
        raise RegistryError("no surfaces")
    return Registry(surfaces, exceptions)


def read_needles(text: str) -> tuple[bytes, ...]:
    """One needle per line; a hex line also adds its decoded bytes (the journey's secret form)."""
    found: list[bytes] = []
    for line in text.splitlines():
        if not line:
            continue
        found.append(line.encode("utf-8"))
        if len(line) >= MIN_HEX and len(line) % 2 == 0 and re.fullmatch(r"[0-9a-fA-F]+", line):
            found.append(bytes.fromhex(line))
    return tuple(found)


def hits(blob: bytes, needles: Sequence[bytes]) -> list[int]:
    """Indexes of the needles found in `blob`. Never returns text."""
    return [i for i, n in enumerate(needles) if n and n in blob]


def canonical(value: object) -> str:
    """The stable text form of a scalar: its decoded type decides, so `7`, `7.0` and `"7"` agree."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, decimal.Decimal):
        return canonical(float(value) if value != value.to_integral() else int(value))
    if isinstance(value, datetime.date | datetime.datetime):
        return value.isoformat()
    return " ".join(unicodedata.normalize("NFC", str(value)).split())


def words(text: str) -> list[str]:
    """The one tokenizer for both sides of the refusal set: case-folded tokens.

    A number is one token (sign and decimal point included); anything else is a run of word
    characters. Punctuation, spacing and case never decide a match, so `O'Brien`, `Smith, John`
    and `(555) 123-4567` are found however a message wraps them. Indexing, lookup and the length
    rule all use this one function.
    """
    return _TOKEN.findall(unicodedata.normalize("NFC", text).casefold())


def _numeric_only(tokens: Sequence[str]) -> bool:
    """A bare integer or decimal: one number token. A date or phone number is several tokens."""
    return len(tokens) == 1 and _NUMBER.fullmatch(tokens[0]) is not None


def _forms(value: object) -> list[str]:
    """Every text form a scalar can take. A datetime also appears with a space for the `T`."""
    form = canonical(value)
    if isinstance(value, datetime.datetime):
        return [form, form.replace("T", " ", 1)]
    return [form]


class RefusalSet:
    """Salted hashes of the token forms of scalars. The values themselves are not kept."""

    def __init__(self, salt: bytes, groups: Mapping[int, frozenset[str]]) -> None:
        # Digests are grouped by token count, so the lengths a lookup tries and the digests it
        # compares can never disagree: there is no separate lengths list to get out of step.
        self.salt = salt
        self._groups = {n: frozenset(d) for n, d in groups.items() if d}

    @classmethod
    def build(cls, scalars: Iterable[object], salt: bytes | None = None) -> RefusalSet:
        salt = salt if salt is not None else secrets.token_bytes(_SALT_BYTES)
        forms = set()
        for value in scalars:
            for form in _forms(value) if value is not None else ():
                tokens = words(form)
                if tokens:
                    forms.add(tuple(tokens))
        groups: dict[int, set[str]] = {}
        for form_tokens in forms:
            digest = cls._digest(salt, " ".join(form_tokens))
            groups.setdefault(len(form_tokens), set()).add(digest)
        return cls(salt, {n: frozenset(d) for n, d in groups.items()})

    @staticmethod
    def _digest(salt: bytes, form: str) -> str:
        return hashlib.sha256(salt + form.encode("utf-8")).hexdigest()

    def is_empty(self) -> bool:
        """True when nothing was indexed, so this set can never find anything."""
        return not self._groups

    def contains(self, scalar: object) -> bool:
        return any(self.found_in(form) for form in _forms(scalar))

    def found_in(self, text: str, *, numeric: bool = True) -> bool:
        """True when any run of tokens in `text` is a set member. Windows count tokens.

        With `numeric` false, a run that is one bare number is skipped (the run summary's rule).
        """
        tokens = words(text)
        for i in range(len(tokens)):
            for size, digests in self._groups.items():
                window = tokens[i : i + size]
                if len(window) != size or (not numeric and _numeric_only(window)):
                    continue
                if self._digest(self.salt, " ".join(window)) in digests:
                    return True
        return False

    def dumps(self) -> str:
        groups = {str(n): sorted(d) for n, d in sorted(self._groups.items())}
        return json.dumps(
            {"schema_version": REFUSAL_VERSION, "salt": self.salt.hex(), "groups": groups}
        )

    @classmethod
    def loads(cls, text: str) -> RefusalSet:
        """Strict reader: version 1, exact types, no extra members. A bad set is refused."""
        reason = _refusal_problem(text)
        if isinstance(reason, str):  # raised outside any handler: no cause or context
            raise RefusalSetError(reason)
        return reason

    def save(self, path: Path) -> None:
        publish_private_once(path, self.dumps().encode("utf-8"))


_HEX64 = re.compile(r"[0-9a-f]{64}")


def _refusal_problem(text: str) -> str | RefusalSet:
    """A fixed reason string when the stored set is not valid, else the set."""
    try:
        doc = json.loads(text)
    except ValueError:
        return "the refusal set is not valid JSON"
    if not isinstance(doc, dict) or set(doc) != {"schema_version", "salt", "groups"}:
        return "the refusal set has the wrong members"
    version = doc["schema_version"]
    if type(version) is not int or version != REFUSAL_VERSION:
        return "the refusal set has an unsupported schema_version"
    salt, raw = doc["salt"], doc["groups"]
    if type(salt) is not str or re.fullmatch(r"[0-9a-f]{32}", salt) is None:
        return "the refusal set salt is not 16 bytes of hex"
    if not isinstance(raw, dict):
        return "the refusal set groups are not an object"
    groups: dict[int, frozenset[str]] = {}
    for key, digests in raw.items():
        if re.fullmatch(r"[1-9][0-9]{0,3}", key) is None:
            return "a refusal set group length is not a positive integer"
        if not isinstance(digests, list) or not digests:
            return "a refusal set group has no digests"
        if not all(isinstance(d, str) and _HEX64.fullmatch(d) for d in digests):
            return "a refusal set digest is not a SHA-256 hex string"
        if len(set(digests)) != len(digests):
            return "a refusal set group repeats a digest"
        groups[int(key)] = frozenset(digests)
    return RefusalSet(bytes.fromhex(salt), groups)


Sets = RefusalSet | Sequence[RefusalSet] | None


def _sets(refusal: Sets) -> list[RefusalSet]:
    if refusal is None:
        return []
    return [refusal] if isinstance(refusal, RefusalSet) else list(refusal)


def require_input(needles: Iterable[bytes], refusal: Sets) -> None:
    """The one not-run rule: no real needle and no usable refusal set means the input was not read.

    The sweep, the finding writer and `publish` all call this, so a pass whose needles file and
    refusal set came out empty can never read as clean.
    """
    if not any(needles) and all(r.is_empty() for r in _sets(refusal)):
        raise NothingRead("no needles and no refusal set: a clean result would mean nothing")


def has_fragment(text: str, fragment: str) -> bool:
    """Case-insensitive substring test, for a detected entity inside the cell it came from.

    The one place outside the sweep where text is searched for a value; invariants call it instead
    of using `in` themselves.
    """
    return bool(fragment) and fragment.casefold() in text.casefold()


def sweep(
    captures: Mapping[str, tuple[str, bytes]],
    needles: Sequence[bytes],
    registry: Registry,
    refusal: Sets = None,
) -> list[Leak]:
    """Sweep named captures, each `(surface id, bytes)`. Raises `NothingRead` if all are empty.

    Each surface runs the check its registry entry names (`CHECK_RULES`). A `cells` surface is
    checked by the I1 cell rules, but a needle on it is still a leak here.
    """
    if not captures or not any(blob for _, blob in captures.values()):
        raise NothingRead("no capture held any bytes")
    require_input(needles, refusal)
    leaks: list[Leak] = []
    for name, (surface, blob) in captures.items():
        if surface not in registry.surfaces:
            raise RegistryError(f"{name}: unknown surface {surface!r}")
        rule = CHECK_RULES[registry.surfaces[surface].check]
        leaks += rule(registry.surfaces[surface], name, blob, needles, _sets(refusal))
    return leaks


def _needles_only(
    surface: Surface, name: str, blob: bytes, needles: Sequence[bytes], sets: list[RefusalSet]
) -> list[Leak]:
    """`cells` and `needles-encrypted`: a needle is a leak. The values in a cell or in encrypted
    text are the point of the file, so the refusal set is not read there (I1 owns the cells)."""
    return [Leak(surface.id, name, f"n{i}") for i in hits(blob, needles)]


def _needles_and_scalars(
    surface: Surface, name: str, blob: bytes, needles: Sequence[bytes], sets: list[RefusalSet]
) -> list[Leak]:
    """`needles`: needles in the bytes, and refusal-set scalars in the text."""
    leaks = _needles_only(surface, name, blob, needles, sets)
    text = blob.decode("utf-8", "replace")
    return leaks + [
        Leak(surface.id, name, f"s{i}")
        for i, r in enumerate(sets)
        if r.found_in(text, numeric=surface.numeric_matches)
    ]


# One entry per registry check; a test fails if `CHECKS` and this table differ.
CHECK_RULES = {
    "cells": _needles_only,
    "needles": _needles_and_scalars,
    "needles-encrypted": _needles_only,
}


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--needles", type=Path, required=True)
    ap.add_argument("--surface", default="stdout", help="surface id for the files given")
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args(argv)
    if not args.needles.is_file() or not all(f.is_file() for f in args.files):
        sys.stderr.write("not run: a needles file or a capture is missing\n")
        return 2
    needles = read_needles(args.needles.read_text(encoding="utf-8"))
    captures = {f.name: (args.surface, f.read_bytes()) for f in args.files}
    try:
        leaks = sweep(captures, needles, load_registry())
    except NothingRead:
        sys.stderr.write("not run: nothing was read\n")
        return 2
    for leak in leaks:
        sys.stdout.write(f"{leak.surface} {leak.name} {leak.coordinate}\n")
    return 0 if leaks else 1


if __name__ == "__main__":
    sys.exit(main())
