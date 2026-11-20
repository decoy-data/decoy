"""AT-S6b: `decoy upgrade --url` with a scheme the purpose does not allow."""

from __future__ import annotations

import json
import socket
import urllib.request

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_USAGE


def test_a_refused_scheme_exits_1_with_no_socket_and_no_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def trap(*args: object, **kwargs: object) -> None:
        raise AssertionError("a socket or opener was used")

    monkeypatch.setattr(socket.socket, "connect", trap)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", trap)
    url = "ftp://user:SECRETPW@files.example.com/v.json?k=QUERYVAL"
    result = CliRunner().invoke(app, ["upgrade", "--url", url, "--json"])
    assert result.exit_code == EXIT_USAGE, result.output
    payload = json.loads(result.stdout)
    assert payload["code"] == "url_scheme_refused"
    for part in ("SECRETPW", "QUERYVAL", "files.example.com", "v.json"):
        assert part not in result.stdout + result.stderr


@pytest.mark.parametrize("failure", ["refused", "unreachable"])
def test_a_fetch_failure_leaves_no_exception_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path, failure: str
) -> None:
    """Defect class 3: the refusal is raised outside the `except`, so nothing carries the URL."""
    import typer

    from decoy import _outbound
    from decoy.cli import upgrade as upg

    def fetch(url: str, purpose: str = "upgrade_artifact") -> bytes:
        if failure == "refused":
            raise _outbound.OutboundRefused("url_redirect_refused", "upgrade_document", "http")
        raise OSError("boom https://u:SECRETPW@h/x")

    monkeypatch.setattr(upg, "_managed_home", lambda: tmp_path / "home")
    monkeypatch.setattr(upg.release_key, "pinned_public_pem", lambda: "PUB")
    monkeypatch.setattr(upg, "_fetch", fetch)
    with pytest.raises(typer.Exit) as info:
        upg.upgrade(
            version=None,
            check=False,
            force=False,
            url="https://h/v.json",
            json_=False,
            quiet=True,
            verbose=False,
        )
    assert info.value.exit_code == 3
    assert info.value.__cause__ is None and info.value.__context__ is None
