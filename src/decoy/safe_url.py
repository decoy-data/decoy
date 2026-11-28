"""Safe components of a URL, for anything that prints, logs or records one.

A URL can carry `user:password@` and a query string, and an incoming-webhook URL carries its
token in the path. This module is the one parser: it returns scheme, host, port and path and
never the user, the password or the query. Callers pick what they may show; a log line or a
recorded path takes `netloc` or `redacted_location`, which drop the path as well.

Report output goes through one display boundary (`display_text`, `display_location`,
`display_copy`). A span scanner finds each location in a string and shows it as
`scheme://host[:port]`, `//host` or `(remote location)`. Parsers disagree on where a pasted
password ends: RFC parsers (CPython `urllib.parse`, urllib3, yarl, pip `redact_auth_from_url`,
sentry-python `sanitize_url`) split on the last `@` before the first `/ ? #`; DSN parsers (libpq,
git `transport_anonymize_url`, SQLAlchemy) split on the first `@`, and SQLAlchemy lets `/ ? #`
and spaces into the password. The scanner takes the widest reading: everything from the
authority start to the last `@` on the line is userinfo, and a host is shown only when that
userinfo holds no whitespace, `/ ? # @` or backslash. The shown form is built from parsed parts,
as pip, Sentry and yarl `URL.origin()` do, never by deleting from the raw text. The rules and
their table: `docs/plans/2026-11-28-d6-manifest-display-boundary.md`, section 1.

Parsing is `urllib.parse.urlsplit`; a bad port or an unparseable URL gives `None`, not an
error carrying the text.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, overload
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


# Span starts. S1: `://` after a run of scheme characters, or a collapsed `scheme:/` whose run is
# at least two characters with a letter (so `C:/` stays a drive). The lookbehind makes a span take
# in the whole run, so a second pass meets the same run and the scan is idempotent. S2: a bare
# `//` after a character that cannot be part of a path.
_RUN = r"[A-Za-z0-9+.\-]"
_START = re.compile(
    rf"(?<!{_RUN})(?P<s1a>{_RUN}*)://"
    rf"|(?<!{_RUN})(?P<s1b>{_RUN}*[A-Za-z]{_RUN}+):/(?!/)"
    r"|(?<![A-Za-z0-9._~/\-])(?P<s2>//)(?=[^\s/])"
)
_SCHEME_MARK = re.compile(rf"{_RUN}*://|{_RUN}*[A-Za-z]{_RUN}+:/")
_WHITESPACE = re.compile(r"\s")
_SEGMENT = re.compile(r"[^/?#\s]*")
_PREFIX = re.compile(r"[^/?#\r\n]*")
# A userinfo holding one of these cannot be told apart from a host, a path or a second password.
_BAD_USERINFO = re.compile(r"[\s/?#@\\]")
_AUTHORITY = re.compile(r"//([^/?#\s][^/?#]*)")
_CLOSERS = {">": "<", ")": "(", "]": "[", "}": "{", '"': '"', "'": "'", "`": "`"}
_LINE_BREAK = re.compile(r"(\r\n|\r|\n)")


def _line_end(text: str, pos: int) -> int:
    ends = [i for i in (text.find("\r", pos), text.find("\n", pos)) if i >= 0]
    return min(ends, default=len(text))


def _netloc(body: str, at: int) -> str | None:
    """The `host[:port]` to show for the authority that starts `body`, or None (fail closed).

    `at` is the index of the userinfo `@` in `body`, or -1 when there is no userinfo.
    """
    if at >= 0 and _BAD_USERINFO.search(body, 0, at):
        return None
    host = _SEGMENT.match(body, at + 1)
    assert host is not None  # the segment pattern also matches the empty string
    if "\\" in host.group():
        return None
    parts = safe_url_parts(f"x://{host.group()}")
    return None if parts is None else parts.netloc


def _end(text: str, start: int, a: int, at: int, whole: bool) -> int:
    """Where a span ends: the next whitespace after its host; a closer matching the opener
    just before the span stays outside it."""
    if whole:
        return len(text)
    found = _WHITESPACE.search(text, a if at < 0 else at + 1)
    end = len(text) if found is None else found.start()
    if end > a and start > 0 and _CLOSERS.get(text[end - 1]) == text[start - 1]:
        return end - 1
    return end


def _suspect(text: str, a: int) -> int:
    """The userinfo `@` of a bare `//` reference, or -1 for an ordinary share.

    The prefix up to `/ ? #` or the line end decides, spaces included: an `@` in it, or a `:`
    in it with an `@` later on the line.
    """
    line_end = _line_end(text, a)
    at = text.rfind("@", a, line_end)
    prefix = _PREFIX.match(text, a, line_end)
    assert prefix is not None
    colon = prefix.group().find(":")
    if "@" in prefix.group() or (colon >= 0 and at > a + colon):
        return at
    return -1


def _scheme_span(text: str, start: int, a: int, run: str, whole: bool) -> tuple[int, str]:
    at = text.rfind("@", a, _line_end(text, a))
    end = _end(text, start, a, at, whole)
    netloc = _netloc(text[a:end], at - a if at >= 0 else -1)
    if netloc is None or not run[:1].isalpha():
        return end, _UNKNOWN_LOCATION
    return end, f"{run.lower()}://{netloc}"


def _share_span(text: str, start: int, a: int, whole: bool) -> tuple[int, str | None]:
    """A bare `//` span: (end, shown), shown None for an ordinary share left unchanged."""
    at = _suspect(text, a)
    end = _end(text, start, a, at, whole)
    body = text[a:end]
    if at >= 0:
        netloc = _netloc(body, at - a)
    else:
        segment = _SEGMENT.match(body)
        assert segment is not None
        if "\\" in segment.group():
            return end, _UNKNOWN_LOCATION
        # Two authorities in one token have no single display host.
        if any("@" in m[1] for m in _AUTHORITY.finditer(body, segment.end())):
            return end, _UNKNOWN_LOCATION
        if "?" not in body and "#" not in body:
            return end, None
        netloc = _netloc(body, -1)
    return end, _UNKNOWN_LOCATION if netloc is None else f"//{netloc}"


def _span(text: str, found: re.Match[str], whole: bool) -> tuple[int, str | None]:
    if found["s2"] is not None:
        return _share_span(text, found.start(), found.end(), whole)
    run = found["s1a"] if found["s1a"] is not None else found["s1b"]
    return _scheme_span(text, found.start(), found.end(), run, whole)


def _scan(text: str, pos: int) -> str:
    pieces: list[str] = []
    copied = 0
    while (found := _START.search(text, pos)) is not None:
        end, shown = _span(text, found, whole=False)
        if shown is None:
            pos = found.end()  # an unchanged share is rescanned from its authority
            continue
        pieces.extend((text[copied : found.start()], shown))
        copied = pos = end
    pieces.append(text[copied:])
    return "".join(pieces)


def display_text(text: str) -> str:
    """`text` with every location span in it shown by its safe form."""
    if ":/" not in text and "//" not in text:
        return text
    return _scan(text, 0)


def _location_line(value: str) -> str:
    found = _START.match(value)
    if found is not None and found["s2"] is None:  # the value is a scheme URL
        return _span(value, found, whole=True)[1] or _UNKNOWN_LOCATION
    if _SCHEME_MARK.search(value):  # a path that holds a URL has no single display host
        return _UNKNOWN_LOCATION
    if found is not None:  # the value is a bare `//` reference
        shown = _span(value, found, whole=True)[1]
        return _scan(value, found.end()) if shown is None else shown
    return display_text(value)


def display_location(value: str) -> str:
    """A location field or an echoed path argument as it may be shown, line by line."""
    parts = _LINE_BREAK.split(value)
    return "".join(p if i % 2 else _location_line(p) for i, p in enumerate(parts))


def display_file_name(path: Path) -> str:
    """The name of `path` to show: its safe location when that differs, else its base name.

    Display comes first: a base name cut from a URL-shaped path is a bare token no scanner finds.
    """
    shown = display_location(str(path))
    return shown if shown != str(path) else path.name


def redacted_location(raw: str) -> str:
    """A recorded path or argument as it may be printed or stored.

    A URL keeps its scheme and authority only. A double-slash filesystem path
    can contain literal punctuation in its filename. On display, userinfo,
    a query delimiter or a fragment delimiter identifies a remote reference.
    """
    return remote_location(raw) or raw


def remote_location(raw: str, local_file: Callable[[Path], bool] | None = None) -> str | None:
    """Return the safe remote location, or None for a file path.

    A URL and a `//` reference with userinfo follow the display rules, so the writer never
    records a host the display would refuse. A writer can identify an existing file whose name
    resembles a query; a display reader has only the text and hides ambiguous query values.
    """
    if "://" in raw:
        found = _START.match(raw)
        if found is None or found["s1a"] is None:
            return _UNKNOWN_LOCATION
        return _span(raw, found, whole=True)[1]
    if _AUTHORITY.match(raw) is None:
        return None
    at = _suspect(raw, 2)
    if at < 0 and local_file is not None and ("?" in raw or "#" in raw) and local_file(Path(raw)):
        return None
    return _share_span(raw, 0, 2, whole=True)[1]


class DisplayCopy(dict[str, Any]):
    """A display copy: every string and key in it went through the display boundary.

    Built only by `display_copy` (sentry R4). It is a `dict`, so it serializes as JSON as is.
    Renderers take one, never the recorded value.
    """


LocationFields = frozenset[tuple[str, ...]]


def location_fields(pointers: Iterable[str], prefix: str) -> LocationFields:
    """JSON-pointer patterns under `prefix` as key paths; `*` matches every key or index."""
    return frozenset(
        tuple(part.replace("~1", "/").replace("~0", "~") for part in p[len(prefix) :].split("/"))
        for p in pointers
        if p.startswith(prefix)
    )


def _is_location(path: tuple[str, ...], fields: LocationFields) -> bool:
    return any(
        len(f) == len(path) and all(c in ("*", k) for c, k in zip(f, path, strict=True))
        for f in fields
    )


def _free_key(name: str, taken: Mapping[str, object]) -> str:
    """`name`, or the smallest free `name (n)` with n >= 2: an earlier key is never displaced."""
    if name not in taken:
        return name
    n = 2
    while f"{name} ({n})" in taken:
        n += 1
    return f"{name} ({n})"


def _copy(value: object, path: tuple[str, ...], fields: LocationFields) -> object:
    if isinstance(value, str):
        return display_location(value) if _is_location(path, fields) else display_text(value)
    if isinstance(value, Mapping):
        shown = DisplayCopy()
        for key, item in value.items():
            shown[_free_key(display_text(str(key)), shown)] = _copy(item, (*path, str(key)), fields)
        return shown
    if isinstance(value, (list, tuple)):
        return [_copy(item, (*path, str(i)), fields) for i, item in enumerate(value)]
    return value


@overload
def display_copy(value: str, fields: LocationFields = ...) -> str: ...


@overload
def display_copy(value: Mapping[str, Any], fields: LocationFields = ...) -> DisplayCopy: ...


@overload
def display_copy(value: list[Any] | tuple[Any, ...], fields: LocationFields = ...) -> list[Any]: ...


@overload
def display_copy(value: object, fields: LocationFields = ...) -> object: ...


def display_copy(value: object, fields: LocationFields = frozenset()) -> object:
    """A display copy of `value`: str to str, a list or tuple to a list, a dict to `DisplayCopy`.

    A string at a key path in `fields` is a location (`display_location`); every other string
    and every key is text (`display_text`). Two keys that display alike stay apart.
    """
    return _copy(value, (), fields)


@overload
def display_safe(value: Mapping[str, Any]) -> DisplayCopy: ...


@overload
def display_safe(value: list[Any] | tuple[Any, ...]) -> list[Any]: ...


@overload
def display_safe(value: object) -> object: ...


def display_safe(value: object) -> object:
    """`display_copy` with no location fields: every string and key is shown as text."""
    return display_copy(value, frozenset())


def display_path(path: Path | str) -> str:
    """A user-supplied path argument as it may be echoed.

    `Path` folds `https://u:p@h/x` into `https:/u:p@h/x`; the collapsed scheme is read back as
    `https://`.
    """
    return display_location(str(path))
