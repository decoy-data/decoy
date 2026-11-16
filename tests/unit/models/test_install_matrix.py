"""AT-C1d, AT-C1h and the in-process half of AT-C1i for `decoy models install ner`.

AT-C1d (class row 2): pip fails, the verify step fails, the environment changed, Ctrl-C; each
leaves `models list` truthful and no temporary directory (M-C1d reports success before the verify
step). AT-C1h: constraints are `name==version` lines from `installed_distribution_set()` in an
environment holding an editable install (M-C1h builds them from `pip freeze`); the uv route; no
installer at all; the spaCy range (M-C1h2 drops it); an unpinned `--model` online. AT-C1i
(in-process): a failing installer whose output and configured index URL carry a credential
exposes it nowhere, and the safe error has no cause or context.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from pathlib import Path

import pytest
from decoy_engine.detection.ner import (
    DEFAULT_NER_MODEL,
    DEFAULT_NER_MODEL_VERSION,
    NER_MODEL_WHEELS,
)
from decoy_engine.quality.dp_provenance import installed_distribution_set
from tests.unit.models._rig import install_module, make_rig
from typer.testing import CliRunner

from decoy.__main__ import app

CANARY = "CANARY-PASSWORD"
PIN = NER_MODEL_WHEELS[(DEFAULT_NER_MODEL, DEFAULT_NER_MODEL_VERSION)]


def _models_list_ner(rig) -> bool:
    doc = json.loads(CliRunner().invoke(app, ["models", "list", "--json"]).stdout)
    return next(r for r in doc["models"] if r["source"] == "ner")["available"]


@pytest.fixture(autouse=True)
def _list_through_the_rig(monkeypatch: pytest.MonkeyPatch) -> None:
    from decoy_engine import classifier_status

    monkeypatch.setattr("decoy.cli.models._status.classifier_status", classifier_status)


def _share_status(monkeypatch: pytest.MonkeyPatch, rig) -> None:
    monkeypatch.setattr("decoy.cli.models._status.ner_status", rig.ner_status)


# --- AT-C1d: the install matrix -------------------------------------------------------------


def test_installer_failure_exits_3_with_its_exit_code_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    _share_status(monkeypatch, rig)
    rig.rc = 7
    code, doc = rig.json("--yes")
    assert code == 3
    assert doc["code"] == "models.install_failed"
    assert doc["installer_exit_code"] == 7
    assert len(rig.calls) == 1, "nothing runs after a failed installer call"
    assert rig.leftovers() == []
    assert _models_list_ner(rig) is False


def test_verify_failure_exits_3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    _share_status(monkeypatch, rig)
    rig.installs = False  # pip says 0, the model still does not load
    code, doc = rig.json("--yes")
    assert code == 3, doc
    assert doc["code"] == "models.install_failed"
    assert rig.leftovers() == []
    assert _models_list_ner(rig) is False


def test_a_moved_package_exits_3_naming_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    _share_status(monkeypatch, rig)
    rig.changed = True
    code, doc = rig.json("--yes")
    assert code == 3, doc
    assert doc["code"] == "models.env_changed"
    assert "numpy" in doc["error"] and "2.2.6" in doc["error"] and "2.3.0" in doc["error"]
    assert "spacy" not in doc["error"], "a new package is not a change"
    assert "reinstall" in doc["hint"].lower()
    assert rig.leftovers() == []
    assert _models_list_ner(rig) is True


def test_ctrl_c_leaves_no_temporary_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    _share_status(monkeypatch, rig)

    def interrupt(argv: list[str]) -> None:
        raise KeyboardInterrupt

    rig.hook = interrupt
    result = rig.invoke("--yes")
    assert result.exit_code == 130, "Ctrl-C keeps the shell's interrupt status"
    assert rig.leftovers() == []
    assert _models_list_ner(rig) is False


def test_success_reports_the_verified_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    code, doc = rig.json("--yes")
    assert code == 0, doc
    assert doc["status"] == "ok"
    assert doc["model"] == {"id": "en_core_web_sm", "version": "3.8.0"}
    assert doc["installed"] == ["en-core-web-sm", "spacy"]
    assert doc["dp_certified_environment"] is False


def test_off_a_terminal_without_yes_exits_1_and_installs_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    result = rig.invoke()
    assert result.exit_code == 1
    assert rig.calls == []


def test_managed_runtime_is_refused_first(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    monkeypatch.setattr(rig.mod, "managed_home", lambda: tmp_path / "home")
    code, doc = rig.json("--from", str(tmp_path / "missing.whl"), "--yes")
    assert code == 1
    assert doc["code"] == "models.managed_runtime"
    assert rig.calls == []


# --- AT-C1h: install mechanics --------------------------------------------------------------


def test_constraints_are_name_version_lines_from_the_installed_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rig = make_rig(monkeypatch, tmp_path, real_set=True)
    editable = [n for n, _ in installed_distribution_set() if n == "decoy-cli"]
    assert editable, "this test needs the editable decoy-cli install of the dev venv"
    rig.json("--yes")
    assert rig.calls
    for call in rig.calls:
        lines = call.files["--constraint"].splitlines()
        assert all(re.fullmatch(r"[a-z0-9][a-z0-9._-]*==\S+", ln) for ln in lines), lines
        expected = {f"{n}=={v}" for n, v in installed_distribution_set() if n != "decoy-engine"}
        assert set(lines) == expected


def test_uv_route_targets_this_interpreter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    monkeypatch.setattr(rig.mod, "pip_available", lambda: False)
    monkeypatch.setattr(
        rig.mod.shutil, "which", lambda name: "/opt/bin/uv" if name == "uv" else None
    )
    code, doc = rig.json("--yes")
    assert code == 0, doc
    for call in rig.calls:
        assert call.argv[:5] == ["/opt/bin/uv", "pip", "install", "--python", sys.executable]


def test_no_pip_and_no_uv_names_the_uv_tool_route(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    monkeypatch.setattr(rig.mod, "pip_available", lambda: False)
    monkeypatch.setattr(rig.mod.shutil, "which", lambda name: None)
    code, doc = rig.json("--yes")
    assert code == 1
    assert doc["code"] == "models.pip_missing"
    assert "uv tool install 'decoy-cli[ner]' --with" in doc["hint"]
    assert rig.calls == []


def test_pip_route_uses_this_interpreter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    rig.json("--yes")
    for call in rig.calls:
        assert call.argv[:4] == [sys.executable, "-m", "pip", "install"]


def test_online_install_passes_the_pinned_spacy_range_and_the_hashed_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    code, doc = rig.json("--yes")
    assert code == 0, doc
    closure, model = rig.calls
    assert f"spacy{PIN.spacy_range}" in closure.argv
    assert {"click<9,>=8.1", "spacy<4,>=3.7"} <= set(closure.argv)
    assert "--require-hashes" in model.argv and "--no-deps" in model.argv
    assert model.files["-r"].strip() == (
        f"{DEFAULT_NER_MODEL} @ {PIN.url} --hash=sha256:{PIN.sha256}"
    )


def test_an_unpinned_model_online_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    code, doc = rig.json("--model", "other_model", "--yes")
    assert code == 1
    assert doc["code"] == "models.model_unpinned"
    assert "--from" in doc["hint"]
    assert rig.calls == []


# --- AT-C1i (in-process): no credential or installer text leaks ----------------------------


@pytest.mark.parametrize("failure", ["exit", "oserror"])
def test_installer_output_and_index_url_never_leak(
    failure: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    real = install_module().run_installer
    rig = make_rig(monkeypatch, tmp_path)
    monkeypatch.setattr(rig.mod, "run_installer", real)  # fake only the subprocess under it
    monkeypatch.setenv("PIP_INDEX_URL", f"https://user:{CANARY}@host.invalid/simple")
    text = f"Looking in indexes: https://user:{CANARY}@host.invalid/simple"

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if failure == "oserror":
            raise OSError(text)
        return subprocess.CompletedProcess(argv, 2, text.encode(), text.encode())

    monkeypatch.setattr(rig.mod.subprocess, "run", fake_run)
    caplog.set_level(logging.DEBUG)
    result = rig.invoke("--yes", "--json")
    assert result.exit_code == 3
    for stream in (result.stdout, result.stderr, caplog.text):
        assert CANARY not in stream

    with pytest.raises(rig.mod.ModelsError) as info:
        rig.mod.install_ner(model=DEFAULT_NER_MODEL, source=None, confirm=lambda plan: True)
    err = info.value
    assert err.code == "models.install_failed"
    assert CANARY not in str(err) and CANARY not in err.message
    assert err.__cause__ is None and err.__context__ is None
