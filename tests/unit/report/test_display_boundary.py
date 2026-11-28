"""Every report surface prints the display copy, never the recorded manifest (A2, A10).

Row numbers name the behavior table in `docs/plans/2026-11-28-d6-manifest-display-boundary.md`.
Each planted leaf gets its own sentinel inside a credential carrier; the carriers rotate over the
leaves so every leaf meets every carrier across the parameter set.
"""

from __future__ import annotations

import copy
import html
import json
import string
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from tests.unit.test_safe_url import _CARRIERS
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.evidence import (
    ManifestError,
    build_manifest,
    check_manifest,
    compute_manifest_hash,
    display_manifest,
    read_manifest,
    verify_manifest_issues,
)
from decoy.cli.report import render_html, render_markdown
from decoy.safe_url import DisplayCopy, display_location, display_text

pytestmark = pytest.mark.usefixtures("mask_secret")
runner = (
    CliRunner(mix_stderr=False)
    if "mix_stderr" in CliRunner.__init__.__code__.co_varnames
    else CliRunner()
)
_ENV = {"COLUMNS": "10000"}


def _sentinel(i: int) -> str:
    letters = string.ascii_lowercase
    return f"zq{letters[i // 26]}{letters[i % 26]}sentinelqz"


def _base(d: Path, project: bool) -> tuple[dict[str, Any], Path]:
    """A real `build_manifest` result with every kind of free string field filled."""
    d.mkdir(parents=True, exist_ok=True)
    if project:
        (d / "decoy.yaml").write_text("kind: decoy-project/v1\n", encoding="utf-8")
    pipeline = d / "pipeline.yaml"
    pipeline.write_text("version: 2\n", encoding="utf-8")
    (d / "in.csv").write_text("id\n1\n", encoding="utf-8")
    (d / "out.csv").write_text("id\n2\n", encoding="utf-8")
    config = {
        "sources": {"people": {"type": "file", "path": "in.csv"}},
        "targets": {"people": {"type": "file", "format": "csv", "path": "out.csv"}},
        "tables": [{"name": "people", "columns": [{"name": "id", "strategy": "hash"}]}],
    }
    evidence = d / "ev" / "evidence.json"
    evidence.parent.mkdir(exist_ok=True)
    warning = SimpleNamespace(code="probe", provider="regex", column="id", detail={"k": "v"})
    manifest = build_manifest(
        pipeline_path=pipeline,
        config_dict=config,
        run_result={"row_counts": {"people": 1}},
        cli_version="0",
        engine_version="0",
        key_label="label",
        warnings=["cli warning"],
        timings=[
            {"strategy_type": "hash", "column": "id", "elapsed_ms": 1, "peak_memory_delta_kb": 0}
        ],
        engine_warnings=[warning],
        project_root=d if project else None,
        evidence_path=evidence if project else None,
    )
    manifest["scan_baseline"] = {
        "path": "scans/base.json",
        "fingerprint": None,
        "fingerprint_method": None,
        "size_bytes": None,
    }
    manifest["cli_note"] = "additive"
    return manifest, evidence


def _null_entry(path: str) -> dict[str, Any]:
    return {"path": path, "fingerprint": None, "fingerprint_method": None, "size_bytes": None}


def _plant(manifest: dict[str, Any], project: bool, k: int) -> tuple[dict[str, Any], dict, list]:
    """(raw, expected display, sentinels): every free leaf and dynamic key gets a carrier."""
    raw, shown = copy.deepcopy(manifest), copy.deepcopy(manifest)
    sentinels: list[str] = []

    def carrier() -> tuple[str, str]:
        i = len(sentinels)
        sentinels.append(_sentinel(i))
        return _CARRIERS[(i + k) % len(_CARRIERS)].format(S=sentinels[-1]), sentinels[-1]

    def text() -> tuple[str, str]:
        value, _ = carrier()
        return value, display_text(value)

    def location() -> tuple[str, str]:
        value, _ = carrier()
        return value, display_location(value)

    for field in ("run_id", "run_timestamp", "cli_version", "engine_version", "key_label"):
        raw[field], shown[field] = text()
    raw["cli_note"], shown["cli_note"] = text()
    if not project:  # a project manifest resolves its pipeline path inside the project
        raw["pipeline_path"], shown["pipeline_path"] = location()
    raw["scan_baseline"]["path"], shown["scan_baseline"]["path"] = location()
    for group in ("input_fingerprints", "output_fingerprints"):
        key, key_shown = text()
        path, path_shown = location()
        raw[group][key], shown[group][key_shown] = _null_entry(path), _null_entry(path_shown)
    key, key_shown = text()
    raw["row_counts"][key], shown["row_counts"][key_shown] = 7, 7
    raw["warnings"][0], shown["warnings"][0] = text()
    typed_raw, typed_shown = raw["warnings"][1], shown["warnings"][1]
    for field in ("provider", "column"):
        typed_raw[field], typed_shown[field] = text()
    key, key_shown = text()
    typed_raw["detail"][key], typed_shown["detail"][key_shown] = text()
    for field in ("strategy_type", "column"):
        raw["timings"][0][field], shown["timings"][0][field] = text()
    for field in ("table", "column", "strategy"):
        raw["strategies"][0][field], shown["strategies"][0][field] = text()
    raw["manifest_hash"] = shown["manifest_hash"] = compute_manifest_hash(raw)
    return raw, shown, sentinels


def _absent(sentinels: list[str], text: str, where: str) -> None:
    found = [s for s in sentinels if s in text]
    assert not found, f"{where} shows planted values {found}"


def _invoke(args: list[str], expected: int = 0) -> str:
    result = runner.invoke(app, args, env=_ENV)
    assert result.exit_code == expected, f"{args}: exit {result.exit_code}\n{result.output}"
    stderr = result.stderr if result.stderr_bytes is not None else ""
    return result.output + stderr


@pytest.mark.parametrize("project", [False, True], ids=["legacy", "project"])
@pytest.mark.parametrize("k", range(0, len(_CARRIERS), 2))
def test_a2_every_surface_shows_the_display_copy(tmp_path: Path, project: bool, k: int) -> None:
    base, evidence = _base(tmp_path / "run", project)
    raw, shown, sentinels = _plant(base, project, k)
    evidence.write_text(json.dumps(raw), encoding="utf-8")
    plain = tmp_path / "run" / "ev" / "plain.json"
    if not project:  # a bound manifest is read only where its run wrote it
        plain.write_text(json.dumps(base), encoding="utf-8")
    e = str(evidence)

    out = json.loads(_invoke(["report", "show", e, "--json"]))
    assert out["manifest"] == shown
    rc_key = next(t for t in shown["row_counts"] if t != "people")

    card = _invoke(["report", "show", e])
    _absent(sentinels, card, "the card")
    assert rc_key in card
    if not project:
        assert shown["pipeline_path"] in card

    for cmd in ("show", "render"):
        for fmt in ("html", "markdown"):
            written = tmp_path / f"report.{fmt}"
            _absent(
                sentinels, _invoke(["report", cmd, e, "--format", fmt, "-o", str(written)]), cmd
            )
            doc = written.read_text(encoding="utf-8")
            doc = html.unescape(doc) if fmt == "html" else doc
            _absent(sentinels, doc, f"{cmd} {fmt}")
            assert rc_key in doc

    other = str(plain) if not project else e
    diff_json = _invoke(["report", "diff", other, e, "--json"])
    _absent(sentinels, diff_json, "diff --json")
    if not project:
        deltas = json.loads(diff_json)["row_count_deltas"]
        assert rc_key in [d["table"] for d in deltas]
    _absent(sentinels, _invoke(["report", "diff", other, e]), "diff")
    for args in (["report", "verify", e], ["report", "verify", e, "--json"]):
        result = runner.invoke(app, args, env=_ENV)
        _absent(sentinels, result.output, "verify")


# --- A10: the public renderers keep their dict input ---

_ROW36 = "postgresql://admin:2024#Secret word@db.example/prod"


def _a10_manifest(tmp_path: Path) -> dict[str, Any]:
    base, _ = _base(tmp_path, project=False)
    base["row_counts"]["https://u:PW7@h/x"] = 3
    base["input_fingerprints"]["s"] = _null_entry(_ROW36)
    base["manifest_hash"] = compute_manifest_hash(base)
    return base


@pytest.mark.parametrize("render", [render_html, render_markdown], ids=["html", "markdown"])
def test_a10_public_renderers_take_a_raw_dict(tmp_path: Path, render: Any) -> None:
    raw = _a10_manifest(tmp_path)
    text = html.unescape(render(raw))
    for secret in ("PW7", "Secret", "2024", "admin"):
        assert secret not in text
    assert "https://h" in text
    assert "(remote location)" in text
    assert render(display_manifest(raw)) == render(raw)


# --- Rows asserted at their own boundary ---


def test_row_7_row_count_key_in_card_and_json(tmp_path: Path) -> None:
    base, _ = _base(tmp_path / "run", project=False)
    base["row_counts"]["https://u:PW7@h/x"] = 3
    base["manifest_hash"] = compute_manifest_hash(base)
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps(base), encoding="utf-8")
    shown = json.loads(_invoke(["report", "show", str(ev), "--json"]))["manifest"]
    assert shown["row_counts"] == {"people": 1, "https://h": 3}
    card = _invoke(["report", "show", str(ev)])
    assert "PW7" not in card
    assert "https://h" in card


def test_row_35_display_manifest_keeps_every_count(tmp_path: Path) -> None:
    base, _ = _base(tmp_path, project=False)
    base["row_counts"] = {"https://a:1@h/x": 1, "https://b:2@h/y": 2}
    shown = display_manifest(base)
    assert type(shown) is DisplayCopy
    assert shown["row_counts"] == {"https://h": 1, "https://h (2)": 2}


def _changed_file_manifest(tmp_path: Path, table: str, recorded: str) -> dict[str, Any]:
    base, _ = _base(tmp_path, project=False)
    entry = base["input_fingerprints"].pop("people")
    entry["fingerprint"] = recorded
    base["input_fingerprints"][table] = entry
    base["manifest_hash"] = compute_manifest_hash(base)
    return base


def test_row_25_verify_issue_names_the_displayed_table(tmp_path: Path) -> None:
    manifest = _changed_file_manifest(tmp_path, "https://u:PW@h/t", "sha256:" + "0" * 64)
    messages = [i.message for i in verify_manifest_issues(manifest)]
    changed = [m for m in messages if m.startswith("input fingerprint changed")]
    assert len(changed) == 1
    assert "(table 'https://h')" in changed[0]
    assert "PW" not in changed[0]


def test_row_39_noncanonical_recorded_digest_is_not_previewed(tmp_path: Path) -> None:
    manifest = _changed_file_manifest(tmp_path, "people", "https://bob:2024@db/x")
    changed = [
        i.message for i in verify_manifest_issues(manifest) if i.kind == "input_fingerprint_changed"
    ]
    assert len(changed) == 1
    assert "bob" not in changed[0] and "2024" not in changed[0]
    assert "(recorded (not a digest), current sha256:" in changed[0]
    current = changed[0].split("current ")[1]
    assert len(current.split("...")[0]) == len("sha256:") + 9


@pytest.mark.parametrize(
    ("group", "key", "value", "message"),
    [
        (
            "output_fingerprints",
            "https://u:PW@h/x",
            "not an object",
            "evidence manifest is malformed: `output_fingerprints.https://h` must be an object.",
        ),
        (
            "row_counts",
            "//u:PW@host/t",
            "many",
            "evidence manifest is malformed: `row_counts.//host` must be an integer.",
        ),
    ],
    ids=["row26", "row38"],
)
def test_rows_26_38_field_names_use_the_displayed_key(
    tmp_path: Path, group: str, key: str, value: Any, message: str
) -> None:
    base, _ = _base(tmp_path, project=False)
    base[group][key] = value
    with pytest.raises(ManifestError) as caught:
        check_manifest(base)
    assert caught.value.message == message
    assert str(caught.value) == message


def test_row_40_parse_refusal_names_the_displayed_file(tmp_path: Path) -> None:
    bad = tmp_path / "https:" / "h" / "hook" / "TOKEN"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError) as caught:
        read_manifest(bad)
    assert caught.value.message.startswith("could not parse (remote location) as JSON: ")
    assert str(caught.value) == caught.value.message
    assert "TOKEN" not in caught.value.message


def test_row_50_diff_previews_only_canonical_digests(tmp_path: Path) -> None:
    old = _changed_file_manifest(tmp_path / "a", "people", "https://bob:2024@db/x")
    new = _changed_file_manifest(tmp_path / "b", "people", "sha256:" + "1" * 64)
    paths = []
    for name, manifest in (("old.json", old), ("new.json", new)):
        paths.append(tmp_path / name)
        paths[-1].write_text(json.dumps(manifest), encoding="utf-8")
    text = _invoke(["report", "diff", str(paths[0]), str(paths[1])])
    assert "bob" not in text and "2024" not in text
    assert "(not a digest)" in text
    assert "sha256:" + "1" * 16 + "..." in text
