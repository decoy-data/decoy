"""A credential in a recorded path never reaches evidence output (PROP-SHIMS D6 review rounds).

A legacy manifest can hold a URL or a `//user:pass@host/...` reference as a path. Every reader
shows the safe location from `decoy.safe_url.redacted_location`, and the writer records only that.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.evidence import build_manifest, compute_manifest_hash
from decoy.cli.exit_codes import EXIT_USAGE
from decoy.cli.io import LayoutError
from tests.e2e.cli_fmt.test_target_format_readers import _diff, _manifest, _write_manifest

pytestmark = pytest.mark.usefixtures("mask_secret")
runner = CliRunner()

_PASSWORD = "SENTINEL-pw-7f3a"
_TOKEN = "SENTINEL-tok-91c2"
_URL = f"https://svc:{_PASSWORD}@files.example.com/out.csv?token={_TOKEN}"
_NETWORK_PATH = f"//svc:{_PASSWORD}@files.example.com/private?token={_TOKEN}"


@pytest.mark.parametrize("paired", [False, True], ids=["one_sided", "paired"])
def test_report_diff_never_echoes_a_credential_bearing_url(tmp_path: Path, paired: bool) -> None:
    base = _manifest(tmp_path, "a", tmp_path / "unused.csv", "csv")
    # A legacy entry: a URL path, a null fingerprint (the key stays), no format or layout.
    with_url = _write_manifest(
        tmp_path / "with_url.json", base, path=_URL, format=None, layout=None
    )
    legacy = json.loads(with_url.read_text(encoding="utf-8"))
    legacy["output_fingerprints"]["t"]["fingerprint"] = None
    legacy["manifest_hash"] = compute_manifest_hash(legacy)
    with_url.write_text(json.dumps(legacy), encoding="utf-8")
    if paired:
        other = with_url
    else:
        bare = copy.deepcopy(base)
        bare["output_fingerprints"] = {}
        bare["manifest_hash"] = compute_manifest_hash(bare)
        other = tmp_path / "bare.json"
        other.write_text(json.dumps(bare), encoding="utf-8")
    args = [str(with_url), str(other)]

    soft_json = _diff(*args)
    strict_json = _diff(*args, "--require-data")
    soft_human = runner.invoke(app, ["report", "diff", *args])
    strict_human = runner.invoke(app, ["report", "diff", *args, "--require-data"])
    assert soft_json.exit_code == 0, soft_json.output
    assert soft_human.exit_code == 0, soft_human.output
    assert strict_json.exit_code == EXIT_USAGE, strict_json.output
    assert strict_human.exit_code == EXIT_USAGE, strict_human.output
    payload = json.loads(soft_json.stdout)
    assert payload["data_level"] == "skipped"
    assert payload["missing_files"], "the skipped entry is still named"
    for result in (soft_json, strict_json, soft_human, strict_human):
        assert _PASSWORD not in result.output
        assert _TOKEN not in result.output
        assert "files.example.com" in result.output


def _legacy_url_manifest(tmp_path: Path) -> Path:
    """A legacy manifest whose output and input entries hold the credential-bearing URL."""
    base = _manifest(tmp_path, "a", tmp_path / "unused.csv", "csv")
    legacy = copy.deepcopy(base)
    legacy["output_fingerprints"]["t"] = {"path": _URL, "fingerprint": None}
    legacy["input_fingerprints"] = {
        "s": {"path": _URL, "fingerprint": None},
        "n": {"path": _NETWORK_PATH, "fingerprint": None},
    }
    legacy["pipeline_path"] = _URL
    legacy["manifest_hash"] = compute_manifest_hash(legacy)
    out = tmp_path / "legacy_url.json"
    out.write_text(json.dumps(legacy), encoding="utf-8")
    return out


def _assert_no_sentinel(text: str) -> None:
    assert _PASSWORD not in text
    assert _TOKEN not in text
    assert "svc:" not in text


def test_report_show_never_echoes_a_credential_bearing_url(tmp_path: Path) -> None:
    ev = _legacy_url_manifest(tmp_path)
    outputs = []
    for args in (["show", str(ev)], ["show", str(ev), "--json"]):
        result = runner.invoke(app, ["report", *args], env={"COLUMNS": "10000"})
        assert result.exit_code == 0, result.output
        assert "files.example.com" in result.output
        outputs.append(result.output)
    for fmt, name in (("html", "r.html"), ("markdown", "r.md")):
        written = tmp_path / name
        for cmd in ("show", "render"):
            result = runner.invoke(
                app, ["report", cmd, str(ev), "--format", fmt, "--output", str(written)]
            )
            assert result.exit_code == 0, result.output
            outputs.append(result.output)
            outputs.append(written.read_text(encoding="utf-8"))
            assert "files.example.com" in outputs[-1]
    for text in outputs:
        _assert_no_sentinel(text)


def test_report_show_card_displays_exactly_what_the_redaction_helper_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A stand-in helper tags every path it is given. The card shows a tag only for the paths
    # it took from the helper, so a card that picks its own fields to redact misses one.
    ev = _legacy_url_manifest(tmp_path)

    def tagged(manifest: dict[str, Any]) -> dict[str, Any]:
        shown = copy.deepcopy(manifest)
        for group in ("input_fingerprints", "output_fingerprints"):
            for name, info in shown[group].items():
                info["path"] = f"HELPER-{group}-{name}"
        return shown

    monkeypatch.setattr("decoy.cli.evidence.redact_manifest_paths", tagged)
    result = runner.invoke(app, ["report", "show", str(ev)], env={"COLUMNS": "10000"})
    assert result.exit_code == 0, result.output
    assert "HELPER-input_fingerprints-s" in result.output
    assert "HELPER-output_fingerprints-t" in result.output


@pytest.mark.parametrize("cmd", ["show", "render"])
@pytest.mark.parametrize("fmt", ["html", "markdown"])
def test_written_reports_display_exactly_what_the_redaction_helper_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cmd: str, fmt: str
) -> None:
    # Same stand-in as the card test: a renderer that selects its own fields to redact, or is
    # handed the original manifest, shows the raw path instead of the tag.
    ev = _legacy_url_manifest(tmp_path)

    def tagged(manifest: dict[str, Any]) -> dict[str, Any]:
        shown = copy.deepcopy(manifest)
        for group in ("input_fingerprints", "output_fingerprints"):
            for name, info in shown[group].items():
                info["path"] = f"HELPER-{group}-{name}"
        return shown

    monkeypatch.setattr("decoy.cli.evidence.redact_manifest_paths", tagged)
    written = tmp_path / "report.out"
    result = runner.invoke(app, ["report", cmd, str(ev), "--format", fmt, "--output", str(written)])
    assert result.exit_code == 0, result.output
    text = written.read_text(encoding="utf-8")
    assert "HELPER-input_fingerprints-s" in text
    assert "HELPER-output_fingerprints-t" in text


@pytest.mark.parametrize("target", [_URL, "https://svc:" + _PASSWORD + "@host/o.csv"])
def test_a_placement_failure_does_not_record_the_raw_target(tmp_path: Path, target: str) -> None:
    def refuse(_raw: str) -> Path:
        raise LayoutError("target_refused", "the layout refused the target")

    pipeline = tmp_path / "pipeline.yaml"
    pipeline.write_text("version: 2\n", encoding="utf-8")
    config = {
        "sources": {"s": {"type": "s3", "path": target}},
        "targets": {"t": {"type": "file", "format": "csv", "path": target}},
    }
    manifest = build_manifest(
        pipeline_path=pipeline,
        config_dict=config,
        run_result={"row_counts": {"t": 2}},
        cli_version="0",
        engine_version="0",
        place_target=refuse,
    )
    _assert_no_sentinel(json.dumps(manifest))
    assert manifest["manifest_hash"] == compute_manifest_hash(manifest)


# ---------------------------------------------------------------------------
# Class guard: a sentinel in every path field appears in no output
# ---------------------------------------------------------------------------


def _every_path_manifest(tmp_path: Path, project: bool) -> Path:
    """A manifest written by `build_manifest` from config paths that all hold the sentinel,
    then given a credentialed `pipeline_path` the way a legacy file would have it."""
    pipeline = tmp_path / "pipeline.yaml"
    pipeline.write_text("version: 2\n", encoding="utf-8")
    if project:
        (tmp_path / "decoy.yaml").write_text("kind: decoy-project/v1\n", encoding="utf-8")
    config = {
        "sources": {"s": {"type": "s3", "path": _URL}, "n": {"type": "s3", "path": _NETWORK_PATH}},
        "targets": {
            "t": {"type": "file", "format": "csv", "path": _NETWORK_PATH},
            "u": {"type": "file", "format": "csv", "path": _URL},
        },
    }
    manifest = build_manifest(
        pipeline_path=pipeline,
        config_dict=config,
        run_result={"row_counts": {"t": 1, "u": 1}},
        cli_version="0",
        engine_version="0",
        project_root=tmp_path if project else None,
        evidence_path=tmp_path / "evidence.json" if project else None,
    )
    (tmp_path / "written.json").write_text(json.dumps(manifest), encoding="utf-8")
    legacy = copy.deepcopy(manifest)
    if not project:  # a project manifest records the pipeline as a relative path
        legacy["pipeline_path"] = _URL
    legacy["manifest_hash"] = compute_manifest_hash(legacy)
    out = tmp_path / "evidence.json"
    out.write_text(json.dumps(legacy), encoding="utf-8")
    return out


@pytest.mark.parametrize("project", [False, True], ids=["no_project", "marked_project"])
def test_no_output_carries_a_credential_from_any_path_field(tmp_path: Path, project: bool) -> None:
    ev = _every_path_manifest(tmp_path, project)
    written = (tmp_path / "written.json").read_text(encoding="utf-8")
    assert _PASSWORD not in written
    assert _TOKEN not in written
    outputs = []
    commands = [
        ["report", "show", str(ev)],
        ["report", "show", str(ev), "--json"],
        ["report", "diff", str(ev), str(ev)],
        ["report", "diff", str(ev), str(ev), "--json"],
        ["report", "verify", str(ev)],
        ["report", "verify", str(ev), "--json"],
    ]
    if project:
        commands = [[*c, "--project", str(tmp_path)] if c[1] == "verify" else c for c in commands]
    for args in commands:
        result = runner.invoke(app, args, env={"COLUMNS": "10000"})
        outputs.append(result.output)
    for fmt, name in (("html", "r.html"), ("markdown", "r.md")):
        dest = tmp_path / name
        for cmd in ("show", "render"):
            runner.invoke(app, ["report", cmd, str(ev), "--format", fmt, "--output", str(dest)])
            outputs.append(dest.read_text(encoding="utf-8") if dest.exists() else "")
    for text in outputs:
        _assert_no_sentinel(text)
    assert any("files.example.com" in text for text in outputs)
