"""Text that names a source path or URL in a finding, with credentials left out."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"]+")


def _redact_text(url: str) -> str:
    """Scheme, host, port and path only: no `user:password@`, query or fragment."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        if ":" in host:  # an IPv6 literal loses its brackets in `hostname`
            host = f"[{host}]"
        port = parts.port  # raises ValueError for a bad port
    except ValueError:
        return f"{url.split('://', 1)[0]}://(redacted)"
    netloc = f"{host}:{port}" if port is not None else host
    return f"{parts.scheme}://{netloc}{parts.path}"


def _redact_one(match: re.Match[str]) -> str:
    return _redact_text(match.group(0))


def redact_url(value: str) -> str:
    """One configured path or URL as shown in a finding, parsed whole.

    Userinfo may hold quotes and other characters a text scan would stop at, so a value with
    a scheme is parsed as a whole, not matched. A plain path comes back unchanged.
    """
    if re.match(r"[A-Za-z][A-Za-z0-9+.-]*://", value):
        return _redact_text(value)
    return value


def redact_urls(text: str) -> str:
    """`text` with the credentials, query and fragment of any URL in it removed.

    A plain filename or path has no `://`, so it comes back unchanged.
    """
    return _URL.sub(_redact_one, text)
