"""AT-C1a: `decoy models list` rows and `--json` keys for available and unavailable models.

Mutation M-C1a (hide the reason code) turns `test_unavailable_rows_name_the_reason_code` red.
"""

from __future__ import annotations

import json

import pytest
from decoy_engine import ModelStatus
from typer.testing import CliRunner

from decoy.__main__ import app

runner = CliRunner()
ROW_KEYS = {
    "source",
    "model_id",
    "available",
    "version",
    "runtime_version",
    "reason",
    "cause",
    "hint",
}

CLASSIFIER_OK = ModelStatus("classifier", "lgbm-v1", True, "0.1.0", "4.6.0", None)
CLASSIFIER_IMPORT = ModelStatus(
    "classifier", "lgbm-v1", False, None, None, "provider.classifier_unavailable", "import"
)
NER_OK = ModelStatus("ner", "en_core_web_sm", True, "3.8.0", "3.8.18", None)
NER_MISSING = ModelStatus(
    "ner", "en_core_web_sm", False, None, None, "provider.ner_spacy_not_installed"
)


def _fake(monkeypatch: pytest.MonkeyPatch, classifier: ModelStatus, ner: ModelStatus) -> None:
    monkeypatch.setattr("decoy.cli.models._status.classifier_status", lambda: classifier)
    monkeypatch.setattr("decoy.cli.models._status.ner_status", lambda model="en_core_web_sm": ner)


def _rows(*args: str) -> tuple[int, dict]:
    result = runner.invoke(app, ["models", "list", "--json", *args])
    return result.exit_code, json.loads(result.stdout)


def test_available_rows_and_json_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, CLASSIFIER_OK, NER_OK)
    code, doc = _rows()
    assert code == 0
    assert doc["command"] == "models list" and doc["status"] == "ok"
    rows = {r["source"]: r for r in doc["models"]}
    assert [r["source"] for r in doc["models"]] == ["classifier", "ner"]
    assert all(set(r) == ROW_KEYS for r in doc["models"])
    assert rows["classifier"] == {
        "source": "classifier",
        "model_id": "lgbm-v1",
        "available": True,
        "version": "0.1.0",
        "runtime_version": "4.6.0",
        "reason": None,
        "cause": None,
        "hint": None,
    }
    assert rows["ner"]["available"] is True and rows["ner"]["version"] == "3.8.0"
    assert rows["ner"]["runtime_version"] == "3.8.18"


def test_unavailable_rows_name_the_reason_code(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, CLASSIFIER_IMPORT, NER_MISSING)
    code, doc = _rows()
    assert code == 0, "an unavailable model is a status, not a failure"
    rows = {r["source"]: r for r in doc["models"]}
    assert rows["classifier"]["available"] is False
    assert rows["classifier"]["reason"] == "provider.classifier_unavailable"
    assert rows["classifier"]["cause"] == "import"
    assert "brew install libomp" in rows["classifier"]["hint"]
    assert rows["ner"]["reason"] == "provider.ner_spacy_not_installed"
    assert rows["ner"]["version"] is None
    assert "decoy models install ner" in rows["ner"]["hint"]

    human = runner.invoke(app, ["models", "list"])
    assert human.exit_code == 0
    text = " ".join(human.stdout.split())
    assert "provider.classifier_unavailable" in text
    assert "provider.ner_spacy_not_installed" in text
    assert "decoy models install ner" in text


def test_list_says_ner_takes_the_environment_off_a_certified_dp_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake(monkeypatch, CLASSIFIER_OK, NER_MISSING)
    _, doc = _rows()
    assert "certified" in doc["note"] and "DP" in doc["note"]
    human = runner.invoke(app, ["models", "list"])
    assert "certified" in " ".join(human.stdout.split())


def test_list_reads_each_status_once_through_the_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def classifier() -> ModelStatus:
        seen.append("classifier")
        return CLASSIFIER_OK

    def ner(model: str = "en_core_web_sm") -> ModelStatus:
        seen.append(f"ner:{model}")
        return NER_OK

    monkeypatch.setattr("decoy.cli.models._status.classifier_status", classifier)
    monkeypatch.setattr("decoy.cli.models._status.ner_status", ner)
    assert _rows()[0] == 0
    assert seen == ["classifier", "ner:en_core_web_sm"]
