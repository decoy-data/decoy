"""Class guard: a credential planted in any path field or argument reaches no output.

Every recorded path field and every echoed argument gets its own sentinel. The reader fixture is a
legacy manifest written by hand (so it holds credentials the writer would never record), with real
fingerprints so `report verify` reads each entry. The writer fixture runs `build_manifest` over
every source kind in both project layouts. Each command must exit as expected, produce its file
fresh, and print no sentinel on stdout, stderr or in any file it wrote.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.evidence import build_manifest, compute_manifest_hash
from decoy.cli.exit_codes import EXIT_FINDINGS, EXIT_USAGE

pytestmark = pytest.mark.usefixtures("mask_secret")
runner = (
    CliRunner(mix_stderr=False)
    if "mix_stderr" in CliRunner.__init__.__code__.co_varnames
    else CliRunner()
)

_HOST = "files.example.com"
_FP = "sha256:" + "ab" * 32
_LONG = "L" * 300  # longer than a filesystem name: `exists()` raises ENAMETOOLONG


def _sentinel(field: str) -> str:
    return f"SENTINEL-{field}-pw"


def _sources() -> dict[str, str]:
    """Declared path per source kind, each with its own sentinel."""
    return {
        "file_url": f"https://svc:{_sentinel('file_url')}@{_HOST}/f.csv?token={_sentinel('file_url_q')}",
        "s3": f"s3://svc:{_sentinel('s3')}@bucket/key.csv",
        "net_user": f"//svc:{_sentinel('net_user')}@{_HOST}/share/f.csv",
        "net_query": f"//{_HOST}/f.csv?access_token={_sentinel('net_query')}",
    }


def _legacy_manifest(tmp_path: Path) -> Path:
    entries: dict[str, Any] = {
        name: {"path": raw, "fingerprint": _FP, "fingerprint_method": "full", "size_bytes": 1}
        for name, raw in _sources().items()
    }
    entries["long"] = {
        "path": f"//svc:{_LONG}{_sentinel('long')}@{_HOST}/f.csv",
        "fingerprint": _FP,
        "fingerprint_method": "full",
        "size_bytes": 1,
    }
    outputs = {
        "t": {
            "path": f"//svc:{_sentinel('target')}@{_HOST}/out.csv",
            "fingerprint": _FP,
            "fingerprint_method": "full",
            "size_bytes": 1,
            "format": "csv",
        },
        "u": {
            "path": f"https://svc:{_sentinel('target_url')}@{_HOST}/o.csv?t={_sentinel('tq')}",
            "fingerprint": _FP,
            "fingerprint_method": "full",
            "size_bytes": 1,
            "format": "csv",
        },
    }
    manifest: dict[str, Any] = {
        "schema_version": "cli-local-1",
        "producer": "decoy-cli",
        "project_manifest": f"//svc:{_sentinel('project_manifest')}@{_HOST}/e.json",
        "run_id": "r1",
        "run_timestamp": "2026-01-01T00:00:00+00:00",
        "cli_version": "0",
        "engine_version": "0",
        "pipeline_path": f"https://svc:{_sentinel('pipeline')}@{_HOST}/p.yaml?t={_sentinel('pq')}",
        "pipeline_fingerprint": _FP,
        "input_fingerprints": entries,
        "output_fingerprints": outputs,
        "row_counts": {"t": 1},
        "key_label": None,
        "warnings": [],
        "timings": [],
        "strategies": [],
        "manifest_hash": "",
    }
    manifest["manifest_hash"] = compute_manifest_hash(manifest)
    out = tmp_path / "legacy.json"
    out.write_text(json.dumps(manifest), encoding="utf-8")
    return out


def _written_manifest(tmp_path: Path, project: bool) -> Path:
    """`build_manifest` over every source kind, the file kind given as a URL too."""
    pipeline = tmp_path / "pipeline.yaml"
    pipeline.write_text("version: 2\n", encoding="utf-8")
    if project:
        (tmp_path / "decoy.yaml").write_text("kind: decoy-project/v1\n", encoding="utf-8")
    config = {
        "sources": {
            **{f"file_{k}": {"type": "file", "path": v} for k, v in _sources().items()},
            **{f"s3_{k}": {"type": "s3", "path": v} for k, v in _sources().items()},
        },
        "targets": {
            f"t_{k}": {"type": "file", "format": "csv", "path": v} for k, v in _sources().items()
        },
    }
    manifest = build_manifest(
        pipeline_path=pipeline,
        config_dict=config,
        run_result={"row_counts": {}},
        cli_version="0",
        engine_version="0",
        project_root=tmp_path if project else None,
        evidence_path=tmp_path / "written.json" if project else None,
    )
    out = tmp_path / "written.json"
    out.write_text(json.dumps(manifest), encoding="utf-8")
    return out


def _assert_clean(text: str, where: str) -> None:
    assert "SENTINEL" not in text, f"a credential reached {where}"
    assert "svc:" not in text, f"userinfo reached {where}"
    assert "L" * 100 not in text, f"an over-long path reached {where}"


def _run(
    args: list[str],
    expected: int,
    tmp_path: Path,
    wrote: Path | None = None,
    project: Path | None = None,
) -> str:
    """Run one command; check exit code, a fresh output file and no sentinel anywhere."""
    if wrote is not None:
        wrote.unlink(missing_ok=True)
    started = time.time() - 1
    full = [*args, *(["--project", str(project)] if project and args[1] in ("verify",) else [])]
    result = runner.invoke(app, full, env={"COLUMNS": "10000"})
    shown = " ".join(args[:3])
    assert result.exit_code == expected, f"{shown}: exit {result.exit_code}\n{result.output}"
    text = result.output
    _assert_clean(text, f"output of {shown}")
    if wrote is not None:
        assert wrote.is_file() and wrote.stat().st_mtime >= started, f"{shown}: no fresh file"
        _assert_clean(wrote.read_text(encoding="utf-8"), f"file written by {shown}")
    return text


def _reader_routes(ev: Path, d: Path, verify_exit: int) -> list[tuple[list[str], int, Path | None]]:
    html, md = d / "r.html", d / "r.md"
    e = str(ev)
    return [
        (["report", "show", e], 0, None),
        (["report", "show", e, "--json"], 0, None),
        (["report", "show", e, "--format", "html", "--output", str(html)], 0, html),
        (["report", "show", e, "--format", "markdown", "--output", str(md)], 0, md),
        (["report", "render", e, "--format", "html", "--output", str(html)], 0, html),
        (["report", "render", e, "--format", "markdown", "--output", str(md)], 0, md),
        (["report", "diff", e, e], 0, None),
        (["report", "diff", e, e, "--json"], 0, None),
        (["report", "verify", e], verify_exit, None),
        (["report", "verify", e, "--json"], verify_exit, None),
    ]


def test_legacy_manifest_fields_reach_no_output(tmp_path: Path) -> None:
    ev = _legacy_manifest(tmp_path)
    texts = [
        _run(a, code, tmp_path, w) for a, code, w in _reader_routes(ev, tmp_path, EXIT_FINDINGS)
    ]
    # Verify read the entries: every recorded file is a finding, and the long one did not crash it.
    assert all(_HOST in t for t in texts[:2])
    assert "input missing" in texts[8] or "missing" in texts[8]


@pytest.mark.parametrize("project", [False, True], ids=["no_project", "marked_project"])
def test_written_manifest_holds_and_shows_no_credential(tmp_path: Path, project: bool) -> None:
    ev = _written_manifest(tmp_path, project)
    _assert_clean(ev.read_text(encoding="utf-8"), "the written evidence file")
    for args, code, wrote in _reader_routes(ev, tmp_path, 0):
        _run(args, code, tmp_path, wrote, tmp_path if project else None)


@pytest.mark.parametrize(
    "arg",
    [
        f"//svc:{_sentinel('arg')}@{_HOST}/missing.json",
        f"https://svc:{_sentinel('arg_url')}@{_HOST}/missing.json?t={_sentinel('arg_q')}",
    ],
    ids=["network_path", "url"],
)
def test_evidence_file_argument_is_never_echoed(tmp_path: Path, arg: str) -> None:
    out = str(tmp_path / "never.html")
    for sub in ("show", "verify"):
        for extra in ([], ["--json"]):
            _run(["report", sub, arg, *extra], EXIT_USAGE, tmp_path)
    _run(["report", "render", arg, "--format", "html", "--output", out], EXIT_USAGE, tmp_path)
    _run(["report", "diff", arg, arg], EXIT_USAGE, tmp_path)
    _run(["report", "diff", arg, arg, "--json"], EXIT_USAGE, tmp_path)
