"""Class guard: a credential planted in any path field or argument reaches no output.

Every recorded path field and every echoed argument gets its own sentinel. The reader fixture is a
legacy manifest written by hand (so it holds credentials the writer would never record), with real
fingerprints so `report verify` reads each entry. The writer fixture runs `build_manifest` over
every source kind in both project layouts. Each command must exit as expected, produce its file
fresh, and print no sentinel on stdout, stderr or in any file it wrote.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.evidence import ManifestError, build_manifest, compute_manifest_hash, read_manifest
from decoy.cli.exit_codes import EXIT_FINDINGS, EXIT_USAGE
from decoy.cli.library import open_library
from tests.e2e.library._records import build

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
        "nested_url": f"//share/https://svc:{_sentinel('nested')}@{_HOST}/f",
        "fragment": f"//id.example/callback#access_token={_sentinel('fragment')}",
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


def _written_manifest(tmp_path: Path, project: bool, filename: str = "payroll@2026.csv") -> Path:
    """`build_manifest` over every source kind, the file kind given as a URL too."""
    pipeline = tmp_path / "pipeline.yaml"
    pipeline.write_text("version: 2\n", encoding="utf-8")
    if project:
        (tmp_path / "decoy.yaml").write_text("kind: decoy-project/v1\n", encoding="utf-8")
    payroll = tmp_path / filename
    payroll.write_text("id\n1\n", encoding="utf-8")
    config = {
        "sources": {
            "payroll": {"type": "file", "path": "/" + str(payroll)},
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
    if result.stderr_bytes is not None:
        _assert_clean(result.stderr, f"stderr of {shown}")
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


@pytest.mark.serial
def test_legacy_manifest_fields_reach_no_output(tmp_path: Path) -> None:
    ev = _legacy_manifest(tmp_path)
    texts = [
        _run(a, code, tmp_path, w) for a, code, w in _reader_routes(ev, tmp_path, EXIT_FINDINGS)
    ]
    # Verify read the entries: every recorded file is a finding, and the long one did not crash it.
    assert (
        json.loads(texts[1])["manifest"]["input_fingerprints"]["fragment"]["path"] == "//id.example"
    )
    assert all(_HOST in t for t in texts[:2])
    assert "input missing" in texts[8] or "missing" in texts[8]


@pytest.mark.serial
@pytest.mark.parametrize("project", [False, True], ids=["no_project", "marked_project"])
@pytest.mark.parametrize(
    "filename",
    ["payroll@2026.csv", "payroll#2026.csv", "payroll?2026.csv", "payroll?year=2026.csv"],
)
def test_written_manifest_holds_and_shows_no_credential(
    tmp_path: Path, project: bool, filename: str
) -> None:
    ev = _written_manifest(tmp_path, project, filename)
    written = ev.read_text(encoding="utf-8")
    _assert_clean(written, "the written evidence file")
    assert json.loads(written)["input_fingerprints"]["payroll"]["fingerprint"] is not None
    for args, code, wrote in _reader_routes(ev, tmp_path, 0):
        _run(args, code, tmp_path, wrote, tmp_path if project else None)
    (tmp_path / filename).write_text("id\n2\n", encoding="utf-8")
    drift = _run(["report", "verify", str(ev), "--json"], EXIT_FINDINGS, tmp_path)
    assert "payroll" in str(json.loads(drift)["issues"])


@pytest.mark.serial
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


@pytest.mark.serial
def test_output_argument(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ev = _written_manifest(tmp_path, False)
    arg = f"https://svc:{_sentinel('output')}@{_HOST}/out.html"
    out = Path(arg)
    for success in (True, False):
        out.parent.mkdir(parents=True, exist_ok=True)
        if not success:
            out.unlink()
            out.mkdir()  # a directory cannot be replaced with a report
        for sub, mode in (("show", []), ("render", []), ("render", ["--json"])):
            text = _run(
                ["report", sub, str(ev), "--output", arg, *mode],
                0 if success else EXIT_USAGE,
                tmp_path,
                out if success else None,
            )
            assert f"https://{_HOST}" in text
            if mode:
                doc = json.loads(text)
                assert doc["status"] == ("ok" if success else "error")
                if success:
                    assert doc["output"] == f"https://{_HOST}"


@pytest.mark.serial
def test_verify_project_argument(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ev = _written_manifest(tmp_path, True)
    arg = f"https://svc:{_sentinel('project')}@{_HOST}/project"
    for mode in ([], ["--json"]):
        text = _run(["report", "verify", str(ev), "--project", arg, *mode], EXIT_USAGE, tmp_path)
        assert f"https://{_HOST}" in text


@pytest.mark.serial
def test_diff_warnings_and_unreadable_output(tmp_path: Path) -> None:
    ev = _legacy_manifest(tmp_path)
    manifest = json.loads(ev.read_text())
    long_path = f"//svc:{_LONG}{_sentinel('long_output')}@long.example/out.csv"
    manifest["output_fingerprints"]["t"]["path"] = long_path
    paths = []
    for side in ("old", "new"):
        url = f"https://svc:{_sentinel(side)}@{_HOST}/warning"
        warning = f"could not open //svc:{_sentinel(side)}@{_HOST}/share"
        manifest["warnings"] = [warning, {"code": "changed", "column": f"could not open {url}"}]
        manifest["manifest_hash"] = compute_manifest_hash(manifest)
        path = tmp_path / f"{side}.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        paths.append(str(path))
    args = ["report", "diff", *paths]
    human = _run(args, 0, tmp_path)
    assert "warning(s) added" in human and "warning(s) removed" in human
    doc = json.loads(_run([*args, "--json"], 0, tmp_path))
    assert doc["data_level"] == "skipped" and "//long.example" in doc["missing_files"]
    for field in ("warnings_added", "warnings_removed"):
        assert doc[field] == [
            f"could not open //{_HOST}",
            {"code": "changed", "column": f"could not open https://{_HOST}"},
        ]


@pytest.mark.serial
def test_library_show_payload(tmp_path: Path) -> None:
    ev = _written_manifest(tmp_path, False)
    manifest = json.loads(ev.read_text())
    manifest["warnings"] = [f"could not open {_sources()[key]}" for key in ("net_user", "file_url")]
    manifest["pipeline_path"] = _sources()["file_url"]
    manifest["manifest_hash"] = compute_manifest_hash(manifest)
    root = tmp_path / "library"
    record = open_library(root).put(build("evidence", manifest, 1))
    args = ["library", "show", record.id, "--library", str(root)]
    assert f"https://{_HOST}" in _run(args, 0, tmp_path)
    doc = json.loads(_run([*args, "--json"], 0, tmp_path))
    assert doc["record"]["payload"]["warnings"] == [
        f"could not open //{_HOST}",
        f"could not open https://{_HOST}",
    ]
    assert doc["record"]["payload"]["pipeline_path"] == f"https://{_HOST}"


# --- A3: two different manifests through every reader (plan rows 25, 26, 38 to 40, 53 to 62) ---

_CARRIER = f"https://svc:{_sentinel('carrier')}@h.example/x"
_SHOWN = "https://h.example"


def ab_manifests(tmp_path: Path) -> tuple[Path, Path]:
    """Legacy manifests A and B from real CSV files: B changes the carrier table's file and
    count, adds a table and records one `probe` warning whose column is the carrier."""
    paths = []
    for side, rows, extra in (("a", 3, False), ("b", 4, True)):
        d = tmp_path / side
        d.mkdir(parents=True)
        tables = [_CARRIER, *(["extra"] if extra else [])]
        config: dict[str, Any] = {"sources": {}, "targets": {}}
        for i, name in enumerate(tables):
            (d / f"in{i}.csv").write_text("id\n1\n", encoding="utf-8")
            (d / f"out{i}.csv").write_text(f"id\n{rows}\n", encoding="utf-8")
            config["sources"][name] = {"type": "file", "path": str(d / f"in{i}.csv")}
            config["targets"][name] = {
                "type": "file", "format": "csv", "path": str(d / f"out{i}.csv")
            }  # fmt: skip
        pipeline = d / "p.yaml"
        pipeline.write_text("version: 2\n", encoding="utf-8")
        probe = SimpleNamespace(code="probe", provider=None, column=_CARRIER, detail={})
        manifest = build_manifest(
            pipeline_path=pipeline, config_dict=config,
            run_result={"row_counts": dict.fromkeys(tables, rows)}, cli_version="0.1.0",
            engine_version="0.22.0", engine_warnings=[probe] if extra else None,
        )  # fmt: skip
        paths.append(d / "evidence.json")
        paths[-1].write_text(json.dumps(manifest), encoding="utf-8")
    return paths[0], paths[1]


@pytest.mark.serial
def test_a3_two_manifests_reach_no_output_and_show_the_safe_table(tmp_path: Path) -> None:
    a, b = ab_manifests(tmp_path)
    routes = [
        (["report", "diff", str(a), str(b), *args[4:]], code, w)
        if args[1] == "diff"
        else (args, code, w)
        for args, code, w in _reader_routes(b, tmp_path, 0)
    ]
    texts = [_run(args, code, tmp_path, w) for args, code, w in routes]
    card, shown = texts[0], json.loads(texts[1])["manifest"]
    assert shown["row_counts"] == {_SHOWN: 4, "extra": 4}
    assert (
        set(shown["input_fingerprints"]) == set(shown["output_fingerprints"]) == {_SHOWN, "extra"}
    )
    assert shown["warnings"][0]["column"] == _SHOWN
    assert re.search(r"Warnings\W+1\b", card)
    assert re.search(re.escape(_SHOWN) + r"\W+4\b", card)
    for doc in (tmp_path / "r.html", tmp_path / "r.md"):
        assert _SHOWN in doc.read_text(encoding="utf-8")
    diff = json.loads(texts[7])
    assert {"table": _SHOWN, "old": 3, "new": 4, "delta": 1} in diff["row_count_deltas"]
    assert re.search(re.escape(_SHOWN) + r"\W+3\W+4\W+\+1", texts[6])
    assert json.loads(texts[9])["issues"] == []
    assert "All fingerprints match" in texts[8]
    assert _run(["report", "verify", str(a)], 0, tmp_path)


def _refusal(tmp_path: Path, ev: Path, message: str, project: Path | None = None) -> None:
    for sub in ("show", "verify"):
        # `report show` has no --project; it finds the marker above the file, as verify does.
        extra = ["--project", str(project)] if project and sub == "verify" else []
        human = _run(["report", sub, str(ev), *extra], EXIT_USAGE, tmp_path)
        assert message in human
        doc = json.loads(_run(["report", sub, str(ev), "--json", *extra], EXIT_USAGE, tmp_path))
        assert doc["error"].startswith(message)


@pytest.mark.serial
@pytest.mark.parametrize(
    ("group", "key", "value", "message"),
    [
        (
            "output_fingerprints",
            f"https://svc:{_sentinel('r26')}@h.example/x",
            "not an object",
            f"evidence manifest is malformed: `output_fingerprints.{_SHOWN}` must be an object.",
        ),
        (
            "row_counts",
            f"//svc:{_sentinel('r38')}@h.example/t",
            "many",
            "evidence manifest is malformed: `row_counts.//h.example` must be an integer.",
        ),
    ],
    ids=["row26", "row38"],
)
def test_rows_26_38_malformed_names_the_displayed_table(
    tmp_path: Path, group: str, key: str, value: object, message: str
) -> None:
    ev = _legacy_manifest(tmp_path)
    manifest = json.loads(ev.read_text(encoding="utf-8"))
    manifest[group][key] = value
    ev.write_text(json.dumps(manifest), encoding="utf-8")
    _refusal(tmp_path, ev, message)


@pytest.mark.serial
def test_row_40_unparsable_file_at_a_url_shaped_path(tmp_path: Path) -> None:
    bad = tmp_path / "https:" / "h" / "hook" / _sentinel("r40")
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json", encoding="utf-8")
    _refusal(tmp_path, bad, "could not parse (remote location) as JSON: ")


@pytest.mark.serial
def test_rows_25_39_verify_names_safe_table_and_digest(tmp_path: Path) -> None:
    a, _ = ab_manifests(tmp_path)
    manifest = json.loads(a.read_text(encoding="utf-8"))
    entry = manifest["input_fingerprints"][_CARRIER]
    entry["fingerprint"] = f"https://bob:{_sentinel('r39')}@db/x"
    manifest["manifest_hash"] = compute_manifest_hash(manifest)
    a.write_text(json.dumps(manifest), encoding="utf-8")
    doc = json.loads(_run(["report", "verify", str(a), "--json"], EXIT_FINDINGS, tmp_path))
    [issue] = doc["issues"]
    assert f"(table '{_SHOWN}')" in issue
    assert "(recorded (not a digest), current sha256:" in issue
    assert f"(table '{_SHOWN}')" in _run(["report", "verify", str(a)], EXIT_FINDINGS, tmp_path)


def _bound(ev: Path, pipeline: Path, written_at: str, pipeline_path: str) -> None:
    """A project-bound manifest at `ev` with a valid pipeline fingerprint."""
    from decoy.cli.evidence import hash_file

    manifest: dict[str, Any] = {
        "schema_version": "cli-local-1", "producer": "decoy-cli", "path_base": "project",
        "project_manifest": written_at, "run_id": "r1", "run_timestamp": "2026-01-01T00:00:00Z",
        "cli_version": "0", "engine_version": "0", "pipeline_path": pipeline_path,
        "pipeline_fingerprint": hash_file(pipeline), "input_fingerprints": {},
        "output_fingerprints": {}, "row_counts": {}, "key_label": None, "warnings": [],
        "timings": [], "strategies": [], "manifest_hash": "",
    }  # fmt: skip
    manifest["manifest_hash"] = compute_manifest_hash(manifest)
    ev.parent.mkdir(parents=True, exist_ok=True)
    ev.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.serial
@pytest.mark.parametrize("row", ["53", "54", "62"])
def test_rows_53_54_62_project_refusals_name_no_carrier(tmp_path: Path, row: str) -> None:
    (tmp_path / ".git").mkdir()  # the project walk stops here
    proj = tmp_path / "proj"
    proj.mkdir()
    pipeline = proj / "p.yaml"
    pipeline.write_text("version: 2\n", encoding="utf-8")
    marker = _sentinel("marker")
    carrier = proj / "https:" / "h" / "hook" / marker
    project = None
    if row == "53":
        ev, kind, start = carrier, "project_not_found", "(remote location) records paths relative"
        _bound(ev, pipeline, "e.json", "p.yaml")
    elif row == "54":
        (proj / "decoy.yaml").write_text("kind: decoy-project/v1\n", encoding="utf-8")
        ev, kind, start = carrier, "project_mismatch", "(remote location) is not where its run"
        _bound(ev, pipeline, "ev/other.json", "p.yaml")
        project = proj
    else:
        (proj / "decoy.yaml").write_text("kind: decoy-project/v1\n", encoding="utf-8")
        ev, kind, start = proj / "ev" / "e.json", "path_outside_project", "evidence manifest is"
        _bound(ev, pipeline, "ev/e.json", f"../https:/h/hook/{marker}")
    with pytest.raises(ManifestError) as caught:
        read_manifest(ev, project)
    assert caught.value.kind == kind
    assert caught.value.message.startswith(start)
    assert str(caught.value) == caught.value.message
    assert marker not in caught.value.message
    if row == "62":
        assert "`pipeline_path`" in caught.value.message
    _refusal(tmp_path, ev, start, project)


@pytest.mark.serial
def test_verify_refuses_a_missing_project_under_a_carrier_path(tmp_path: Path) -> None:
    ev = _written_manifest(tmp_path, True)
    missing = tmp_path / "https:" / f"svc:{_sentinel('proj')}@h.example" / "nothere"
    for mode in ([], ["--json"]):
        _run(["report", "verify", str(ev), "--project", str(missing), *mode], EXIT_USAGE, tmp_path)


# --- A6: verify keeps reading the raw path ---


@pytest.mark.serial
@pytest.mark.parametrize("name", ["payroll#2026.csv", "payroll?2026.csv"])
def test_a6_verify_reads_raw_where_display_differs(tmp_path: Path, name: str) -> None:
    share = tmp_path / "share"
    share.mkdir()
    payroll = share / name
    payroll.write_text("id\n1\n", encoding="utf-8")
    pipeline = tmp_path / "pipeline.yaml"
    pipeline.write_text("version: 2\n", encoding="utf-8")
    manifest = build_manifest(
        pipeline_path=pipeline,
        config_dict={"sources": {"payroll": {"type": "file", "path": "/" + str(payroll)}}},
        run_result={"row_counts": {}},
        cli_version="0",
        engine_version="0",
    )
    assert manifest["input_fingerprints"]["payroll"]["fingerprint"] is not None
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps(manifest), encoding="utf-8")
    top = "//" + str(tmp_path).split("/")[1]
    shown = json.loads(_run(["report", "show", str(ev), "--json"], 0, tmp_path))["manifest"]
    assert shown["input_fingerprints"]["payroll"]["path"] == top
    assert _run(["report", "verify", str(ev)], 0, tmp_path)
    payroll.write_text("id\n2\n", encoding="utf-8")
    [issue] = json.loads(_run(["report", "verify", str(ev), "--json"], EXIT_FINDINGS, tmp_path))[
        "issues"
    ]
    assert issue.startswith(f"input fingerprint changed: {top} (table 'payroll')")


@pytest.mark.serial
def test_a6_legacy_row_4_entry_still_resolves_and_reports_missing(tmp_path: Path) -> None:
    ev = _legacy_manifest(tmp_path)
    manifest = json.loads(ev.read_text(encoding="utf-8"))
    row4 = f"/project/https:/user:{_sentinel('row4')}@host/in.csv"
    manifest["input_fingerprints"] = {
        "s": {"path": row4, "fingerprint": _FP, "fingerprint_method": "full", "size_bytes": 1}
    }
    manifest["manifest_hash"] = compute_manifest_hash(manifest)
    ev.write_text(json.dumps(manifest), encoding="utf-8")
    doc = json.loads(_run(["report", "verify", str(ev), "--json"], EXIT_FINDINGS, tmp_path))
    assert "input missing: (remote location) (table 's') not found" in doc["issues"]
