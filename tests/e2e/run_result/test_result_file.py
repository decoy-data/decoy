"""`decoy run --result PATH` writes the run result document to a path the user names (C-DOC3).

The file is the `result` member of the `--json` envelope, written by the one writer in
`_result.py` for every end of the run, and the path obeys the same placement rules as
`--evidence-out`: it never lands on an output, the quarantine file, `--evidence-out` or
`--vault`, and never replaces them through a link.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.csv_sources import csv_source
from tests.e2e.run_result.test_run_result import MARKER, _model, _write

runner = CliRunner()
posix_only = pytest.mark.skipif(os.name == "nt", reason="needs symlinks and hard links")


def _file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_file_equals_member(tmp_path: Path, monkeypatch) -> None:
    cfg = _write(tmp_path)
    out = tmp_path / "out.json"
    result = runner.invoke(app, ["run", str(cfg), "--json", "--result", str(out)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert _file(out) == payload["result"]
    _model(_file(out))
    assert payload["result_status"] == {"document": "built", "file": "written", "code": None}

    human = tmp_path / "human.json"
    monkeypatch.chdir(tmp_path)
    shown = runner.invoke(app, ["run", str(cfg), "--result", "human.json"])
    assert shown.exit_code == 0, shown.output
    assert "Result: human.json" in shown.output
    assert _file(human)["status"] == "succeeded"


@pytest.mark.parametrize(
    ("end", "exit_code"),
    [("success", 0), ("runtime", 3), ("interrupt", 130), ("early", 1)],
)
def test_every_end_writes_the_file(tmp_path: Path, end: str, exit_code: int) -> None:
    cfg = _write(tmp_path)
    out = tmp_path / "out.json"
    args = ["run", str(cfg), "--json", "--result", str(out)]
    patched = None
    if end == "runtime":
        patched = mock.patch("decoy_engine.run_pipeline", side_effect=RuntimeError(MARKER))
    elif end == "interrupt":
        patched = mock.patch("decoy_engine.run_pipeline", side_effect=KeyboardInterrupt())
    elif end == "early":
        args += ["--notify", "bogus"]
    if patched is None:
        result = runner.invoke(app, args)
    else:
        with patched:
            result = runner.invoke(app, args)
    assert result.exit_code == exit_code, result.output
    document = _file(out)
    _model(document)
    assert document["exit_code"] == exit_code
    assert MARKER not in out.read_text(encoding="utf-8")
    if end != "interrupt":
        assert json.loads(result.stdout)["result"] == document


@pytest.mark.parametrize("flag", [[], ["-q"]])
def test_preview_writes_the_file_in_every_mode(tmp_path: Path, flag: list[str]) -> None:
    cfg = _gen_config(tmp_path)
    out = tmp_path / "out.json"
    result = runner.invoke(app, ["run", str(cfg), "--rows", "2", *flag, "--result", str(out)])
    assert result.exit_code == 0, result.output
    _model(_file(out))


def _gen_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "gen.yaml"
    cfg.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "global_settings": {"seed": 7},
                "sources": {},
                "tables": [
                    {
                        "name": "g",
                        "row_count": 3,
                        "generate_columns": [
                            {"name": "id", "type": "sequence", "start": 1, "step": 1}
                        ],
                    }
                ],
                "targets": {
                    "g": {"type": "file", "format": "csv", "path": str(tmp_path / "g.csv")}
                },
            }
        ),
        encoding="utf-8",
    )
    return cfg


@pytest.mark.parametrize("kind", ["generate", "mask"])
def test_preview_result_does_not_replace_a_target(tmp_path: Path, kind: str) -> None:
    cfg = _gen_config(tmp_path) if kind == "generate" else _write(tmp_path)
    target = tmp_path / ("g.csv" if kind == "generate" else "out1.csv")
    target.write_text("zz_keep\n", encoding="utf-8")
    result = runner.invoke(app, ["run", str(cfg), "--rows", "2", "--json", "--result", str(target)])
    assert target.read_text(encoding="utf-8") == "zz_keep\n", result.output


# The evidence manifest is written only when the run ends well, so its early-refusal case would
# assert nothing: `--evidence-out` is tried on a run that really reaches the write.
SIDE_FILE_RUNS = [("--result", False), ("--result", True), ("--evidence-out", False)]


def _refused_and_kept(args: list[str], victim: Path) -> None:
    before = victim.read_bytes()
    result = runner.invoke(app, args)
    assert result.exit_code == 1, result.output
    assert victim.read_bytes() == before


@posix_only
@pytest.mark.parametrize(("flag", "early"), SIDE_FILE_RUNS)
@pytest.mark.parametrize("what", ["source", "config", "symlink"])
def test_side_file_never_lands_on_an_input(
    tmp_path: Path, flag: str, early: bool, what: str
) -> None:
    cfg = _write(tmp_path)
    source = tmp_path / "in1.csv"
    victim = cfg if what == "config" else source
    path = victim
    if what == "symlink":
        path = tmp_path / "alias.json"
        path.symlink_to(source)
    args = ["run", str(cfg), "--json", flag, str(path)]
    _refused_and_kept([*args, "--notify", "bogus"] if early else args, victim)


def _relative_source_config(tmp_path: Path) -> tuple[Path, Path]:
    """`sub/p.yaml` naming its source as `../data/in1.csv`: `(config, source)`."""
    cfg = _write(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    (tmp_path / "in1.csv").rename(data / "in1.csv")
    sub = tmp_path / "sub"
    sub.mkdir()
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    raw["sources"]["t1"]["path"] = "../data/in1.csv"
    moved = sub / "p.yaml"
    moved.write_text(yaml.safe_dump(raw), encoding="utf-8")
    cfg.unlink()
    return moved, data / "in1.csv"


@pytest.mark.parametrize(("flag", "early"), SIDE_FILE_RUNS)
def test_relative_source_is_protected(tmp_path: Path, flag: str, early: bool) -> None:
    cfg, source = _relative_source_config(tmp_path)
    args = ["run", str(cfg), "--json", flag, str(source)]
    _refused_and_kept([*args, "--notify", "bogus"] if early else args, source)


def test_column_names_file_is_protected(tmp_path: Path) -> None:
    cfg = _write(tmp_path)
    names = tmp_path / "names.txt"
    names.write_text("code\n", encoding="utf-8")
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    raw["sources"]["t1"].update({"has_header": False, "column_names_file": "names.txt"})
    cfg.write_text(yaml.safe_dump(raw), encoding="utf-8")
    for flag in ("--result", "--evidence-out"):
        _refused_and_kept(["run", str(cfg), "--json", flag, str(names)], names)


def test_duckdb_source_database_is_protected(tmp_path: Path) -> None:
    duckdb = pytest.importorskip("duckdb")
    cfg = _write(tmp_path)
    db = tmp_path / "src.duckdb"
    con = duckdb.connect(str(db))
    con.execute("create table t1 as select 'zz_a' as code")
    con.close()
    flags = ["--duckdb-source", f"t1={db}"]
    _refused_and_kept(["run", str(cfg), "--json", *flags, "--result", str(db)], db)
    _refused_and_kept(
        ["run", str(cfg), "--json", *flags, "--notify", "bogus", "--result", str(db)], db
    )


def test_project_pipeline_source_is_protected(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("DECOY_PROJECT", raising=False)
    root = tmp_path / "proj"
    (root / "data").mkdir(parents=True)
    (root / "decoy.yaml").write_text("kind: decoy-project/v1\n", encoding="utf-8")
    source = root / "data" / "in.csv"
    source.write_text("code\nzz_a\nzz_b\n", encoding="utf-8")
    folder = root / "pipelines" / "p1"
    folder.mkdir(parents=True)
    raw = {
        "version": 2,
        "global_settings": {"seed": 7},
        "sources": {"t1": csv_source(source) | {"path": "../../data/in.csv"}},
        "tables": [{"name": "t1", "columns": [{"name": "code", "strategy": "redact"}]}],
        "targets": {"t1": {"type": "file", "format": "csv", "path": "t1.csv"}},
    }
    (folder / "pipeline.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    monkeypatch.chdir(root)
    _refused_and_kept(["run", "p1", "--json", "--result", "data/in.csv"], source)
    _refused_and_kept(
        ["run", "p1", "--json", "--notify", "bogus", "--result", "data/in.csv"], source
    )


@pytest.mark.parametrize(("end", "exit_code"), [("success", 0), ("runtime", 3)])
def test_write_failure_keeps_exit(tmp_path: Path, end: str, exit_code: int) -> None:
    cfg = _write(tmp_path)
    missing = tmp_path / "no_such_dir" / "out.json"
    args = ["run", str(cfg), "--json", "--result", str(missing)]
    if end == "runtime":
        with mock.patch("decoy_engine.run_pipeline", side_effect=RuntimeError(MARKER)):
            result = runner.invoke(app, args)
    else:
        result = runner.invoke(app, args)
    assert result.exit_code == exit_code, result.output
    payload = json.loads(result.stdout)
    assert payload["result_status"]["file"] == "failed"
    assert payload["result_status"]["code"] == "run_result_write_failed"
    assert payload["result"]["exit_code"] == exit_code
    lines = [ln for ln in result.stderr.splitlines() if "run_result_write_failed" in ln]
    assert len(lines) == 1
    assert "no_such_dir" not in result.stderr and MARKER not in result.stderr


def _with_quarantine(cfg: Path, quarantine: Path) -> None:
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    raw["quarantine"] = {"enabled": True, "output_path": str(quarantine)}
    cfg.write_text(yaml.safe_dump(raw), encoding="utf-8")


@posix_only
@pytest.mark.parametrize(
    "case", ["target", "quarantine", "evidence", "vault", "symlink", "hardlink"]
)
def test_result_path_collides(tmp_path: Path, case: str) -> None:
    cfg = _write(tmp_path)
    target = tmp_path / "out1.csv"
    keep = "zz_keep\n"
    args = ["run", str(cfg), "--json"]
    shared = target
    if case == "target":
        pass
    elif case == "quarantine":
        shared = tmp_path / "quarantine.jsonl"
        _with_quarantine(cfg, shared)
    elif case == "evidence":
        shared = tmp_path / "evidence.json"
        args += ["--evidence-out", str(shared)]
    elif case == "vault":
        shared = tmp_path / "vault.bin"
        args += ["--vault", str(shared)]
    elif case == "symlink":
        shared = tmp_path / "alias.json"
        target.write_text(keep, encoding="utf-8")
        shared.symlink_to(target)
    else:
        shared = tmp_path / "hard.json"
        target.write_text(keep, encoding="utf-8")
        os.link(target, shared)
    if case in ("target", "quarantine", "evidence", "vault"):
        shared.write_text(keep, encoding="utf-8")
    with mock.patch("decoy_engine.run_pipeline") as engine:
        result = runner.invoke(app, [*args, "--result", str(shared)])
    assert result.exit_code == 1, result.output
    assert "output_path_collision" in result.output
    assert "--result" in result.output
    engine.assert_not_called()
    assert shared.read_text(encoding="utf-8") == keep
    if case in ("symlink", "hardlink"):
        assert target.read_text(encoding="utf-8") == keep


@posix_only
def test_early_refusal_does_not_overwrite_a_target(tmp_path: Path) -> None:
    """A refusal that comes before the gate still holds the placement rules."""
    cfg = _write(tmp_path)
    target = tmp_path / "out1.csv"
    target.write_text("zz_keep\n", encoding="utf-8")
    result = runner.invoke(
        app, ["run", str(cfg), "--json", "--notify", "bogus", "--result", str(target)]
    )
    assert result.exit_code == 1, result.output
    assert target.read_text(encoding="utf-8") == "zz_keep\n"
    assert json.loads(result.stdout)["result_status"]["file"] == "failed"


def test_refused_with_all(tmp_path: Path) -> None:
    result = runner.invoke(app, ["run", "--all", "--result", str(tmp_path / "x.json")])
    assert result.exit_code == 1, result.output
    assert "--result" in result.output
