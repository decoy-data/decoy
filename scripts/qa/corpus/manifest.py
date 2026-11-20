"""Strict reader for `docs/qa/corpus/manifest.toml`, shared by the generator and the fetcher.

Why strict: a manifest that silently accepts a missing hash, an unknown field or a wrong type is
how an unchecked download or an unlicensed item gets in. Every error names the item id and the
field, never a value from the data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

SCHEMA_VERSION = 1
TIERS = ("S", "M", "L")
GENERATED = "generated"
# Licenses that allow internal testing without redistribution (plan 5.2). A new entry is a
# reviewed change, not a manifest edit.
ALLOWED_LICENSES = frozenset(
    {"Apache-2.0", "MIT", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0", "CC-BY-4.0"}
)
ITEM_FIELDS = frozenset(
    {"id", "origin", "license", "sha256", "tier", "format", "shapes", "marker_columns"}
)
# `max_bytes` caps a public download; `needs_conversion` marks an item no pass may use until a
# later slice converts it (a SQLite file the DuckDB source cannot read as is).
OPTIONAL_FIELDS = frozenset({"max_bytes", "needs_conversion"})
_ID = re.compile(r"[a-z0-9][a-z0-9-]*")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ManifestError(ValueError):
    """The manifest is malformed. The message holds field names and item ids only."""


@dataclass(frozen=True)
class Item:
    id: str
    origin: str
    license: str
    sha256: str
    tier: str
    format: str
    shapes: tuple[str, ...]
    marker_columns: tuple[str, ...]
    max_bytes: int = 0
    needs_conversion: str = ""

    @property
    def generated(self) -> bool:
        return self.origin == GENERATED


def _fail(item: str, field: str, why: str) -> ManifestError:
    return ManifestError(f"item {item!r}: field {field!r} {why}")


def _text(raw: dict[str, object], item: str, field: str) -> str:
    value = raw.get(field)
    if type(value) is not str or not value:
        raise _fail(item, field, "must be a non-empty string")
    return value


def _strings(raw: dict[str, object], item: str, field: str, *, empty_ok: bool) -> tuple[str, ...]:
    value = raw.get(field)
    ok = isinstance(value, list) and all(type(v) is str and v for v in value)
    if not ok or (not value and not empty_ok):
        raise _fail(item, field, "must be a list of non-empty strings")
    return tuple(value)  # type: ignore[arg-type]


def parse_item(raw: dict[str, object]) -> Item:
    ident = raw.get("id")
    name = ident if type(ident) is str else "?"
    if type(ident) is not str or _ID.fullmatch(ident) is None:
        raise _fail(name, "id", "must match [a-z0-9][a-z0-9-]*")
    extra = set(raw) - ITEM_FIELDS - OPTIONAL_FIELDS
    missing = ITEM_FIELDS - set(raw)
    if extra or missing:
        raise _fail(name, "fields", f"unknown {sorted(extra)} or missing {sorted(missing)}")
    origin = _text(raw, name, "origin")
    if origin != GENERATED and not origin.startswith("https://"):
        raise _fail(name, "origin", "must be 'generated' or an https URL")
    sha = raw["sha256"]
    if type(sha) is not str:
        raise _fail(name, "sha256", "must be a string")
    if origin == GENERATED:
        if sha != "":
            raise _fail(name, "sha256", "must be empty for a generated item")
    elif _SHA256.fullmatch(sha) is None:
        raise _fail(name, "sha256", "must be 64 lowercase hex characters")
    max_bytes = raw.get("max_bytes", 0)
    if type(max_bytes) is not int or max_bytes < 0:
        raise _fail(name, "max_bytes", "must be a non-negative integer")
    if origin != GENERATED and max_bytes == 0:
        raise _fail(name, "max_bytes", "is required for a public item")
    convert = raw.get("needs_conversion", "")
    if type(convert) is not str:
        raise _fail(name, "needs_conversion", "must be a string")
    tier = _text(raw, name, "tier")
    if tier not in TIERS:
        raise _fail(name, "tier", f"must be one of {TIERS}")
    return Item(
        id=ident,
        origin=origin,
        # The license may be missing or off the allow-list in a parsed item: fetch.py refuses it
        # (AT-8), so the manifest can still be read and audited.
        license=raw["license"] if type(raw["license"]) is str else "",
        sha256=sha,
        tier=tier,
        format=_text(raw, name, "format"),
        shapes=_strings(raw, name, "shapes", empty_ok=False),
        marker_columns=_strings(raw, name, "marker_columns", empty_ok=True),
        max_bytes=max_bytes,
        needs_conversion=convert,
    )


def parse_manifest(text: str) -> list[Item]:
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        raise ManifestError("the manifest is not valid TOML") from None
    version = doc.get("schema_version")
    if type(version) is not int:
        raise ManifestError("schema_version must be an integer")
    if version != SCHEMA_VERSION:
        raise ManifestError(f"schema_version {version} is not supported (want {SCHEMA_VERSION})")
    raw_items = doc.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ManifestError("items must be a non-empty list of tables")
    items = [parse_item(r) for r in raw_items]
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise ManifestError("an item id appears twice")
    return items


def load_manifest(path: Path) -> list[Item]:
    return parse_manifest(Path(path).read_text(encoding="utf-8"))
