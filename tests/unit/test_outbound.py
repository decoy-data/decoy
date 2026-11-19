"""AT-S6a, AT-S6c, AT-S6e and AT-S6f: the one outbound function and its per-purpose rules.

Freeze batch plan 10.7. Redirect cases run against real local servers; the https ones use a
throwaway self-signed certificate that `SSL_CERT_FILE` makes the default context trust.
"""

from __future__ import annotations

import http.server
import threading
import urllib.error
from collections.abc import Iterator
from pathlib import Path

import pytest
from tests import loopback_tls

from decoy import _outbound
from decoy.notify import NotifySpecError, parse_notify_spec
from decoy.telemetry import OtelSettingsError, validate_endpoint

SECRET = "SECRETTOKEN"


def _no_context(exc: BaseException) -> None:
    assert exc.__cause__ is None and exc.__context__ is None


def test_file_opens_for_upgrade_purposes_only(tmp_path: Path) -> None:
    doc = tmp_path / "v.json"
    doc.write_bytes(b"{}")
    for purpose in ("upgrade_document", "upgrade_artifact"):
        with _outbound.open_url(doc.as_uri(), purpose=purpose) as resp:
            assert resp.read() == b"{}"
    for purpose in ("notify_webhook", "notify_slack", "update_check"):
        with pytest.raises(_outbound.OutboundRefused) as info:
            _outbound.open_url(doc.as_uri(), purpose=purpose)
        assert not hasattr(info.value, "url")
        assert str(tmp_path) not in str(info.value) and purpose in str(info.value)
        _no_context(info.value)


@pytest.mark.parametrize(
    "spec, code",
    [
        ("webhook:file:///x", "notify_url_scheme_refused"),
        ("webhook:ftp://u:SECRETTOKEN@h/x", "notify_url_scheme_refused"),
        ("webhook:SECRETTOKEN", "notify_url_scheme_refused"),
        ("slack:http://hooks.example.com/SECRETTOKEN", "notify_url_scheme_refused"),
        ("sms:SECRETTOKEN", "notify_spec_invalid"),
        ("SECRETTOKEN", "notify_spec_invalid"),
        ("webhook:", "notify_spec_invalid"),
    ],
)
def test_a_notify_spec_error_is_value_free(spec: str, code: str) -> None:
    with pytest.raises(NotifySpecError) as info:
        parse_notify_spec(spec)
    assert info.value.code == code
    assert SECRET not in str(info.value)
    assert spec.endswith(":") or spec not in str(info.value)  # `kind:` alone is a fixed word
    _no_context(info.value)


def test_allowed_notify_schemes_parse() -> None:
    for spec in ("webhook:https://h/x", "webhook:http://h/x", "slack:https://h/x"):
        assert parse_notify_spec(spec).target.startswith("http")


def test_the_opened_value_is_the_checked_value() -> None:
    # A control character in the scheme position is read one way by urlsplit and another by
    # urllib; the check must use the reading that opens.
    for url in ("\nfile:///etc/hostname", " file:///etc/hostname"):
        with pytest.raises(_outbound.OutboundRefused):
            _outbound.open_url(url, purpose="notify_webhook")


@pytest.fixture
def servers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict]:
    hits: list[str] = []
    state: dict = {"hits": hits}

    class Handler(http.server.BaseHTTPRequestHandler):
        def _answer(self) -> None:
            hits.append(self.path)
            if self.path.startswith("/to/"):
                self.send_response(302)
                self.send_header("Location", state["targets"][self.path[4:]])
                self.send_header("Content-Length", "0")
            else:
                self.send_response(200)
                self.send_header("Content-Length", "2")
            self.end_headers()
            if not self.path.startswith("/to/"):
                self.wfile.write(b"ok")

        do_GET = do_POST = _answer

        def log_message(self, *args: object) -> None:
            pass

    plain = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    tls = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    loopback_tls.secure(tls, tmp_path, monkeypatch)
    http_base = f"http://127.0.0.1:{plain.server_port}"
    https_base = f"https://127.0.0.1:{tls.server_port}"
    state["targets"] = {
        "https": f"{https_base}/final",
        "http": f"{http_base}/final",
        "file": "file:///etc/hostname",
    }
    state.update(http=http_base, https=https_base)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (plain, tls)]
    for t in threads:
        t.start()
    yield state
    for s in (plain, tls):
        s.shutdown()
        s.server_close()


def _get(base: str, via: str, purpose: str):
    return _outbound.open_url(f"{base}/to/{via}", purpose=purpose, timeout=5)


@pytest.mark.parametrize("purpose", ["upgrade_document", "upgrade_artifact", "notify_slack"])
def test_https_hops_follow_https_and_refuse_the_rest(servers: dict, purpose: str) -> None:
    with _get(servers["https"], "https", purpose) as resp:
        assert resp.read() == b"ok"
    for target in ("http", "file"):
        servers["hits"].clear()
        with pytest.raises(_outbound.OutboundRefused) as info:
            _get(servers["https"], target, purpose)
        assert info.value.code == "url_redirect_refused"
        assert servers["hits"] == [f"/to/{target}"]
        _no_context(info.value)


def test_update_check_refuses_every_redirect(servers: dict) -> None:
    for target in ("https", "http"):
        servers["hits"].clear()
        with pytest.raises(urllib.error.HTTPError):
            _get(servers["https"], target, "update_check")
        assert servers["hits"] == [f"/to/{target}"]
    assert _outbound.RefuseRedirects.__module__ == "decoy._outbound"


def test_webhook_follows_allowed_hops_and_rechecks_each(servers: dict) -> None:
    for base in (servers["http"], servers["https"]):
        for via in ("http", "https"):
            with _get(base, via, "notify_webhook") as resp:
                assert resp.read() == b"ok"
    with pytest.raises(_outbound.OutboundRefused) as info:
        _get(servers["http"], "file", "notify_webhook")
    assert info.value.code == "url_redirect_refused"


@pytest.mark.parametrize(
    "endpoint, has_headers, message",
    [
        ("not a url", False, "OTEL: not a URL"),
        ("ftp://h/x", False, "OTEL: must be an http:// or https:// URL with a host"),
        ("https://", False, "OTEL: must be an http:// or https:// URL with a host"),
        ("https://u:p@h/x", False, "OTEL: must not carry credentials; use DECOY_OTEL_HEADERS"),
        ("https://h/x?a=1", False, "OTEL: must not carry a query string or fragment"),
        ("https://h/x#f", False, "OTEL: must not carry a query string or fragment"),
        ("https://h/x?", False, "OTEL: must not carry a query string or fragment"),
        (
            "http://h/x",
            True,
            "DECOY_OTEL_HEADERS needs an https:// OTEL (http only for a loopback host)",
        ),
        ("http://[::1", False, "OTEL: not a URL"),
    ],
)
def test_the_otel_purpose_refuses_what_validate_endpoint_refused(
    endpoint: str, has_headers: bool, message: str
) -> None:
    got = _outbound.otel_endpoint_problem(
        endpoint, has_headers=has_headers, setting="OTEL", headers_setting="DECOY_OTEL_HEADERS"
    )
    assert got == message
    with pytest.raises(
        OtelSettingsError, match="^" + message.replace("(", r"\(").replace(")", r"\)")
    ):
        validate_endpoint(endpoint, has_headers=has_headers, setting="OTEL")


@pytest.mark.parametrize(
    "endpoint, has_headers",
    [("https://h/x", True), ("http://127.0.0.1:4318/v1/traces", True), ("http://h/x", False)],
)
def test_the_otel_purpose_accepts_what_validate_endpoint_accepted(
    endpoint: str, has_headers: bool
) -> None:
    assert (
        _outbound.otel_endpoint_problem(
            endpoint, has_headers=has_headers, setting="OTEL", headers_setting="H"
        )
        is None
    )
    validate_endpoint(endpoint, has_headers=has_headers, setting="OTEL")
