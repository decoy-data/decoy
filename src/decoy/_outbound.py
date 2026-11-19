"""The one first-party outbound function: `open_url(url, purpose)`.

Every urllib request the CLI opens goes through here, under a named purpose. A purpose fixes
the schemes it may open and what it does with a redirect, so a flag, a version document or a
redirect hop cannot move a request to a scheme the purpose never allowed (`file:` for a
webhook, `http:` for an installer download).

| purpose            | schemes     | redirects                                                |
| `upgrade_document` | https, file | https to https only                                      |
| `upgrade_artifact` | https, file | https to https only (release downloads redirect to a CDN)|
| `update_check`     | https       | none                                                     |
| `notify_webhook`   | https, http | followed while every hop is https or http                |
| `notify_slack`     | https       | https to https only                                      |
| `otel`             | http, https | not opened here; `otel_endpoint_problem` is its rule     |

The URL is read once: the scheme that is checked is the scheme urllib dispatches on. A refusal
names the purpose and a well-known scheme only, never the URL, its credentials or its query,
and is raised outside any `except`, so no exception context carries the value.
"""

from __future__ import annotations

import ipaddress
import re
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

Purpose = Literal[
    "upgrade_document", "upgrade_artifact", "update_check", "notify_webhook", "notify_slack", "otel"
]


@dataclass(frozen=True)
class _Rule:
    schemes: frozenset[str]
    redirects: Literal["none", "https_only", "allowed_hops"]
    scheme_code: str


_UPGRADE = "url_scheme_refused"
_NOTIFY = "notify_url_scheme_refused"
_RULES: dict[str, _Rule] = {
    "upgrade_document": _Rule(frozenset({"https", "file"}), "https_only", _UPGRADE),
    "upgrade_artifact": _Rule(frozenset({"https", "file"}), "https_only", _UPGRADE),
    "update_check": _Rule(frozenset({"https"}), "none", _UPGRADE),
    "notify_webhook": _Rule(frozenset({"https", "http"}), "allowed_hops", _NOTIFY),
    "notify_slack": _Rule(frozenset({"https"}), "https_only", _NOTIFY),
    "otel": _Rule(frozenset({"https", "http"}), "none", _UPGRADE),
}
# Schemes that may appear in a refusal. Any other scheme text could be user data.
_NAMEABLE = frozenset({"http", "https", "file", "ftp", "data", "gopher", "ws", "wss"})
_URL_CHARS = re.compile(r"[\x21-\x7e]+")


class OutboundRefused(Exception):
    """A purpose refused a scheme or a redirect hop. `code` is the `--json` error code."""

    def __init__(self, code: str, purpose: Purpose, scheme: str | None) -> None:
        shown = scheme if scheme in _NAMEABLE else "other"
        super().__init__(f"{purpose}: {code.removesuffix('_refused').replace('_', ' ')} ({shown})")
        self.code = code
        self.purpose = purpose


def allowed_schemes(purpose: Purpose) -> tuple[str, ...]:
    return tuple(sorted(_RULES[purpose].schemes))


def _scheme_of(url: str) -> str | None:
    # The Request is built with the same reader urllib dispatches on, so the checked scheme
    # is the opened scheme (leading whitespace, control characters and `<URL:...>` included).
    try:
        return urllib.request.Request(url).type.lower()
    except ValueError:
        return None


def check_scheme(url: str, purpose: Purpose) -> None:
    """Raise `OutboundRefused` unless `purpose` may open `url`'s scheme."""
    rule = _RULES[purpose]
    scheme = _scheme_of(url)
    if scheme is not None and scheme in rule.schemes:
        return
    raise OutboundRefused(rule.scheme_code, purpose, scheme)


class RefuseRedirects(urllib.request.HTTPRedirectHandler):
    # Returning None makes urllib raise HTTPError for the 3xx instead of following it, so a
    # redirect can never send the request (and the user's IP) to a second host.
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class _PurposeRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, purpose: Purpose) -> None:
        self._purpose = purpose

    def http_error_302(self, req, fp, code, msg, headers):  # type: ignore[no-untyped-def]
        # urllib refuses `file:` and unknown schemes itself, with an HTTPError that quotes the
        # target. Checking here, before it does, gives every refused hop the same value-free
        # error and re-checks each hop against this purpose before the next request is built.
        target = headers.get("location") or headers.get("uri")
        if target is not None:
            rule = _RULES[self._purpose]
            scheme = _scheme_of(urljoin(req.full_url, target))
            allowed = scheme in rule.schemes
            if rule.redirects == "https_only":
                allowed = allowed and scheme == "https" and req.type == "https"
            if not allowed:
                fp.close()
                raise OutboundRefused("url_redirect_refused", self._purpose, scheme)
        return super().http_error_302(req, fp, code, msg, headers)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def redirect_handler(purpose: Purpose) -> urllib.request.HTTPRedirectHandler:
    if _RULES[purpose].redirects == "none":
        return RefuseRedirects()
    return _PurposeRedirects(purpose)


def _open(
    opener: urllib.request.OpenerDirector, req: urllib.request.Request, timeout: float | None
):
    return opener.open(req) if timeout is None else opener.open(req, timeout=timeout)


def open_url(
    url: str,
    purpose: Purpose,
    *,
    timeout: float | None = None,
    data: bytes | None = None,
    method: str | None = None,
    headers: Mapping[str, str] | None = None,
    user_agent: str | None = None,
) -> Any:
    """Open `url` for `purpose` and return the response (a context manager).

    Raises `OutboundRefused` for a scheme or a redirect hop the purpose does not allow; any
    other failure is urllib's own (`URLError`, `HTTPError`, `OSError`).
    """
    if purpose == "otel":
        raise ValueError("the otel purpose is applied by the telemetry exporter, not opened here")
    check_scheme(url, purpose)
    req = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
    opener = urllib.request.build_opener(redirect_handler(purpose))
    if user_agent is not None:
        # The default User-Agent names the Python version, so it is replaced, not added to.
        opener.addheaders = [("User-Agent", user_agent)]
    return _open(opener, req, timeout)


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    if addr.version == 4:
        return addr in ipaddress.ip_network("127.0.0.0/8")
    return addr == ipaddress.IPv6Address("::1")


def otel_endpoint_problem(
    endpoint: str, *, has_headers: bool, setting: str, headers_setting: str
) -> str | None:
    """The `otel` purpose's rule: why a collector URL is refused, or None. The text names the
    setting, never the value. A URL that is not plain `http(s)://host[:port]/path` is refused,
    and so are credential headers over cleartext to a non-loopback host."""
    if not _URL_CHARS.fullmatch(endpoint):
        return f"{setting}: not a URL"
    try:
        parts = urlsplit(endpoint)
        host, _port = (parts.hostname or "").lower(), parts.port
    except ValueError:
        return f"{setting}: not a URL"
    if parts.scheme not in _RULES["otel"].schemes or not host:
        return f"{setting}: must be an http:// or https:// URL with a host"
    if "@" in parts.netloc:
        return f"{setting}: must not carry credentials; use {headers_setting}"
    if parts.query or parts.fragment or endpoint.endswith(("?", "#")):
        return f"{setting}: must not carry a query string or fragment"
    if has_headers and parts.scheme == "http" and not _is_loopback(host):
        return f"{headers_setting} needs an https:// {setting} (http only for a loopback host)"
    return None
