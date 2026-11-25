"""A credential in a file source `path` never reaches a preflight finding (both routes)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_USAGE
from decoy.cli.io import redact_urls
from tests.csv_sources import csv_source

runner = CliRunner()
CANARY = "PW-CANARY-7f3a"
URL = f"https://user:{CANARY}@example.invalid/data/in.csv?token={CANARY}#frag"


def _config(tmp_path: Path, path: str) -> Path:
    cfg = {
        "version": 2,
        "global_settings": {"seed": 1},
        "sources": {"a": {**csv_source(tmp_path / "unused.csv"), "path": path}},
        "tables": [{"name": "a", "columns": [{"name": "email", "strategy": "redact"}]}],
        "targets": {"a": {"type": "file", "format": "csv", "path": "out.csv"}},
    }
    p = tmp_path / "pipeline.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return p


@pytest.mark.parametrize("command", [["validate", "preflight"], ["validate"]])
@pytest.mark.parametrize("flags", [[], ["--json"]])
def test_a_url_credential_is_not_printed(tmp_path: Path, command: list[str], flags: list[str]):
    result = runner.invoke(app, [*command, str(_config(tmp_path, URL)), *flags])
    text = result.output + (getattr(result, "stderr", "") or "")
    assert result.exit_code == EXIT_USAGE, text
    assert CANARY not in text
    assert "token=" not in text
    assert "example.invalid" in text


@pytest.mark.parametrize("command", [["validate", "preflight"], ["validate"]])
def test_a_plain_missing_file_keeps_its_name(tmp_path: Path, command: list[str]):
    result = runner.invoke(app, [*command, str(_config(tmp_path, "missing-input.csv"))])
    assert result.exit_code == EXIT_USAGE
    assert "missing-input.csv" in result.output + (getattr(result, "stderr", "") or "")


def test_redact_urls_cases() -> None:
    assert redact_urls("data/in.csv") == "data/in.csv"
    assert redact_urls(f"s3://u:{CANARY}@bucket:9000/k.csv?x=1") == "s3://bucket:9000/k.csv"
    assert redact_urls(f"[Errno 2] No such file: '{URL}'") == (
        "[Errno 2] No such file: 'https://example.invalid/data/in.csv'"
    )
    assert CANARY not in redact_urls("http://u:p@[::1]:99999999/x")
