"""P9: `decoy tokenize --out-dir DIR` places its targets like `decoy run --out-dir DIR`.

DIR stands in for the run folder: relative to the current folder, made owner-only after the gate,
no claim, run id or `current` link, files overwritten. `--vault` stays a path typed relative to the
current folder. Every refusal exits 1 before a source is read or a folder is made.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_OK, EXIT_USAGE
from tests.e2e.test_tokenize_cli import _TOKENIZE_COLS
from tests.e2e.test_tokenize_cli import _pipeline as _tokenize_pipeline

pytestmark = pytest.mark.usefixtures("mask_secret")
runner = CliRunner()
EMAILS = ["a@x.com", "b@y.com", "a@x.com"]


def _project(tmp_path: Path, target: str = "tok.csv") -> Path:
    root = tmp_path / "proj"
    d = root / "pipelines" / "orders"
    d.mkdir(parents=True)
    (root / "decoy.yaml").write_text("kind: decoy-project/v1\n", encoding="utf-8")
    cfg = _tokenize_pipeline(d, _TOKENIZE_COLS, out_name="tok.csv", emails=EMAILS)
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    raw["targets"]["people"]["path"] = target
    cfg.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return root


def _tokenize(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> Any:
    monkeypatch.chdir(root)
    return runner.invoke(app, ["tokenize", "orders", *args], catch_exceptions=False)


def _files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*")}


def _no_source_read(monkeypatch: pytest.MonkeyPatch) -> None:
    import decoy.cli.run as run_module

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("a source was read before the refusal")

    monkeypatch.setattr(run_module, "_load_sources_from_config", boom)


def test_targets_land_in_dir_and_no_run_folder_is_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    result = _tokenize(root, monkeypatch, "--out-dir", "build", "--vault", "v.db")
    assert result.exit_code == EXIT_OK, result.output
    assert (root / "build" / "tok.csv").is_file()
    assert (root / "v.db").is_file()
    assert not (root / "out").exists()
    assert "a@x.com" not in (root / "build" / "tok.csv").read_text(encoding="utf-8")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_dir_is_relative_to_the_current_folder_and_owner_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    assert _tokenize(root, monkeypatch, "--out-dir", "a/b", "--vault", "v.db").exit_code == 1
    assert not (root / "a").exists()
    assert _tokenize(root, monkeypatch, "--out-dir", "b", "--vault", "v.db").exit_code == EXIT_OK
    assert ((root / "b").stat().st_mode & 0o077) == 0
    assert not (root / "pipelines" / "orders" / "b").exists()


def test_a_second_run_overwrites_in_place(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    assert _tokenize(root, monkeypatch, "--out-dir", "b", "--vault", "v.db").exit_code == EXIT_OK
    before = _files(root)
    assert _tokenize(root, monkeypatch, "--out-dir", "b", "--vault", "v.db").exit_code == EXIT_OK
    assert _files(root) == before


def test_detokenize_reads_the_out_dir_file_by_the_suffix_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    assert _tokenize(root, monkeypatch, "--out-dir", "b", "--vault", "v.db").exit_code == EXIT_OK
    result = runner.invoke(
        app, ["detokenize", "orders", "b/tok.csv", "--vault", "v.db"], catch_exceptions=False
    )
    assert result.exit_code == EXIT_OK, result.output
    got = pd.read_csv(root / "b" / "tok.detokenized.csv", dtype=str)
    assert got["email"].tolist() == EMAILS


def test_a_vault_that_aliases_a_target_is_refused_before_any_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    _no_source_read(monkeypatch)
    before = _files(root)
    result = _tokenize(root, monkeypatch, "--out-dir", "b", "--vault", "b/tok.csv")
    assert result.exit_code == EXIT_USAGE
    assert "layout.output_path_collision" in result.output
    assert _files(root) == before


def test_a_target_escaping_dir_is_refused_before_any_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path, target="../x.csv")
    _no_source_read(monkeypatch)
    before = _files(root)
    result = _tokenize(root, monkeypatch, "--out-dir", "b", "--vault", "v.db")
    assert result.exit_code == EXIT_USAGE
    assert "layout.output_path_escapes" in result.output
    assert _files(root) == before


def test_a_dir_that_is_a_file_is_refused_with_the_exact_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    root = _project(tmp_path)
    (root / "b").write_text("x", encoding="utf-8")
    _no_source_read(monkeypatch)
    before = _files(root)
    result = _tokenize(root, monkeypatch, "--out-dir", "b", "--vault", "v.db", "--json")
    assert result.exit_code == EXIT_USAGE
    doc = json.loads(result.stdout)
    assert doc["status"] == "error"
    assert doc["code"] == "layout.output_dir_unusable"
    assert doc["error_kind"] == "validation"
    (message,) = doc["messages"]
    assert (message["layer"], message["severity"], message["code"]) == (
        "config",
        "error",
        "layout.output_dir_unusable",
    )
    assert _files(root) == before


def test_without_out_dir_a_run_folder_is_still_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    assert _tokenize(root, monkeypatch, "--vault", "v.db").exit_code == EXIT_OK
    assert list((root / "out" / "orders").glob("*/tok.csv"))


def test_a_refusal_carries_its_code_and_every_finding_in_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    root = _project(tmp_path)
    result = _tokenize(root, monkeypatch, "--out-dir", "b", "--vault", "b/tok.csv", "--json")
    assert result.exit_code == EXIT_USAGE
    doc = json.loads(result.stdout)
    assert doc["code"] == "layout.output_path_collision"
    assert doc["error_kind"] == "validation"
    assert [m["code"] for m in doc["messages"]] == ["layout.output_path_collision"]


# DUP-DEST CL1: the project route (no --out-dir) runs the same layout check, with --vault typed.


def _two_table_project(tmp_path: Path, path_a: str, path_b: str) -> Path:
    root = _project(tmp_path)
    cfg = root / "pipelines" / "orders" / "pipeline.yaml"
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    raw["sources"]["people_b"] = raw["sources"]["people"]
    raw["tables"].append({**raw["tables"][0], "name": "people_b"})
    raw["targets"]["people"]["path"] = path_a
    raw["targets"]["people_b"] = {**raw["targets"]["people"], "path": path_b}
    cfg.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return root


def _engine_must_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("run_pipeline was called before the refusal")

    monkeypatch.setattr("decoy_engine.run_pipeline", boom)


def _refused(result: Any, root: Path, before: set[str]) -> None:
    assert result.exit_code == EXIT_USAGE
    assert "layout.output_path_collision" in result.output
    assert _files(root) == before


def test_project_route_refuses_two_targets_on_one_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = str(tmp_path / "shared.csv")
    root = _two_table_project(tmp_path, shared, shared)
    _no_source_read(monkeypatch)
    _engine_must_not_run(monkeypatch)
    before = _files(root)
    _refused(_tokenize(root, monkeypatch, "--vault", "v.db"), root, before)
    assert not (tmp_path / "shared.csv").exists()


@pytest.mark.parametrize("out_dir", [False, True], ids=["project", "out-dir"])
def test_targets_meeting_through_a_symlinked_folder_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, out_dir: bool
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    root = _two_table_project(tmp_path, str(real / "t.csv"), str(tmp_path / "link" / "t.csv"))
    _no_source_read(monkeypatch)
    _engine_must_not_run(monkeypatch)
    before = _files(root)
    args = ("--out-dir", "b") if out_dir else ()
    _refused(_tokenize(root, monkeypatch, *args, "--vault", "v.db"), root, before)
    assert list(real.iterdir()) == []


@pytest.mark.parametrize("out_dir", [False, True], ids=["project", "out-dir"])
def test_a_target_on_the_vault_path_is_refused_and_the_vault_is_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, out_dir: bool
) -> None:
    vault = tmp_path / "vault.db"
    root = _project(tmp_path, target=str(vault))
    _no_source_read(monkeypatch)
    _engine_must_not_run(monkeypatch)
    before = _files(root)
    args = ("--out-dir", "b") if out_dir else ()
    _refused(_tokenize(root, monkeypatch, *args, "--vault", str(vault)), root, before)
    assert not vault.exists()


def test_project_route_with_distinct_absolute_targets_still_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    root = _two_table_project(tmp_path, str(first), str(second))
    result = _tokenize(root, monkeypatch, "--vault", str(tmp_path / "vault.db"))
    assert result.exit_code == EXIT_OK, result.output
    assert first.exists() and second.exists()
    assert (tmp_path / "vault.db").exists()


@pytest.mark.parametrize("out_dir", [False, True], ids=["project", "out-dir"])
def test_equal_targets_no_table_writes_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, out_dir: bool
) -> None:
    # Every file target takes part, as in `decoy run` and `decoy validate`. The spare targets
    # share the real target's folder, so the collision is the first layout finding.
    root = _project(tmp_path)
    cfg = root / "pipelines" / "orders" / "pipeline.yaml"
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    unused = {"type": "file", "format": "csv", "path": "unused.csv"}
    raw["targets"]["ghost_a"] = unused
    raw["targets"]["ghost_b"] = dict(unused)
    cfg.write_text(yaml.safe_dump(raw), encoding="utf-8")
    _no_source_read(monkeypatch)
    _engine_must_not_run(monkeypatch)
    before = _files(root)
    args = ("--out-dir", "b") if out_dir else ()
    _refused(
        _tokenize(root, monkeypatch, *args, "--vault", str(tmp_path / "vault.db")), root, before
    )


@pytest.mark.parametrize("out_dir", [False, True], ids=["project", "out-dir"])
def test_an_existing_vault_a_target_names_keeps_its_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, out_dir: bool
) -> None:
    vault = tmp_path / "vault.db"
    vault.write_bytes(b"canary vault bytes")
    root = _project(tmp_path, target=str(vault))
    _no_source_read(monkeypatch)
    _engine_must_not_run(monkeypatch)
    before = _files(root)
    args = ("--out-dir", "b") if out_dir else ()
    _refused(_tokenize(root, monkeypatch, *args, "--vault", str(vault)), root, before)
    assert vault.read_bytes() == b"canary vault bytes"


@pytest.mark.parametrize("out_dir", [False, True], ids=["project", "out-dir"])
def test_a_target_hard_linked_to_an_existing_vault_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, out_dir: bool
) -> None:
    # tokenize updates an existing vault in place, so a hard link to it is the vault.
    vault = tmp_path / "vault.db"
    vault.write_bytes(b"canary vault bytes")
    alias = tmp_path / "alias.csv"
    os.link(vault, alias)
    root = _project(tmp_path, target=str(alias))
    _no_source_read(monkeypatch)
    _engine_must_not_run(monkeypatch)
    before = _files(root)
    args = ("--out-dir", "b") if out_dir else ()
    _refused(_tokenize(root, monkeypatch, *args, "--vault", str(vault)), root, before)
    assert vault.read_bytes() == b"canary vault bytes"
    assert os.path.samefile(vault, alias)
