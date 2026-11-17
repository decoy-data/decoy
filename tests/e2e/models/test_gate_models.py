"""AT-C1g: the gate refuses a `post_scan` model that cannot run here (plan 4.1 matrix).

`decoy validate` and `decoy ci check` exit 1 with the reason code; `decoy validate` also prints the
install hint (`decoy ci check` reports codes only, never prose). A `pre_scan` model alone is not
the gate's to check. Mutation M-C1g (the gate preflight skips `post_scan`) turns every refusal
test here red.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.ci_support import (
    ci_check,
    ci_manifest,
    commit_all,
    make_repo,
    parse_stdout,
    write,
    write_clean_pipeline,
)

runner = CliRunner()


def _expected_ner_code() -> str:
    if importlib.util.find_spec("spacy") is None:
        return "ner_spacy_not_installed"
    from decoy_engine.detection.ner import model_installed

    if not model_installed("en_core_web_sm"):
        return "ner_model_not_installed"
    pytest.skip("spaCy and the model are installed here; the NER refusal cannot be shown")


def _pipeline(tmp_path: Path, *, post: list[str] | None, pre: list[str] | None = None) -> Path:
    src = tmp_path / "in.csv"
    src.write_text("email\na@example.invalid\nb@example.invalid\n", encoding="utf-8")
    cfg: dict = {
        "version": 2,
        "global_settings": {"seed": 42},
        "sources": {
            "customers": {"type": "file", "format": "csv", "has_header": True, "path": str(src)}
        },
        "tables": [
            {
                "name": "customers",
                "columns": [
                    {
                        "name": "email",
                        "strategy": "faker",
                        "provider": "person_email",
                        "deterministic": True,
                        "namespace": "cust_ns",
                    }
                ],
            }
        ],
        "targets": {
            "customers": {"type": "file", "format": "csv", "path": str(tmp_path / "out.csv")}
        },
    }
    if post is not None:
        cfg["post_scan"] = {"integrity": True, "detectors": post}
    if pre is not None:
        cfg["pre_scan"] = {"detectors": pre}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def _validate(path: Path, *extra: str):
    return runner.invoke(app, ["validate", str(path), *extra])


def test_classifier_disabled_refuses_with_code_and_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DECOY_ML_DISABLED", "1")
    path = _pipeline(tmp_path, post=["regex", "classifier"])
    result = _validate(path)
    assert result.exit_code == 1, result.output
    text = " ".join(result.output.split())
    assert "classifier_unavailable" in text
    assert "DECOY_ML_DISABLED" in text
    doc = json.loads(_validate(path, "--json").stdout)
    codes = [m["code"] for m in doc["messages"] if m["severity"] == "error"]
    assert codes == ["classifier_unavailable"]


def test_ner_missing_refuses_with_code_and_install_hint(tmp_path: Path) -> None:
    code = _expected_ner_code()
    path = _pipeline(tmp_path, post=["regex", "ner"])
    result = _validate(path)
    assert result.exit_code == 1, result.output
    text = " ".join(result.output.split())
    assert code in text
    assert "decoy models install ner" in text


def test_a_pre_scan_model_alone_is_not_the_gates_to_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DECOY_ML_DISABLED", "1")
    path = _pipeline(tmp_path, post=None, pre=["regex", "classifier", "ner"])
    result = _validate(path)
    assert result.exit_code == 0, result.output


def test_regex_only_post_scan_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DECOY_ML_DISABLED", "1")
    assert _validate(_pipeline(tmp_path, post=["regex"])).exit_code == 0


@pytest.mark.parametrize("model", ["classifier", "ner"])
def test_ci_check_refuses_with_the_reason_code(tmp_path: Path, model: str) -> None:
    expected = "classifier_unavailable" if model == "classifier" else _expected_ner_code()
    repo = make_repo(tmp_path / "repo")
    write_clean_pipeline(repo)
    text = (repo / "pipeline.yaml").read_text(encoding="utf-8")
    text += f"post_scan:\n  integrity: true\n  detectors: [regex, {model}]\n"
    write(repo, "pipeline.yaml", text)
    write(repo, ".decoy-ci.yaml", ci_manifest())
    commit_all(repo)
    proc = ci_check(repo, "--format", "json", env={"DECOY_ML_DISABLED": "1"})
    assert proc.returncode == 1, proc.stderr[-2000:]
    report = parse_stdout(proc)
    assert f"validate.{expected}" in [f["rule_id"] for f in report["findings"]]
