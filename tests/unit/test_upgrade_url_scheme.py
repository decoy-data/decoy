"""AT-S6b: `decoy upgrade --url` with a scheme the purpose does not allow."""

from __future__ import annotations

import json
import socket
import urllib.request

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_USAGE


def test_a_refused_scheme_exits_1_with_no_socket_and_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
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
