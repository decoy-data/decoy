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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import overload
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
    if not host or parts.netloc.count("@") > 1:
        return None
    if ":" in host:  # an IPv6 literal loses its brackets in `hostname`
        host = f"[{host}]"
    return SafeUrl(scheme=parts.scheme, host=host, port=port, path=parts.path)


def redacted_location(raw: str) -> str:
    """A recorded path or argument as it may be printed or stored.

    A URL keeps its scheme and authority only. A double-slash filesystem path
    can contain literal punctuation in its filename. On display, userinfo,
    a query delimiter or a fragment delimiter identifies a remote reference.
    """
    return remote_location(raw) or raw


def remote_location(raw: str, local_file: Callable[[Path], bool] | None = None) -> str | None:
    """Return the safe remote location, or None for a file path.

    A writer can identify an existing file whose name resembles a query.
    A display reader has only the text and hides ambiguous query values.
    """
    if "://" in raw:
        parts = safe_url_parts(raw)
        if parts is None or not parts.scheme:
            return _UNKNOWN_LOCATION
        return f"{parts.scheme}://{parts.netloc}"
    authority = _AUTHORITY.match(raw)
    if authority is None:
        return None
    if "@" not in authority[1]:
        if "?" not in raw and "#" not in raw:
            # Multiple authorities in one token have no unambiguous display host.
            if any("@" in inner[1] for inner in _AUTHORITY.finditer(raw, authority.end())):
                return _UNKNOWN_LOCATION
            return None
        if local_file is not None and local_file(Path(raw)):
            return None
    parts = safe_url_parts(raw)
    return _UNKNOWN_LOCATION if parts is None else f"//{parts.netloc}"


_AUTHORITY = re.compile(r"//([^/?#\s][^/?#]*)")
_LOCATION_START = re.compile(r"""(?<![^\s"'(\[{=])(?:[A-Za-z][A-Za-z0-9+.\-]*:|:)?//(?=[^/?#\s])""")
# A pasted password can contain spaces and @. Match through the final authority @.
_LOCATION_BODY = re.compile(r"(?:[^/?#\r\n]*@)?\S*")


def _display_text(text: str) -> str:
    if "//" not in text:
        return text
    pieces: list[str] = []
    end = 0
    for start in _LOCATION_START.finditer(text):
        if start.start() < end:
            continue
        body = _LOCATION_BODY.match(text, start.end())
        assert body is not None  # the body pattern also matches the empty string
        shown = remote_location(text[start.start() : body.end()])
        if shown is not None:
            pieces.extend((text[end : start.start()], shown))
            end = body.end()
    pieces.append(text[end:])
    return "".join(pieces)


@overload
def display_safe(value: dict[str, object]) -> dict[str, object]: ...


@overload
def display_safe(value: object) -> object: ...


def display_safe(value: object) -> object:
    """Redact location spans in every string in a display copy, including keys."""
    if isinstance(value, str):
        return _display_text(value)
    if isinstance(value, dict):
        return {_display_text(k): display_safe(v) for k, v in value.items()}
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
