"""AT-C2a1 and AT-C2a2: `decoy run` with `post_scan.integrity` writes the post-scan report.

The report lands beside the first target (`<target dir>/<config stem>.post-scan.json`) or at
`--integrity-out`, carries `config_sha256` (the SHA-256 of the YAML bytes `run` read), and a
rerun replaces it. The human card prints one post-scan line and `--json` gains `post_scan`.

Mutations: M-C2a1 (hash the `read_text()` output, so a CRLF file hashes as LF) turns the CRLF case
red; M-C2a2 (write the report create-once) turns both rerun tests red.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.e2e.integrity._fixtures import default_report, sha256, write_pipeline

runner = CliRunner()
REGEX_ONLY = {"integrity": True}


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_report_is_written_beside_the_first_target_with_the_bytes_hash(
    tmp_path: Path, newline: str
) -> None:
    cfg = write_pipeline(tmp_path, post=REGEX_ONLY, newline=newline, relative=True)
    data = cfg.read_bytes()
    if newline == "\r\n":
        # Non-vacuity: the CRLF case tells a byte hash from a hash of decoded text.
        assert sha256(data) != sha256(cfg.read_text(encoding="utf-8").encode("utf-8"))

    result = runner.invoke(app, ["run", str(cfg)])

    assert result.exit_code == 0, result.output
    (first,) = (tmp_path / "out").rglob("masked/customers.csv")
    (second,) = (tmp_path / "out").rglob("other/orders.csv")
    report_path = first.parent / "pipeline.post-scan.json"
    assert report_path.is_file()
    assert not (second.parent / "pipeline.post-scan.json").exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["config_sha256"] == sha256(data)
    assert report["tables_checked"] == ["customers", "orders"]
    text = " ".join(result.stdout.split())
    assert "Post-scan: regex. 0 warnings, 0 fail. Report:" in text
    assert "pipeline.post-scan.json" in text


def test_json_carries_the_post_scan_block(tmp_path: Path) -> None:
    cfg = write_pipeline(tmp_path, post=REGEX_ONLY)

    result = runner.invoke(app, ["run", str(cfg), "--json"])

    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    report_path = default_report(tmp_path)
    assert doc["post_scan"] == {
        "detectors": [{"source": "regex", "model_id": None, "model_version": None}],
        "counts": {"pass": 4, "warning": 0, "fail": 0, "error": 0},
        "report": str(report_path.resolve()),
    }


def test_no_report_and_no_block_without_integrity(tmp_path: Path) -> None:
    cfg = write_pipeline(tmp_path)

    result = runner.invoke(app, ["run", str(cfg), "--json"])

    assert result.exit_code == 0, result.output
    assert "post_scan" not in json.loads(result.stdout)
    assert not default_report(tmp_path).exists()


def test_integrity_out_is_honored_and_a_rerun_replaces_the_report(tmp_path: Path) -> None:
    cfg = write_pipeline(tmp_path, post=REGEX_ONLY)
    chosen = tmp_path / "reports" / "scan.json"
    chosen.parent.mkdir()

    first = runner.invoke(app, ["run", str(cfg), "--integrity-out", str(chosen)])
    assert first.exit_code == 0, first.output
    before = json.loads(chosen.read_text(encoding="utf-8"))
    second = runner.invoke(app, ["run", str(cfg), "--integrity-out", str(chosen)])

    assert second.exit_code == 0, second.output
    after = json.loads(chosen.read_text(encoding="utf-8"))
    assert after["generated_at"] != before["generated_at"]
    assert after["config_sha256"] == sha256(cfg.read_bytes())
    assert not default_report(tmp_path).exists()


def test_a_rerun_replaces_the_default_report(tmp_path: Path) -> None:
    cfg = write_pipeline(tmp_path, post=REGEX_ONLY)
    stamps = []
    for _ in range(2):
        result = runner.invoke(app, ["run", str(cfg)])
        assert result.exit_code == 0, result.output
        stamps.append(json.loads(default_report(tmp_path).read_text("utf-8"))["generated_at"])
    assert stamps[0] != stamps[1]


def test_a_report_that_cannot_be_written_exits_3_after_the_outputs(tmp_path: Path) -> None:
    cfg = write_pipeline(tmp_path, post=REGEX_ONLY)
    blocked = tmp_path / "reports"
    blocked.mkdir()
    chosen = blocked / "dir-in-the-way"
    chosen.mkdir()

    result = runner.invoke(app, ["run", str(cfg), "--integrity-out", str(chosen), "--json"])

    assert result.exit_code == 3, result.output
    doc = json.loads(result.stdout)
    assert doc["code"] == "run.integrity_write_failed"
    assert str(chosen) in doc["error"]
    assert (tmp_path / "masked" / "customers.csv").is_file()


def test_the_report_is_written_before_the_evidence_manifest(tmp_path: Path) -> None:
    from unittest import mock

    from decoy.cli.run import _evidence, _flow

    cfg = write_pipeline(tmp_path, post=REGEX_ONLY)
    order: list[str] = []
    real_report, real_evidence = _flow.write_run_report, _evidence.write_evidence

    def report(*args, **kwargs):
        order.append("report")
        return real_report(*args, **kwargs)

    def evidence(*args, **kwargs):
        order.append("evidence")
        return real_evidence(*args, **kwargs)

    with (
        mock.patch.object(_flow, "write_run_report", report),
        mock.patch.object(_evidence, "write_evidence", evidence),
    ):
        result = runner.invoke(app, ["run", str(cfg), "--evidence-out", str(tmp_path / "ev.json")])

    assert result.exit_code == 0, result.output
    assert order == ["report", "evidence"]


@pytest.mark.parametrize("clash", ["target", "evidence"])
def test_integrity_out_joins_the_typed_collision_rule(tmp_path: Path, clash: str) -> None:
    cfg = write_pipeline(tmp_path, post=REGEX_ONLY)
    same = tmp_path / "masked" / "customers.csv" if clash == "target" else tmp_path / "same.json"
    args = ["run", str(cfg), "--integrity-out", str(same)]
    if clash == "evidence":
        args += ["--evidence-out", str(same)]

    result = runner.invoke(app, args)

    assert result.exit_code == 1, result.output
    assert not default_report(tmp_path).exists()
