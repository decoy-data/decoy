"""AT-C2a3 and AT-C2a4: a run an NER finding blocks publishes nothing and still writes its report.

`decoy run` handles `PostScanBlockedError` as a branch of its one error handler: exit 4, the
report written, no target, no vault, no evidence manifest, the failure notification with the
type name only, and the registry's fixed summary (never `str(error)`) on the terminal and in the
`--json` envelope, which also carries `code: post_scan.ner_blocked`, the report path and counts.
`decoy.mask()` raises the same error and writes no target.

The matrix runs in-process with the engine call raising a real `PostScanBlockedError`; the
`real_model` tests run the whole path with spaCy in a fresh venv.

Mutations: M-C2a3 (commit the vault before the engine verdict), M-C2a3b (raise `typer.Exit(4)`
inside the `try`, so the notification and envelope are skipped), M-C2a3c (leave the generic
`error_text` unchanged), M-C2a4 (catch the error in `api.py` and write anyway).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.e2e.first_user.test_items_error_envelope import SCHEMA
from tests.e2e.integrity._fixtures import (
    CANARY,
    blocked_error,
    default_report,
    sha256,
    write_pipeline,
)
from tests.e2e.models._venvs import child_env, run_cli
from tests.keyed_secret import secret_env

runner = CliRunner()
NER_FAIL = {"integrity": True, "detectors": ["regex", "ner"], "ner_findings": "fail"}
SUMMARY = "An NER post-scan finding blocked this run under ner_findings: fail"
WEBHOOK = "webhook:https://hooks.example.invalid/decoy"


def _summary() -> str:
    from decoy_engine import reasons

    return reasons.get("post_scan", "ner_blocked").summary


def _blocked_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *flags: str):
    """`decoy run` whose engine call raises a blocked error with a canary as its text."""
    pytest.importorskip("cryptography")
    for name, value in secret_env().items():
        monkeypatch.setenv(name, value)
    cfg = write_pipeline(tmp_path, vault=True, notes=True)
    sent: list[dict] = []

    def webhook(url, event, *, secret_key=None):
        sent.append(event)
        return True, "200"

    args = ["run", str(cfg), "--vault", str(tmp_path / "vault.bin")]
    args += ["--evidence-out", str(tmp_path / "evidence.json"), "--notify", WEBHOOK, *flags]
    with (
        mock.patch("decoy_engine.run_pipeline", side_effect=blocked_error(leak=CANARY)),
        mock.patch("decoy.notify.send_webhook", webhook),
    ):
        result = runner.invoke(app, args)
    return cfg, result, sent


def _nothing_published(tmp_path: Path) -> None:
    assert not (tmp_path / "masked" / "customers.csv").exists()
    assert not (tmp_path / "masked" / "orders.csv").exists()
    assert not (tmp_path / "vault.bin").exists()
    assert not (tmp_path / "evidence.json").exists()


def test_blocked_run_exits_4_writes_the_report_and_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, result, sent = _blocked_run(tmp_path, monkeypatch)

    assert result.exit_code == 4, result.output
    _nothing_published(tmp_path)
    report = json.loads(default_report(tmp_path).read_text(encoding="utf-8"))
    assert report["config_sha256"] == sha256(cfg.read_bytes())
    assert [f["severity"] for f in report["residual_pii"]] == ["fail"]
    assert len(sent) == 1
    assert sent[0]["status"] == "failure"
    assert sent[0]["detail"].endswith(" - PostScanBlockedError")
    assert CANARY not in json.dumps(sent)


def test_blocked_run_prints_the_fixed_summary_never_the_error_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, result, _ = _blocked_run(tmp_path, monkeypatch)

    assert result.exit_code == 4, result.output
    text = " ".join(result.output.split())
    assert _summary() in text
    assert CANARY not in result.output
    assert "Post-scan: regex; ner en_core_web_sm 3.8.0. 0 warnings, 1 fail. Report:" in text


def test_blocked_json_envelope_carries_code_report_and_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    _, result, sent = _blocked_run(tmp_path, monkeypatch, "--json")

    assert result.exit_code == 4, result.output
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1, result.stdout
    doc = json.loads(lines[0])
    jsonschema.validate(doc, SCHEMA)
    assert doc["status"] == "error"
    assert doc["error"] == _summary()
    assert doc["error_kind"] == "post_scan_blocked"
    assert doc["code"] == "post_scan.ner_blocked"
    assert list(doc)[:4] == ["command", "status", "error", "code"]
    assert doc["post_scan"] == {
        "detectors": [
            {"source": "regex", "model_id": None, "model_version": None},
            {"source": "ner", "model_id": "en_core_web_sm", "model_version": "3.8.0"},
        ],
        "counts": {"pass": 3, "warning": 0, "fail": 1, "error": 0},
        "report": str(default_report(tmp_path).resolve()),
    }
    assert CANARY not in result.stdout
    assert "residual_pii" not in result.stdout
    assert "outputs" not in doc
    assert len(sent) == 1
    _nothing_published(tmp_path)


def test_blocked_run_writes_the_report_in_the_run_folder_it_never_published_to(
    tmp_path: Path,
) -> None:
    cfg = write_pipeline(tmp_path, notes=True, relative=True)
    with mock.patch("decoy_engine.run_pipeline", side_effect=blocked_error()):
        result = runner.invoke(app, ["run", str(cfg), "--json"])

    assert result.exit_code == 4, result.output
    (report,) = (tmp_path / "out").rglob("masked/pipeline.post-scan.json")
    assert json.loads(result.stdout)["post_scan"]["report"] == str(report.resolve())
    assert list((tmp_path / "out").rglob("*.csv")) == []


def test_mask_api_raises_the_block_and_writes_no_target(tmp_path: Path) -> None:
    from decoy_engine import PostScanBlockedError

    import decoy

    cfg = write_pipeline(tmp_path, notes=True)
    with (
        mock.patch("decoy_engine.run_pipeline", side_effect=blocked_error()),
        pytest.raises(PostScanBlockedError),
    ):
        decoy.mask(config=str(cfg))
    assert not (tmp_path / "masked" / "customers.csv").exists()
    assert not (tmp_path / "masked" / "orders.csv").exists()


# --- the whole path with the real model --------------------------------------------------------


@pytest.mark.timeout(1200)
def test_real_model_blocked_run(tmp_path: Path, ner_python: Path) -> None:
    cfg = write_pipeline(tmp_path, post=NER_FAIL, notes=True)

    proc = run_cli(ner_python, ["run", str(cfg), "--json"], tmp_path, child_env())

    assert proc.returncode == 4, proc.stdout[-2000:] + proc.stderr[-2000:]
    doc = json.loads(proc.stdout)
    assert doc["code"] == "post_scan.ner_blocked"
    assert doc["error"].startswith(SUMMARY)
    assert doc["post_scan"]["counts"]["fail"] == 1
    report = json.loads(default_report(tmp_path).read_text(encoding="utf-8"))
    assert report["config_sha256"] == sha256(cfg.read_bytes())
    ner = [f for f in report["residual_pii"] if f["source"] == "ner"]
    assert [(f["column"], f["severity"], f["promoted"]) for f in ner] == [("notes", "fail", True)]
    blob = json.dumps(report) + proc.stdout + proc.stderr
    assert not any(name in blob for name in ("John Smith", "Mary Johnson"))
    assert not (tmp_path / "masked" / "customers.csv").exists()


@pytest.mark.timeout(1200)
def test_real_model_mask_api_raises_and_writes_nothing(tmp_path: Path, ner_python: Path) -> None:
    cfg = write_pipeline(tmp_path, post=NER_FAIL, notes=True)
    prelude = (
        "import sys, decoy\n"
        "from decoy_engine import PostScanBlockedError\n"
        f"try:\n    decoy.mask(config={str(cfg)!r})\n"
        "except PostScanBlockedError as e:\n    print('BLOCKED', e.code); sys.exit(0)\n"
        "sys.exit(7)\n"
    )

    proc = run_cli(ner_python, [], tmp_path, child_env(), prelude=prelude)

    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    assert "BLOCKED ner_blocked" in proc.stdout
    assert not (tmp_path / "masked" / "customers.csv").exists()


def test_blocked_run_stderr_carries_no_report_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _cfg, result, _sent = _blocked_run(tmp_path, monkeypatch)

    assert result.exit_code == 4, result.output
    assert CANARY not in result.output
    assert "tables_checked" not in result.stderr
    assert "schema_version" not in result.stderr
    assert "rerun with --verbose" not in result.stderr
