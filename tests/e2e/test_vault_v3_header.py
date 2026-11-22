"""F09 CLI header slice: the authenticated `decoy-vault/v3` header as the CLI shows and enforces it.

Cells CV-1, CV-2, CV-3 and CV-6 of the F09 plan. A real `decoy run --vault` writes the vault;
the tamper cells edit the file the way an attacker with disk access could, and the CLI must
refuse it by name with a value-free message.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_RUNTIME, EXIT_USAGE
from tests.csv_sources import csv_source
from tests.keyed_secret import TEST_MASK_SECRET_BYTES, TEST_MASK_SECRET_REF

runner = CliRunner()

_MAGIC = b"DCYVAULT3\n"
_EMAIL = "u7@example.com"


def _pipeline(tmp_path: Path) -> Path:
    src = tmp_path / "in.csv"
    pd.DataFrame({"email": [f"u{i}@example.com" for i in range(30)]}).to_csv(src, index=False)
    cfg = {
        "version": 2,
        "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
        "sources": {"accounts": csv_source(src)},
        "tables": [
            {
                "name": "accounts",
                "columns": [
                    {"name": "email", "strategy": "hash", "namespace": "email_ns", "vault": True}
                ],
            }
        ],
        "targets": {
            "accounts": {"type": "file", "format": "csv", "path": str(tmp_path / "out.csv")}
        },
    }
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


@pytest.fixture()
def written(tmp_path: Path, mask_secret: str) -> tuple[Path, Path]:
    """The pipeline config and the vault a real run wrote."""
    cfg = _pipeline(tmp_path)
    vault = tmp_path / "vault.bin"
    result = runner.invoke(app, ["run", str(cfg), "--vault", str(vault)])
    assert result.exit_code == 0, result.output
    return cfg, vault


def _report(cfg: Path, vault: Path, *extra: str):
    return runner.invoke(app, ["report", "vault", str(vault), "--config", str(cfg), *extra])


def _header_json(blob: bytes) -> dict[str, object]:
    start = blob.index(b"{")
    return json.loads(blob[start : blob.index(b"}", start) + 1])


def test_run_writes_v3_and_unmask_recovers_it(written: tuple[Path, Path], tmp_path: Path) -> None:
    """CV-1: the file is a v3 vault and the one-way column comes back through it."""
    cfg, vault = written
    blob = vault.read_bytes()
    assert blob.startswith(_MAGIC)
    assert _header_json(blob)["format"] == "decoy-vault/v3"
    recovered = tmp_path / "recovered.csv"
    result = runner.invoke(
        app,
        [
            "unmask",
            str(cfg),
            str(tmp_path / "out.csv"),
            "--vault",
            str(vault),
            "-o",
            str(recovered),
        ],
    )
    assert result.exit_code == 0, result.output
    assert _EMAIL in recovered.read_text(encoding="utf-8").splitlines()


def test_report_shows_header_fields_and_no_secret_material(
    written: tuple[Path, Path],
) -> None:
    """CV-2: format, key version, short vault id and entry count; never the key check value."""
    cfg, vault = written
    header = _header_json(vault.read_bytes())
    result = _report(cfg, vault, "--json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload["format"] == "decoy-vault/v3"
    assert payload["key_version"] == header["key_version"]
    assert payload["entries"] == header["entry_count"] == 30
    shown_id = payload["vault_id"]
    assert 0 < len(shown_id) < len(str(header["vault_id"]))
    assert str(header["vault_id"]).startswith(shown_id)
    for text in (result.output, _report(cfg, vault).output):
        assert str(header["key_check"]) not in text
        assert str(header["vault_id"]) not in text
        assert TEST_MASK_SECRET_BYTES.hex() not in text
        assert _EMAIL not in text


def test_report_console_lists_the_header_fields(written: tuple[Path, Path]) -> None:
    cfg, vault = written
    flat = " ".join(_report(cfg, vault).output.split())
    for label in ("format: decoy-vault/v3", "key version:", "vault id:", "entries: 30"):
        assert label in flat, flat


def _flip_last_byte(blob: bytes) -> bytes:
    return blob[:-1] + bytes([blob[-1] ^ 0x01])


def _edit_header(blob: bytes) -> bytes:
    """Lower the `ambiguous_dropped` count in the cleartext header (11.8's example)."""
    assert b'"ambiguous_dropped":0' in blob
    return blob.replace(b'"ambiguous_dropped":0', b'"ambiguous_dropped":1', 1)


def _drop_tail(blob: bytes) -> bytes:
    return blob[:-40]


@pytest.mark.parametrize(
    "damage", [_flip_last_byte, _edit_header, _drop_tail], ids=["segment", "header", "truncated"]
)
def test_a_damaged_vault_is_refused_by_name(written: tuple[Path, Path], damage) -> None:
    """CV-3: report vault exits 3 with `vault_tampered`, as text and as a `--json` envelope."""
    cfg, vault = written
    vault.write_bytes(damage(vault.read_bytes()))
    text = _report(cfg, vault)
    assert text.exit_code == EXIT_RUNTIME, text.output
    assert "vault_tampered" in text.output
    assert "Traceback" not in text.output
    as_json = _report(cfg, vault, "--json")
    assert as_json.exit_code == EXIT_RUNTIME, as_json.output
    payload = json.loads(as_json.output.strip())
    assert payload["command"] == "report vault"
    assert payload["status"] == "error"
    assert payload["code"] == "vault_tampered"
    for out in (text.output, as_json.output):
        assert _EMAIL not in out
        assert TEST_MASK_SECRET_BYTES.hex() not in out


def test_unmask_refuses_a_tampered_vault_with_the_runtime_exit(
    written: tuple[Path, Path], tmp_path: Path
) -> None:
    cfg, vault = written
    vault.write_bytes(_flip_last_byte(vault.read_bytes()))
    recovered = tmp_path / "recovered.csv"
    result = runner.invoke(
        app,
        [
            "unmask",
            str(cfg),
            str(tmp_path / "out.csv"),
            "--vault",
            str(vault),
            "-o",
            str(recovered),
        ],
    )
    assert result.exit_code == EXIT_RUNTIME, result.output
    assert "vault_tampered" in result.output
    assert not recovered.exists()


def test_a_file_that_is_not_a_vault_stays_a_usage_error(
    written: tuple[Path, Path], tmp_path: Path
) -> None:
    """A bad magic is the caller's input, not a damaged vault: exit 1, not 3."""
    cfg, vault = written
    vault.write_bytes(b"NOTAVAULT\n" + vault.read_bytes()[len(_MAGIC) :])
    result = _report(cfg, vault)
    assert result.exit_code == EXIT_USAGE, result.output
    assert "vault_tampered" not in result.output


def test_run_refuses_an_existing_vault_and_leaves_it_alone(
    written: tuple[Path, Path], tmp_path: Path
) -> None:
    """CV-6: the existing v3 vault is never overwritten."""
    cfg, vault = written
    before = vault.read_bytes()
    result = runner.invoke(app, ["run", str(cfg), "--vault", str(vault)])
    assert result.exit_code == EXIT_USAGE, result.output
    assert "vault_exists" in result.output
    assert vault.read_bytes() == before
