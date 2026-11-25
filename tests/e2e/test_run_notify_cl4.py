"""CL4 (24zf): the notify channel failures carry no exception text, and a bad SMTP port fails
only the email channel (AT-2, G4, G5b, and the transport half of AT-16)."""

from __future__ import annotations

import json
import logging
import urllib.error
from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.e2e.test_run_error_arms import _config

runner = CliRunner()
WEBHOOK = "https://hookuser:HOOKPASS@hooks.example.com:8443/x"
SLACK = "https://hooks.slack.example.com/services/T0/B0/SLACKTOKEN"
PORT_MESSAGE = "DECOY_NOTIFY_SMTP_PORT must be a whole number."


@pytest.fixture(autouse=True)
def _smtp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HOST", "FROM", "USER", "PASS", "PORT"):
        monkeypatch.delenv(f"DECOY_NOTIFY_SMTP_{name}", raising=False)


@pytest.mark.parametrize("flags", [(), ("--json",)])
def test_a_bad_smtp_port_fails_only_the_email_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, flags
) -> None:
    monkeypatch.setenv("DECOY_NOTIFY_SMTP_PORT", "abc")
    monkeypatch.setenv("DECOY_NOTIFY_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("DECOY_NOTIFY_SMTP_FROM", "decoy@example.com")
    sent: list[str] = []

    def webhook(url, event, *, secret_key=None):
        sent.append(url)
        return True, None

    cfg = _config(tmp_path)
    caplog.set_level(logging.DEBUG)
    with mock.patch("decoy.notify.send_webhook", webhook):
        result = runner.invoke(
            app,
            [
                "run", str(cfg), "--notify", f"webhook:{WEBHOOK}", "--notify",
                "email:ops@example.com", "--notify-on", "always", *flags,
            ],
        )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert sent == [WEBHOOK]
    everything = result.stdout + result.stderr + caplog.text
    for secret in ("abc", "hookuser", "HOOKPASS"):
        assert secret not in everything.replace("abcdef", "")
    if "--json" in flags:
        doc = json.loads(result.stdout.strip().splitlines()[-1])
        hosts = {n["kind"]: n["target_host"] for n in doc["notify"]}
        assert hosts["webhook"] == "hooks.example.com:8443"
    else:
        assert f"did not deliver: {PORT_MESSAGE}" in result.stderr
        assert "notify email to ***@example.com" in result.stderr


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://u:p@hooks.example.com:8443/x", "hooks.example.com:8443"),
        ("https://u:p@hooks.example.com/x", "hooks.example.com"),
        ("https://hooks.example.com/x", "hooks.example.com"),
        ("https://u:p@[::1]:9000/x", "[::1]:9000"),
        ("https://hooks.example.com:notaport/x", "(unknown host)"),
    ],
)
def test_host_only_drops_userinfo(url: str, expected: str) -> None:
    from decoy.notify import _host_only

    assert _host_only(url) == expected


def test_smtp_config_carries_the_port_problem_and_email_reports_it_first() -> None:
    from decoy.notify import SmtpConfig, send_email

    smtp = SmtpConfig(host="", problem=PORT_MESSAGE)  # not configured, and a problem
    assert send_email("ops@example.com", {}, smtp=smtp) == (False, PORT_MESSAGE)


# AT-16 transport: an exception text never reaches a warning or a result.
CANARY = "HOOKPASS-CANARY-42"


def _warnings(result, caplog) -> str:
    return result.stdout + result.stderr + caplog.text


def _run_with_failure(tmp_path, caplog, patch_target, side_effect, spec, *flags):
    cfg = _config(tmp_path)
    caplog.set_level(logging.DEBUG)
    with mock.patch(patch_target, side_effect=side_effect) as patched:
        result = runner.invoke(
            app, ["run", str(cfg), "--notify", spec, "--notify-on", "always", *flags]
        )
    assert patched.called
    return result


@pytest.mark.parametrize("flags", [(), ("--quiet",), ("--json",)])
@pytest.mark.parametrize(
    ("target", "effect", "spec"),
    [
        ("decoy.notify._outbound.open_url", ValueError(CANARY), f"webhook:{WEBHOOK}"),
        (
            "decoy.notify._outbound.open_url",
            urllib.error.URLError(CANARY),
            f"webhook:{WEBHOOK}",
        ),
        ("decoy.notify._outbound.open_url", urllib.error.URLError(CANARY), f"slack:{SLACK}"),
        ("decoy.notify.send_webhook", RuntimeError(CANARY), f"webhook:{WEBHOOK}"),
    ],
)
def test_a_failed_delivery_never_shows_the_exception_text(
    tmp_path, caplog, flags, target, effect, spec, monkeypatch
) -> None:
    monkeypatch.setattr("decoy.notify._WEBHOOK_BACKOFF_BASE_SECS", 0)
    monkeypatch.setattr("decoy.notify._WEBHOOK_MAX_BACKOFF_SECS", 0)
    result = _run_with_failure(tmp_path, caplog, target, effect, spec, *flags)

    assert result.exit_code == 0, result.output
    assert CANARY not in _warnings(result, caplog)


@pytest.mark.parametrize("flags", [(), ("--quiet",), ("--json",)])
def test_an_smtp_failure_never_shows_the_exception_text(
    tmp_path, caplog, flags, monkeypatch
) -> None:
    monkeypatch.setenv("DECOY_NOTIFY_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("DECOY_NOTIFY_SMTP_FROM", "decoy@example.com")
    result = _run_with_failure(
        tmp_path, caplog, "decoy.notify.smtplib.SMTP", OSError(CANARY), "email:ops@example.com",
        *flags,
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert CANARY not in _warnings(result, caplog)


@pytest.mark.parametrize("flags", [(), ("--quiet",), ("--json",)])
def test_a_failed_dispatch_never_shows_the_exception_text(tmp_path, caplog, flags) -> None:
    result = _run_with_failure(
        tmp_path, caplog, "decoy.notify.dispatch", RuntimeError(CANARY), f"webhook:{WEBHOOK}",
        *flags,
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert CANARY not in _warnings(result, caplog)
