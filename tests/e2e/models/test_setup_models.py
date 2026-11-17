"""AT-C1f: the `models` section of `decoy setup`.

`decoy setup` keeps RUN-STREAM's rule that it needs a terminal or `--yes`; the models section adds
`--ner install|skip` and `--ner-from`. It installs through the same code as `decoy models install`
and stores nothing in `settings.json`. Mutation M-C1f (prompt off a terminal) turns
`test_yes_without_a_ner_answer_never_prompts_or_installs` red.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from decoy import _resources
from decoy.__main__ import app
from tests.unit.models._rig import make_rig, wheel

GIB = 2**30
runner = CliRunner()


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("DECOY_HOME", str(home))
    monkeypatch.delenv("DECOY_MAX_MEMORY", raising=False)
    monkeypatch.delenv("DECOY_THREADS", raising=False)
    monkeypatch.setattr(_resources, "_auto_memory", lambda: 8 * GIB)
    monkeypatch.setattr(_resources, "_auto_threads", lambda: 6)
    return home


@pytest.fixture
def rig(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    rig = make_rig(monkeypatch, tmp_path / "rig")
    monkeypatch.setattr("decoy.cli.models._status.ner_status", rig.ner_status)
    return rig


def _json(result) -> dict:
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1, (result.exit_code, result.stdout, result.stderr)
    return json.loads(lines[0])


def test_ner_skip_with_yes_off_a_terminal_installs_nothing_and_exits_0(rig, _home: Path) -> None:
    result = runner.invoke(app, ["setup", "--ner", "skip", "--yes", "--json"])
    assert result.exit_code == 0, result.output
    doc = _json(result)
    assert doc["models"]["ner"] == "skipped"
    assert rig.calls == []
    stored = json.loads((_home / "settings.json").read_text(encoding="utf-8"))
    assert "models" not in stored, "the models section installs; it stores nothing"
    assert doc["sections"] == {"resources": {"max_memory": "8GiB", "threads": 6}}


def test_ner_install_without_yes_off_a_terminal_exits_1(rig, _home: Path) -> None:
    result = runner.invoke(app, ["setup", "--ner", "install", "--json"])
    assert result.exit_code == 1
    assert rig.calls == []
    assert not (_home / "settings.json").exists()


def test_yes_without_a_ner_answer_never_prompts_or_installs(rig, _home: Path) -> None:
    result = runner.invoke(app, ["setup", "--yes", "--json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["models"]["ner"] == "skipped"
    assert rig.calls == []


def test_ner_install_with_yes_runs_the_shared_install(rig) -> None:
    result = runner.invoke(app, ["setup", "--ner", "install", "--yes", "--json"])
    assert result.exit_code == 0, result.output
    doc = _json(result)
    assert doc["models"]["ner"] == "installed"
    assert doc["models"]["model"] == {"id": "en_core_web_sm", "version": "3.8.0"}
    assert len(rig.calls) == 2


def test_ner_from_installs_from_the_given_wheels(rig, tmp_path: Path) -> None:
    src = tmp_path / "wh"
    for name in ("en_core_web_sm-3.8.0-py3-none-any.whl", "spacy-3.8.18-py3-none-any.whl"):
        wheel(src, name)
    result = runner.invoke(
        app, ["setup", "--ner", "install", "--ner-from", str(src), "--yes", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert rig.calls and all("--no-index" in c.argv for c in rig.calls)


def test_a_failing_install_returns_its_code_after_the_settings_are_written(
    rig, _home: Path
) -> None:
    rig.rc = 1
    result = runner.invoke(app, ["setup", "--ner", "install", "--yes", "--json"])
    assert result.exit_code == 3
    assert _json(result)["code"] == "models.install_failed"
    assert (_home / "settings.json").exists(), "the resources section ran first"


def test_ner_from_with_skip_is_a_usage_error(rig, tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["setup", "--ner", "skip", "--ner-from", str(tmp_path), "--yes", "--json"]
    )
    assert result.exit_code == 1
    assert rig.calls == []


def test_section_order_is_fixed_and_appendable() -> None:
    from decoy.cli.setup._sections import SECTIONS, STEPS, setup_order

    assert [s.name for s in SECTIONS] == ["resources"]
    assert [s.name for s in STEPS] == ["models"]
    assert setup_order() == ("resources", "models")
