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
            "lang.unknown_connector",
            f"`{call.name.text}` is not a {role} this version of the language can write",
            call.name.span,
            "use one of: " + ", ".join(sorted(CONNECTORS)),
        )
    if len(call.positional) != len(connector.positional):
        wanted = ", ".join(connector.positional)
        raise fail(
            "lang.connector_arguments",
            f"`{call.name.text}` takes {len(connector.positional)} plain value(s): {wanted}",
            call.span,
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
                "lang.option_not_allowed",
                f"`{option.key.text}` is set by `{call.name.text}` itself",
                option.key.span,
            )
        if key in given:
            raise fail(
                "lang.option_repeated", f"`{option.key.text}` is given twice", option.key.span
            )
        given.add(key)
        out[key] = plain(option.value)
        spans[(*path, key)] = option.value.span
    missing = [k for k in connector.source_required if is_source and k not in given]
    if missing:
        written = next((w for w, e in RENAMES.items() if e == missing[0]), missing[0])
        raise fail(
            "lang.connector_option_required",
            f"`{call.name.text}` as a source must say `{written}: true` or `{written}: false`",
            call.span,
            "the file either starts with a row of column names or it does not",
        )
    if "format" not in out:
        located = str(out[connector.positional[-1]])
        suffix = next((s for s in FORMATS if located.lower().endswith(s)), None)
        if suffix is None:
            raise fail(
                "lang.format_unknown",
                f"cannot tell the file format of this {role} from its name",
                call.span,
                "add `format: csv` or `format: parquet`",
            )
        out["format"] = FORMATS[suffix]
    return out
