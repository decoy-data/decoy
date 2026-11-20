"""D-T14: the scan-diff rules moved to `decoy.cli.scanning` with no change in output.

`scan diff` (text, JSON, strict) and `ci check` drift findings are compared byte for byte
with the output recorded from the code before the move (tests/fixtures/scan_diff_move/golden.json).
The facade cell proves both callers can reach the rules through `decoy.cli.scanning`.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

from typer.testing import CliRunner

from decoy.__main__ import app
from tests.ci_support import (
    MANIFEST_NAME,
    ci_check,
    ci_manifest,
    make_repo,
    write,
    write_clean_pipeline,
)
from tests.scan_docs import scan_set_doc

GOLDEN = Path(__file__).parent.parent / "fixtures" / "scan_diff_move" / "golden.json"


def _doc(risk: float, groups: list[list[str]], fields: list[tuple[str, float | None]]) -> dict:
    return scan_set_doc(
        [{"name": n, "pii_score": s} for n, s in fields],
        table="s",
        reid_risk_score=risk,
        quasi_identifier_groups=groups,
    )


OLD = _doc(
    10.0,
    [["a", "b"], ["x", "y"]],
    [
        ("none_to_low", 0.0),
        ("low_to_med", 0.1),
        ("med_to_high", 0.3),
        ("high_to_med", 0.7),
        ("med_to_low", 0.4),
        ("same", 0.65),
        ("gone_high", 0.9),
        ("gone_none", None),
    ],
)
NEW = _doc(
    35.5,
    [["b", "a"], ["p", "q"]],
    [
        ("none_to_low", 0.05),
        ("low_to_med", 0.3),
        ("med_to_high", 0.6),
        ("high_to_med", 0.59),
        ("med_to_low", 0.2999),
        ("same", 0.99),
        ("new_high", 0.8),
        ("new_none", 0),
    ],
)


def collect(tmp: Path) -> dict:
    """Run every drift surface once and return the raw outputs."""
    scans = tmp / "scans"
    scans.mkdir()
    (scans / "old.json").write_text(json.dumps(OLD))
    (scans / "new.json").write_text(json.dumps(NEW))
    runner = CliRunner()
    out: dict = {}
    here = os.getcwd()
    os.chdir(scans)  # relative paths keep the card text independent of the temp dir
    try:
        for label, extra in (("text", []), ("json", ["--json"]), ("strict", ["--strict"])):
            res = runner.invoke(app, ["scan", "diff", "old.json", "new.json", *extra])
            out[f"scan_diff_{label}"] = {"code": res.exit_code, "stdout": res.stdout}
    finally:
        os.chdir(here)
    repo = make_repo(tmp / "repo")
    write_clean_pipeline(repo)
    write(repo, "old.json", json.dumps(OLD))
    write(repo, "new.json", json.dumps(NEW))
    drift = "  drift:\n    - {id: d, baseline: old.json, current: new.json}\n"
    write(repo, MANIFEST_NAME, ci_manifest(validation=False, extra_checks=drift))
    proc = ci_check(repo, "--format", "json")
    out["ci_check_json"] = {"code": proc.returncode, "stdout": proc.stdout}
    return out


def test_output_byte_equal_to_pre_move_golden(tmp_path: Path) -> None:
    assert collect(tmp_path) == json.loads(GOLDEN.read_text())


def test_facade_exports_the_rules() -> None:
    from decoy.cli.scanning import ScanDiff, diff_scan_sets

    diff = diff_scan_sets(OLD["tables"][0], NEW["tables"][0])
    assert isinstance(diff, ScanDiff)
    assert dataclasses.is_dataclass(diff)
    assert diff.drift is True
    assert [r["name"] for r in diff.pii_increased] == [
        "low_to_med",
        "med_to_high",
        "none_to_low",
    ]
    assert [r["name"] for r in diff.new_high_pii] == ["new_high"]
    assert diff.qi_added == [("p", "q")]
    assert diff.qi_removed == [("x", "y")]
    assert diff.risk_delta == 25.5


def test_old_names_are_gone_from_the_command_module() -> None:
    import decoy.cli.scan as scan_module

    assert not hasattr(scan_module, "compute_scan_diff")
    assert not hasattr(scan_module, "ScanDiff")
    assert os.path.exists(GOLDEN)
