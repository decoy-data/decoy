"""AT-C2b and AT-C2b2: `decoy scan --detectors` and `--ner-model` (SCAN-ML C2b, plan 4.7).

- `--detectors regex,classifier` prints the detector line on the card and `detectors` in
  `--json` and in the saved scan; `--detectors classifier` alone (no regex) exits 1 (AT-C2b).
- A model that cannot run refuses with exit 1, its reason code and the install hint before any
  table is read; `-v` sends the engine's `pre_scan.detectors` record to stderr and without `-v`
  it stays off it (AT-C2b2). `decoy scan --config` is SCAN-MULTI S1c.2; it shares this preflight.
- Nothing printed holds a cell value.

Mutations: M-C2b (accept a list without regex), M-C2b2 (map the refusal to exit 3), M-C2b2b
(drop the `-v` stderr handler), M-C2b3 (do not pass `pre_scan` to the engine scan).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app

runner = CliRunner()
CANARY = "CANARY-C2B-4471"
LINE = "regex; classifier lgbm-v1 0.1.0"


@pytest.fixture
def people(tmp_path: Path) -> Path:
    path = tmp_path / "people.csv"
    rows = ["id,email,notes"] + [f"{i},user{i}@example.invalid,{CANARY}" for i in range(20)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _scan(path: Path, *args: str):
    return runner.invoke(app, ["scan", str(path), "--has-header", *args])


def _flat(text: str) -> str:
    return " ".join(text.split())


# --- AT-C2b ------------------------------------------------------------------------------------


def test_the_card_names_the_detectors_that_ran(people: Path) -> None:
    result = _scan(people, "--detectors", "regex,classifier")

    assert result.exit_code == 0, result.output
    assert f"Detectors {LINE}" in _flat(result.stdout)


def test_json_lists_the_detectors_with_model_ids_and_versions(people: Path) -> None:
    result = _scan(people, "--detectors", "regex,classifier", "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["detectors"] == [
        {"source": "regex", "model_id": None, "model_version": None},
        {"source": "classifier", "model_id": "lgbm-v1", "model_version": "0.1.0"},
    ]


def test_a_regex_only_scan_says_so(people: Path) -> None:
    card = _scan(people)
    doc = json.loads(_scan(people, "--json").stdout)

    assert "Detectors regex" in _flat(card.stdout)
    assert doc["detectors"] == [{"source": "regex", "model_id": None, "model_version": None}]


def test_several_tables_carry_one_detector_list(people: Path, tmp_path: Path) -> None:
    other = tmp_path / "orders.csv"
    other.write_text("id,total\n1,5\n2,6\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "scan",
            str(people),
            str(other),
            "--has-header",
            "--detectors",
            "regex,classifier",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    assert [d["source"] for d in doc["detectors"]] == ["regex", "classifier"]


def test_the_saved_scan_records_the_detectors(people: Path, tmp_path: Path) -> None:
    saved = tmp_path / "scan.json"

    result = _scan(people, "--detectors", "regex,classifier", "--output", str(saved))

    assert result.exit_code == 0, result.output
    core = json.loads(saved.read_text(encoding="utf-8"))
    assert [d["source"] for d in core["detectors"]] == ["regex", "classifier"]


@pytest.mark.parametrize(
    "args",
    [
        ("--detectors", "classifier"),
        ("--detectors", "ner"),
        ("--detectors", "regex,regex"),
        ("--detectors", "regex,bogus"),
        ("--detectors", "regex,"),
        ("--ner-model", "en_core_web_sm"),
        ("--detectors", "regex,classifier", "--ner-model", "en_core_web_sm"),
        ("--detectors", "regex,ner", "--ner-model", "not a package"),
    ],
    ids=[
        "classifier_alone",
        "ner_alone",
        "repeat",
        "unknown",
        "empty_name",
        "model_without_ner",
        "model_with_classifier_only",
        "bad_model_name",
    ],
)
def test_a_bad_detector_choice_exits_1_before_any_scan(people: Path, args: tuple[str, ...]) -> None:
    with mock.patch("decoy_engine.scan_sources") as scan:
        result = _scan(people, *args, "--json")

    assert result.exit_code == 1, result.output
    scan.assert_not_called()
    doc = json.loads(result.stdout)
    assert doc["status"] == "error"
    assert "not a package" not in result.output and "bogus" not in result.output


# --- AT-C2b2 -----------------------------------------------------------------------------------


def test_a_model_that_cannot_load_refuses_before_a_table_is_read(people: Path) -> None:
    from decoy_engine import ModelStatus, ModelUnavailableError

    from decoy.cli.models import hint

    refused = ModelUnavailableError("classifier_unavailable", cause="pack")
    with (
        mock.patch("decoy_engine.load_detectors", side_effect=refused),
        mock.patch("decoy_engine.scan_sources") as scan,
    ):
        result = _scan(people, "--detectors", "regex,classifier", "--json")

    assert result.exit_code == 1, result.output
    scan.assert_not_called()
    doc = json.loads(result.stdout)
    assert doc["code"] == refused.reason
    expected = hint(ModelStatus("classifier", "lgbm-v1", False, None, None, refused.reason, "pack"))
    assert doc["hint"] == expected


def test_a_disabled_classifier_names_its_reason_and_hint(
    people: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DECOY_ML_DISABLED", "1")

    result = _scan(people, "--detectors", "regex,classifier")

    assert result.exit_code == 1, result.output
    text = _flat(result.output)
    assert "classifier_unavailable" in text
    assert "unset DECOY_ML_DISABLED" in text
    assert "Detectors" not in text


@pytest.mark.parametrize("verbose", [True, False], ids=["verbose", "default"])
def test_verbose_sends_the_pre_scan_record_to_stderr(people: Path, verbose: bool) -> None:
    result = _scan(people, "--detectors", "regex,classifier", *(["-v"] if verbose else []))

    assert result.exit_code == 0, result.output
    line = "pre_scan.detectors sources=regex,classifier classifier=lgbm-v1@0.1.0"
    assert (line in result.stderr) is verbose
    assert line not in result.stdout


def test_no_cell_value_reaches_any_output(people: Path) -> None:
    result = _scan(people, "--detectors", "regex,classifier", "--show-fields", "-v")

    assert result.exit_code == 0, result.output
    assert CANARY not in result.stdout + result.stderr
