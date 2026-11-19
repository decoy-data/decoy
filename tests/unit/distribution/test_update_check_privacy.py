"""REL-WEB RW-C1 (plan section 5.2, P1 to P5; AT-C1 to AT-C5). Each test drives the real
`maybe_print_notice` against a loopback `http.server`, so the evidence is what reached a socket."""

from __future__ import annotations

import io
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from tests import loopback_tls
from typer.testing import CliRunner

from decoy import _update_check
from decoy.distribution import version_document as vd

DOC_PATH = "/cli/version.json"


def _document(latest: str, *, message: str = "") -> bytes:
    doc = vd.build_document(
        latest=latest, min_supported="0.1", artifacts={}, serial=1, message=message
    )
    return vd.canonical_document_bytes(doc)


class _Loopback:
    """One loopback HTTP server that records every request and answers with one response."""

    def __init__(self, status: int = 200, body: bytes = b"", headers: dict | None = None):
        self.status, self.body, self.headers = status, body, headers or {}
        self.requests: list[tuple[str, list[tuple[str, str]]]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                server.requests.append((self.requestline, list(self.headers.items())))
                self.send_response(server.status)
                for name, value in server.headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(server.body)))
                self.end_headers()
                self.wfile.write(server.body)

            do_CONNECT = do_GET  # a proxied https request opens with CONNECT

            def log_message(self, *args: object) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}{DOC_PATH}"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def serve(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def start(*args, tls: bool = True, **kwargs) -> _Loopback:
        server = _Loopback(*args, **kwargs)
        if tls:
            # The update check opens only https, so the loopback server speaks it.
            loopback_tls.secure(server._httpd, tmp_path, monkeypatch)
            server.url = server.url.replace("http://", "https://", 1)
        request.addfinalizer(server.close)
        return server

    return start


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """No CI, no opt-out, no proxy, and a private cache home."""
    for name in (
        "CI",
        "DECOY_NO_UPDATE_CHECK",
        "NO_PROXY",
        "http_proxy",
        "HTTP_PROXY",
        "https_proxy",
        "HTTPS_PROXY",
        "all_proxy",
        "ALL_PROXY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("DECOY_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, clean_env: Path) -> Path:
    """`clean_env` on a start that counts as interactive."""
    monkeypatch.setattr(_update_check, "_interactive", lambda: True)
    return clean_env


def _start() -> str:
    out = io.StringIO()
    _update_check.maybe_print_notice(stream=out)
    return out.getvalue()


def _cache() -> dict:
    return json.loads(_update_check._cache_path().read_text(encoding="utf-8"))


# AT-C1 (P1), AT-C3 (P3: one request in 24 hours), AT-C4 (P4: two cache keys) -----------


def test_one_request_with_exactly_the_p1_headers(monkeypatch, home, serve) -> None:
    server = serve(body=_document("99.0.0"))
    monkeypatch.setenv("DECOY_VERSION_URL", server.url)
    assert "99.0.0" in _start()
    _start()
    assert len(server.requests) == 1
    cache = _cache()
    assert set(cache) == {"checked_at", "latest"} and cache["latest"] == "99.0.0"
    assert isinstance(cache["checked_at"], int) and not isinstance(cache["checked_at"], bool)
    line, headers = server.requests[0]
    assert line == f"GET {DOC_PATH} HTTP/1.1"
    assert len(headers) == 4, headers
    assert {name.lower(): value for name, value in headers} == {
        "host": f"127.0.0.1:{server.port}",
        "user-agent": "decoy-update-check",
        "accept-encoding": "identity",
        "connection": "close",
    }


# AT-C2 (P2): a 3xx ends the check; the redirect target never sees a request ----------------


def test_a_redirect_is_not_followed(monkeypatch, home, serve) -> None:
    target = serve(body=_document("99.0.0"))
    origin = serve(status=302, headers={"Location": target.url})
    monkeypatch.setenv("DECOY_VERSION_URL", origin.url)
    assert _start() == ""
    assert len(origin.requests) == 1 and target.requests == []
    assert _cache()["latest"] is None


# AT-C3 (P3): no request when the start is not interactive --------------------------------


def _stream(tty: bool) -> io.StringIO:
    stream = io.StringIO()
    stream.isatty = lambda: tty
    return stream


@pytest.mark.parametrize(
    ("ci", "stdout_tty", "stderr_tty", "opt_out", "requests"),
    [
        (None, True, True, None, 1),  # the control: an interactive start sends one request
        ("true", True, True, None, 0),
        (None, False, True, None, 0),  # piped stdout, which is how `--json` output is read
        (None, True, False, None, 0),
        (None, True, True, "1", 0),
    ],
    ids=["interactive", "ci", "stdout-not-a-tty", "stderr-not-a-tty", "env-opt-out"],
)
def test_requests_only_on_an_interactive_start(
    monkeypatch, clean_env, serve, ci, stdout_tty, stderr_tty, opt_out, requests
) -> None:
    server = serve(body=_document("99.0.0"))
    monkeypatch.setenv("DECOY_VERSION_URL", server.url)
    if ci is not None:
        monkeypatch.setenv("CI", ci)
    if opt_out is not None:
        monkeypatch.setenv("DECOY_NO_UPDATE_CHECK", opt_out)
    monkeypatch.setattr("sys.stdout", _stream(stdout_tty))
    monkeypatch.setattr("sys.stderr", _stream(stderr_tty))
    _update_check.maybe_print_notice(stream=io.StringIO())
    assert len(server.requests) == requests


@pytest.mark.parametrize(("flag", "requests"), [([], 1), (["--no-update-check"], 0)])
def test_the_no_update_check_flag_stops_the_request(
    monkeypatch, home, serve, flag, requests
) -> None:
    import decoy.__main__ as main

    server = serve(body=_document("99.0.0"))
    monkeypatch.setenv("DECOY_VERSION_URL", server.url)
    monkeypatch.setattr(main, "_key_unresolved", lambda: False)
    result = CliRunner().invoke(main.app, [*flag, "info"])
    assert result.exit_code == 0, result.output
    assert len(server.requests) == requests


def test_a_configured_proxy_still_carries_the_check(monkeypatch, home, serve) -> None:
    proxy = serve(body=_document("99.0.0"), tls=False)  # a plain-http proxy
    monkeypatch.delenv("no_proxy")
    monkeypatch.setenv("https_proxy", f"http://127.0.0.1:{proxy.port}")
    monkeypatch.setenv("DECOY_VERSION_URL", "https://update.invalid/cli/version.json")
    _start()
    # An https request goes through a proxy as a CONNECT tunnel to the host the URL names.
    assert proxy.requests[0][0].startswith("CONNECT update.invalid:443 ")


# AT-C5 (P5): a bad response is cached as null, prints nothing, and costs one request a day -


def _closed_port_url() -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}{DOC_PATH}"


@pytest.mark.parametrize(
    "case", ["oversize", "redirect", "escape-code", "not-a-version", "too-long", "refused"]
)
def test_a_bad_response_is_cached_as_null_and_prints_nothing(
    monkeypatch, home, serve, case
) -> None:
    server = {
        # A valid document, so only the size cap can refuse it.
        "oversize": lambda: serve(body=_document("99.0.0", message="x" * (1 << 20))),
        "redirect": lambda: serve(status=302, headers={"Location": "http://127.0.0.1:9/"}),
        "escape-code": lambda: serve(body=_document("\x1b[2J")),
        "not-a-version": lambda: serve(body=_document("latest, trust me")),
        "too-long": lambda: serve(body=_document("1." + "9" * 80)),
        "refused": lambda: None,
    }[case]()
    monkeypatch.setenv("DECOY_VERSION_URL", server.url if server else _closed_port_url())
    assert _start() == ""
    assert set(_cache()) == {"checked_at", "latest"} and _cache()["latest"] is None
    _start()
    if server is not None:
        assert len(server.requests) == 1


def test_a_failure_is_cached_at_the_cadence_clock(home, serve) -> None:
    server = serve(status=500)
    assert _update_check.check_latest(url=server.url, now=1000) is None
    assert _cache() == {"checked_at": 1000, "latest": None}
    _update_check.check_latest(url=server.url, now=1000 + 86399)
    assert len(server.requests) == 1


def test_the_notice_prints_the_canonical_version(monkeypatch, home, serve) -> None:
    server = serve(body=_document("v99.0"))
    monkeypatch.setenv("DECOY_VERSION_URL", server.url)
    notice = _start()
    assert "-> 99.0)" in notice and "v99.0" not in notice
    assert _cache()["latest"] == "99.0"


def test_a_raw_value_already_in_the_cache_is_not_shown(monkeypatch, home) -> None:
    _update_check._write_cache("\x1b[2J", int(time.time()))  # as an older build could have
    monkeypatch.setenv("DECOY_VERSION_URL", _closed_port_url())
    assert _cache()["latest"] == "\x1b[2J" and _update_check.check_latest() is None
    assert _start() == ""
