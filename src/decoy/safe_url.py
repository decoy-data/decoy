"""Safe components of a URL, for anything that prints, logs or records one.

A URL can carry `user:password@` and a query string, and an incoming-webhook URL carries its
token in the path. This module is the one parser: it returns scheme, host, port and path and
never the user, the password or the query. Callers pick what they may show; a log line or a
recorded path takes `netloc` or `redacted_location`, which drop the path as well.

Parsing is `urllib.parse.urlsplit`; a bad port or an unparseable URL gives `None`, not an
error carrying the text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_UNKNOWN_LOCATION = "(remote location)"


@dataclass(frozen=True)
class SafeUrl:
    """The parts of a URL that hold no credential. `host` has its IPv6 brackets."""

    scheme: str
    host: str
    port: int | None
    path: str

    @property
    def netloc(self) -> str:
        """`host` or `host:port`."""
        return self.host if self.port is None else f"{self.host}:{self.port}"


def safe_url_parts(url: str) -> SafeUrl | None:
    """The scheme, host, port and path of `url`; None when it has no host or a bad port."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port  # raises ValueError for a bad port
    except ValueError:
        return None
    if not host:
        return None
    if ":" in host:  # an IPv6 literal loses its brackets in `hostname`
        host = f"[{host}]"
    return SafeUrl(scheme=parts.scheme, host=host, port=port, path=parts.path)


def redacted_location(raw: str) -> str:
    """A recorded path or argument as it may be printed or stored.

    A plain path is returned as it is. A remote reference keeps its scheme, host and port only:
    the user, password, path, query and fragment are dropped (a query can hold a token). A
    remote reference is a URL (it holds `://`) or a network-path reference (`//host/...`) that
    holds `@`, `?` or `#`. A plain `//name/...` path with none of those, such as
    `//build[1]/share`, is returned unchanged. A reference that cannot be read gives a fixed
    text, never its characters.
    """
    if raw.startswith("//") and "://" not in raw:
        return _redacted_network_path(raw)
    if "://" not in raw:
        return raw
    parts = safe_url_parts(raw)
    if parts is None or not parts.scheme:
        return _UNKNOWN_LOCATION
    return f"{parts.scheme}://{parts.netloc}"


def _redacted_network_path(raw: str) -> str:
    """`//host[:port]` for a `//host/...` reference with `@`, `?` or `#`; other `//...` unchanged.

    Plain is decided first, on the text, so a POSIX name such as `//build[1]/share` is never
    rejected by URL host parsing.
    """
    if not any(mark in raw for mark in "@?#"):
        return raw
    parts = safe_url_parts(f"x:{raw}")
    return _UNKNOWN_LOCATION if parts is None else f"//{parts.netloc}"


def display_safe(value: Any) -> Any:
    """A copy of `value` with `redacted_location` applied to every string in it, keys included.

    The one display boundary: a manifest copy or a payload that a person will read or share goes
    through here whole, so a field added later is covered without a list of field names.
    """
    if isinstance(value, str):
        return redacted_location(value)
    if isinstance(value, dict):
        return {display_safe(k): display_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [display_safe(v) for v in value]
    return value


_COLLAPSED_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):/(?!/)")


def display_path(path: Path | str) -> str:
    """A user-supplied path argument as it may be echoed.

    `Path` folds `https://u:p@h/x` into `https:/u:p@h/x`, so the collapsed scheme is restored
    before `redacted_location` reads it.
    """
    text = str(path)
    return redacted_location(_COLLAPSED_SCHEME.sub(r"\1://", text))
