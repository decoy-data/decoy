"""The one safe-URL parser: no user, password or query ever comes out of it."""

from __future__ import annotations

import pytest

from decoy.safe_url import redacted_location, safe_url_parts

_PW = "SENTINEL-pw-1a2b"
_TOK = "SENTINEL-tok-3c4d"


@pytest.mark.parametrize(
    ("url", "scheme", "netloc", "path"),
    [
        (
            f"https://u:{_PW}@hooks.example.com:8443/a/b?t={_TOK}",
            "https",
            "hooks.example.com:8443",
            "/a/b",
        ),
        (f"https://u:{_PW}@hooks.example.com/x", "https", "hooks.example.com", "/x"),
        (f"s3://u:{_PW}@[::1]:9000/x?t={_TOK}", "s3", "[::1]:9000", "/x"),
    ],
)
def test_parts_carry_no_credential(url: str, scheme: str, netloc: str, path: str) -> None:
    parts = safe_url_parts(url)
    assert parts is not None
    assert (parts.scheme, parts.netloc, parts.path) == (scheme, netloc, path)
    assert _PW not in repr(parts)
    assert _TOK not in repr(parts)


@pytest.mark.parametrize("url", ["https://h:notaport/x", "not a url", "https:///only-path", ""])
def test_unreadable_url_gives_none(url: str) -> None:
    assert safe_url_parts(url) is None


@pytest.mark.parametrize(
    ("raw", "shown"),
    [
        ("data/out.csv", "data/out.csv"),
        (f"https://u:{_PW}@files.example.com/o.csv?t={_TOK}", "https://files.example.com"),
        (f"sftp://u:{_PW}@[::1]:22/o.csv", "sftp://[::1]:22"),
        (f"https://u:{_PW}@h:bad/o.csv?t={_TOK}", "(remote location)"),
        (f"://u:{_PW}@h/o.csv", "(remote location)"),
        (f"//u:{_PW}@files.example.com:8443/p?t={_TOK}", "//files.example.com:8443"),
        (f"//u@[::1]/p?t={_TOK}", "//[::1]"),
        (f"//u:{_PW}@h:bad/p", "(remote location)"),
        ("//server/share/out.csv", "//server/share/out.csv"),
    ],
)
def test_redacted_location(raw: str, shown: str) -> None:
    assert redacted_location(raw) == shown
