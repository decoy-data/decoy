"""Source and target calls: `csv("in.csv")`, `s3("bucket", "key")` and the config they become.

Each call names a connector. Its plain arguments fill the connector's locator fields in order,
and every `key: value` option is passed to the engine under the same key unless renamed here. The
engine owns the field list: an option it does not know is refused by its validation, and the
compiler reports that refusal on the option's source line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from decoy.lang import _ast as nodes
from decoy.lang._errors import Span, fail

SourceMap = dict[tuple[Any, ...], Span]


@dataclass(frozen=True)
class Connector:
    type: str
    positional: tuple[str, ...]
    format: str | None  # None: read from the file extension or a `format:` option
    source_defaults: dict[str, Any] = field(default_factory=dict)


CONNECTORS: dict[str, Connector] = {
    # A CSV source has a header row unless `header: false` says otherwise.
    "csv": Connector("file", ("path",), "csv", {"has_header": True}),
    "parquet": Connector("file", ("path",), "parquet"),
    "fixed_width": Connector("file", ("path",), "fixed_width"),
    "s3": Connector("s3", ("bucket", "key"), None),
    "gcs": Connector("gcs", ("bucket", "object"), None),
}

# Shorter words in the language for engine field names.
RENAMES = {"header": "has_header", "credentials": "credentials_ref"}
FORMATS = {".csv": "csv", ".parquet": "parquet"}


def plain(value: nodes.Value) -> Any:
    """A syntax-tree value as the plain Python value the config holds."""
    if isinstance(value.value, tuple):
        return [plain(item) for item in value.value]
    if isinstance(value.value, dict):
        return {key: plain(item) for key, item in value.value.items()}
    return value.value


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
    if is_source:
        out.update(connector.source_defaults)
    for option in call.options:
        key = RENAMES.get(option.key.text, option.key.text)
        if key in connector.positional or key == "type":
            raise fail(
                "lang.option_not_allowed",
                f"`{option.key.text}` is set by the plain values of `{call.name.text}`",
                option.key.span,
            )
        out[key] = plain(option.value)
        spans[(*path, key)] = option.value.span
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
