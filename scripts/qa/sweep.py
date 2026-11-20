"""The one needles sweep and the refusal set (plan 4, 5.2, 5.5).

    python -m scripts.qa.sweep --needles data/markers.txt <captured file>...

It keeps the checklist's exit meanings: 1 is a pass (no needle found), 0 is a finding, 2 means the
check did not run (a file is missing or nothing was read). A sweep that read nothing never passes:
a silent no-op is the bug this guards against.

Needles are markers and secrets, one per line in a node-local file. A secret given as hex also
matches as its raw bytes, as the first-user journey does. The refusal set holds salted hashes of
canonical scalar forms, so an arbitrary input or output value (a number, a date, a two-word name)
can be recognised in text without keeping the value itself. A scalar of one or two characters
is not indexed (see `MIN_SCALAR`); every longer one is.

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
# Scalars of one or two characters are the only ones left out of the refusal set: "1" or "ok"
# would match any message. Everything of three or more (`Bob`, `123`) is indexed and matched as
# whole tokens, so `Bobby` does not match `Bob`.
MIN_SCALAR = 3
# Only a line this long is read as a hex secret; a short hex-looking marker stays text.
MIN_HEX = 32
_WORD = re.compile(r"\w+")
_SALT_BYTES = 16


class RegistryError(ValueError):
    """The surface registry is malformed."""


class NothingRead(RuntimeError):
    """The sweep was given nothing to read, so a clean result would mean nothing."""


@dataclass(frozen=True)
class Surface:
    id: str
    check: str


@dataclass(frozen=True)
class Registry:
    surfaces: dict[str, Surface]
    exceptions: dict[str, tuple[str, ...]]  # exception id -> surfaces it applies to


@dataclass(frozen=True)
class Leak:
    surface: str
    name: str
    coordinate: str  # `n<index>` for a needle, `s` for a refusal-set hit


def load_registry(path: Path = SURFACES) -> Registry:
    doc = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    if type(doc.get("schema_version")) is not int or doc["schema_version"] != 1:
        raise RegistryError("surfaces.toml schema_version must be the integer 1")
    surfaces = {}
    for raw in doc.get("surface", []):
        ident, check = raw.get("id"), raw.get("check")
        if type(ident) is not str or check not in CHECKS or ident in surfaces:
            raise RegistryError("a surface needs a unique id and a known check")
        surfaces[ident] = Surface(ident, check)
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
    """The one tokenizer for both sides of the refusal set: case-folded runs of word characters.

    Punctuation, spacing and case never decide a match, so `O'Brien`, `Smith, John` and
    `(555) 123-4567` are found however a message wraps them.
    """
    return _WORD.findall(unicodedata.normalize("NFC", text).casefold())


def _forms(value: object) -> list[str]:
    """Every text form a scalar can take. A datetime also appears with a space for the `T`."""
    form = canonical(value)
    if isinstance(value, datetime.datetime):
        return [form, form.replace("T", " ", 1)]
    return [form]


class RefusalSet:
    """Salted hashes of the token forms of scalars. The values themselves are not kept."""

    def __init__(self, salt: bytes, digests: frozenset[str], lengths: frozenset[int]) -> None:
        self.salt, self._digests, self._lengths = salt, digests, lengths

    @classmethod
    def build(cls, scalars: Iterable[object], salt: bytes | None = None) -> RefusalSet:
        salt = salt if salt is not None else secrets.token_bytes(_SALT_BYTES)
        forms = set()
        for value in scalars:
            for form in _forms(value) if value is not None else ():
                tokens = words(form)
                if len("".join(tokens)) >= MIN_SCALAR:
                    forms.add(tuple(tokens))
        lengths = frozenset(len(t) for t in forms)
        return cls(salt, frozenset(cls._digest(salt, " ".join(t)) for t in forms), lengths)

    @staticmethod
    def _digest(salt: bytes, form: str) -> str:
        return hashlib.sha256(salt + form.encode("utf-8")).hexdigest()

    def is_empty(self) -> bool:
        """True when nothing was indexed, so this set can never find anything."""
        return not self._digests

    def contains(self, scalar: object) -> bool:
        return any(self.found_in(form) for form in _forms(scalar))

    def found_in(self, text: str) -> bool:
        """True when any run of tokens in `text` is a set member. Windows count tokens."""
        tokens = words(text)
        for i in range(len(tokens)):
            for size in self._lengths:
                window = tokens[i : i + size]
                if (
                    len(window) == size
                    and self._digest(self.salt, " ".join(window)) in self._digests
                ):
                    return True
        return False

    def dumps(self) -> str:
        doc = {"salt": self.salt.hex(), "digests": sorted(self._digests)}
        return json.dumps({**doc, "lengths": sorted(self._lengths)})

    @classmethod
    def loads(cls, text: str) -> RefusalSet:
        doc = json.loads(text)
        return cls(bytes.fromhex(doc["salt"]), frozenset(doc["digests"]), frozenset(doc["lengths"]))

    def save(self, path: Path) -> None:
        publish_private_once(path, self.dumps().encode("utf-8"))


def require_input(needles: Iterable[bytes], refusal: RefusalSet | None) -> None:
    """The one not-run rule: no real needle and no usable refusal set means the input was not read.

    The sweep, the finding writer and `publish` all call this, so a pass whose needles file and
    refusal set came out empty can never read as clean.
    """
    if not any(needles) and (refusal is None or refusal.is_empty()):
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
    refusal: RefusalSet | None = None,
) -> list[Leak]:
    """Sweep named captures, each `(surface id, bytes)`. Raises `NothingRead` if all are empty.

    A `cells` surface is checked by the I1 cell rules, but a needle on it is still a leak here.
    """
    if not captures or not any(blob for _, blob in captures.values()):
        raise NothingRead("no capture held any bytes")
    require_input(needles, refusal)
    leaks: list[Leak] = []
    for name, (surface, blob) in captures.items():
        if surface not in registry.surfaces:
            raise RegistryError(f"{name}: unknown surface {surface!r}")
        leaks += [Leak(surface, name, f"n{i}") for i in hits(blob, needles)]
        if refusal is not None and refusal.found_in(blob.decode("utf-8", "replace")):
            leaks.append(Leak(surface, name, "s"))
    return leaks


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
