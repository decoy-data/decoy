"""Source and target calls: `csv("in.csv")`, `s3("bucket", "key")` and the config they become.

Each call names a connector. Its plain arguments fill the connector's locator fields in order,
and every `key: value` option is passed to the engine under the same key unless renamed here. The
engine owns the field list: an option it does not know is refused by its validation, and the
compiler reports that refusal on the option's source line.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from decoy.lang import _ast as nodes
from decoy.lang._ast import plain
from decoy.lang._codes import (
    CONNECTOR_ARGUMENTS,
    CONNECTOR_OPTION_REQUIRED,
    FORMAT_UNKNOWN,
    OPTION_REPEATED,
    OPTION_SET_BY_CONNECTOR,
    UNKNOWN_CONNECTOR,
)
from decoy.lang._errors import SourceMap, fail


@dataclass(frozen=True)
class Connector:
    type: str
    positional: tuple[str, ...]
    format: str | None  # None: read from the file extension or a `format:` option
    source_required: tuple[str, ...] = ()  # engine field names a source must state


CONNECTORS: dict[str, Connector] = {
    # A CSV source states whether it has a header row: the engine has no default for it.
    "csv": Connector("file", ("path",), "csv", ("has_header",)),
    "parquet": Connector("file", ("path",), "parquet"),
    "fixed_width": Connector("file", ("path",), "fixed_width"),
    "s3": Connector("s3", ("bucket", "key"), None),
    "gcs": Connector("gcs", ("bucket", "object"), None),
}

# Shorter words in the language for engine field names.
RENAMES = {"header": "has_header", "credentials": "credentials_ref"}
FORMATS = {".csv": "csv", ".parquet": "parquet"}


def lower_connector(
    call: nodes.Call, *, is_source: bool, path: tuple[Any, ...], spans: SourceMap
) -> dict[str, Any]:
    role = "source" if is_source else "target"
    connector = CONNECTORS.get(call.name.text)
    if connector is None:
        raise fail(
            UNKNOWN_CONNECTOR,
            call.name.span,
            "use one of: " + ", ".join(sorted(CONNECTORS)),
            connector=call.name.text,
            role=role,
        )
    if len(call.positional) != len(connector.positional):
        wanted = ", ".join(connector.positional)
        raise fail(
            CONNECTOR_ARGUMENTS,
            call.span,
            connector=call.name.text,
            count=len(connector.positional),
            wanted=wanted,
        )
    spans[path] = call.span
    out: dict[str, Any] = {"type": connector.type}
    if connector.format is not None:
        out["format"] = connector.format
    for key, value in zip(connector.positional, call.positional, strict=True):
        out[key] = plain(value)
        spans[(*path, key)] = value.span
    given: set[str] = set()
    for option in call.options:
        key = RENAMES.get(option.key.text, option.key.text)
        fixed = key == "type" or (key == "format" and connector.format is not None)
        if key in connector.positional or fixed:
            raise fail(
                OPTION_SET_BY_CONNECTOR,
                option.key.span,
                key=option.key.text,
                connector=call.name.text,
            )
        if key in given:
            raise fail(OPTION_REPEATED, option.key.span, key=option.key.text)
        given.add(key)
        out[key] = plain(option.value)
        spans[(*path, key)] = option.value.span
    missing = [k for k in connector.source_required if is_source and k not in given]
    if missing:
        written = next((w for w, e in RENAMES.items() if e == missing[0]), missing[0])
        raise fail(
            CONNECTOR_OPTION_REQUIRED,
            call.span,
            "the file either starts with a row of column names or it does not",
            connector=call.name.text,
            written=written,
        )
    if "format" not in out:
        located = str(out[connector.positional[-1]])
        suffix = next((s for s in FORMATS if located.lower().endswith(s)), None)
        if suffix is None:
            raise fail(
                FORMAT_UNKNOWN, call.span, "add `format: csv` or `format: parquet`", role=role
            )
        out["format"] = FORMATS[suffix]
    return out
