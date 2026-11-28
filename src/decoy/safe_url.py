"""Safe components of a URL, for anything that prints, logs or records one.

A URL can carry `user:password@` and a query string, and an incoming-webhook URL carries its
token in the path. This module is the one parser: it returns scheme, host, port and path and
never the user, the password or the query. Callers pick what they may show; a log line or a
recorded path takes `netloc` or `redacted_location`, which drop the path as well.

Parsing is `urllib.parse.urlsplit`; a bad port or an unparseable URL gives `None`, not an
error carrying the text.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    """A recorded path as it may be printed or stored.

    A plain path is returned as it is. A URL (it holds `://`) keeps `scheme://host[:port]` only:
    the user, password, path and query are dropped. A URL that cannot be read gives a fixed
    text, never its characters. A network-path reference (`//host/...`) with a user or password
    keeps `//host[:port]` only; one without credentials is a plain path and is returned as is.
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
    """`//host[:port]` for a `//user:pass@host/...` reference; other `//...` text unchanged.

    Credential-free is decided first, on the text before the first `/`, `?` or `#`, so a POSIX
    name such as `//build[1]/share` is never rejected by URL host parsing.
    """
    authority = raw[2:].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "@" not in authority:
        return raw
    parts = safe_url_parts(f"x:{raw}")
    return _UNKNOWN_LOCATION if parts is None else f"//{parts.netloc}"
