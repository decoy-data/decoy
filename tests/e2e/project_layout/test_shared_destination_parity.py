"""DUP-DEST CL2 (plan 7.3): `decoy run` and `decoy validate` report the same first code.

Two targets the declarations prove equal are the engine's `target_shared_destination` in both
commands, and `run` raises it before any source read or DuckDB staging. Outputs that meet only on
disk keep `layout.output_path_collision` in both.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_USAGE
from tests.e2e.project_layout.test_layout_gate import (
    COLLISION,
    SHARED,
    _codes,
    _project,
    _two_tables,
    _write,
    install_read_spy,
    posix_only,
    runner,
)


@pytest.fixture
def read_spy(monkeypatch) -> list[str]:
    return install_read_spy(monkeypatch)


def _first_code(output: str) -> str:
    return next(code for code in _codes(output) if code)


def _run_and_validate(cfg: Path) -> tuple[object, object]:
    return (
        runner.invoke(app, ["run", str(cfg), "--json"]),
        runner.invoke(app, ["validate", str(cfg), "--json"]),
    )


@posix_only
@pytest.mark.parametrize("case", ["equal_relative", "symlinked_folder"])
def test_run_and_validate_report_one_first_code_for_a_shared_destination(
    tmp_path: Path, read_spy: list[str], case: str
) -> None:
    # T-C5: equal declarations are the engine's refusal in both commands; outputs that meet
    # only on disk keep the layout code in both.
    root = _project(tmp_path)
    if case == "equal_relative":
        first, second, expected = "m.csv", "m.csv", SHARED
    else:
        (tmp_path / "real").mkdir()
        (tmp_path / "alias").symlink_to(tmp_path / "real", target_is_directory=True)
        first, second, expected = f"{tmp_path}/real/o.csv", f"{tmp_path}/alias/o.csv", COLLISION
    cfg = _write(root, "pipelines/orders/pipeline.yaml", _two_tables(root, first, second))
    run_result, validate_result = _run_and_validate(cfg)
    for result in (run_result, validate_result):
        assert result.exit_code == EXIT_USAGE, result.output
        assert _first_code(result.output) == expected
        assert "targets.a.path" in result.output and "targets.b.path" in result.output
    assert read_spy == []
    assert not (root / "out").exists()


def test_two_s3_targets_with_one_key_get_the_engine_code_from_both_commands(
    tmp_path: Path, read_spy: list[str]
) -> None:
    # T-C6: the CLI's own "shares its file name" cloud rule stays as a defense behind it.
    root = _project(tmp_path)
    cfg_dict = _two_tables(root, "unused.csv", "unused.csv")
    s3 = {"type": "s3", "format": "csv", "bucket": "b", "region": "us-east-1", "key": "d/x.csv"}
    cfg_dict["targets"] = {"a": dict(s3), "b": dict(s3)}
    cfg = _write(root, "pipelines/orders/pipeline.yaml", cfg_dict)
    run_result, validate_result = _run_and_validate(cfg)
    for result in (run_result, validate_result):
        assert result.exit_code == EXIT_USAGE, result.output
        assert _first_code(result.output) == SHARED
        assert "targets.a.key" in result.output and "targets.b.key" in result.output
        assert "d/x.csv" not in result.output
    assert read_spy == []


@pytest.fixture
def acquire_spy(monkeypatch) -> list[str]:
    """Records every `--duckdb-source` relation the run acquires."""
    from decoy.cli.run import _prepare

    seen: list[str] = []

    def spy(*_args, **_kwargs):
        seen.append("acquire_relation")
        raise AssertionError("a DuckDB relation was acquired before the refusal")

    monkeypatch.setattr(_prepare, "acquire_relation", spy)
    return seen


@posix_only
def test_a_source_less_duckdb_config_keeps_its_layout_refusal_before_staging(
    tmp_path: Path, acquire_spy: list[str]
) -> None:
    # T-C11: the schema refuses a YAML with no `sources:` before E1 runs, so the early layout
    # check still names the clash before a relation is read.
    root = _project(tmp_path)
    (tmp_path / "real").mkdir()
    (tmp_path / "alias").symlink_to(tmp_path / "real", target_is_directory=True)
    cfg_dict = _two_tables(root, f"{tmp_path}/real/o.csv", f"{tmp_path}/alias/o.csv")
    del cfg_dict["sources"]
    cfg = _write(root, "pipelines/orders/pipeline.yaml", cfg_dict)
    db = str(tmp_path / "missing.duckdb")
    args = ["run", str(cfg), "--json", "--duckdb-source", f"a={db}", "--duckdb-source", f"b={db}"]
    result = runner.invoke(app, args)
    assert result.exit_code == EXIT_USAGE, result.output
    assert _first_code(result.output) == COLLISION
    assert acquire_spy == []
    assert list((tmp_path / "real").iterdir()) == []


def test_equal_targets_refuse_before_a_duckdb_relation_is_acquired(
    tmp_path: Path, acquire_spy: list[str]
) -> None:
    # T-C11b: the early check raises the schema refusal itself, so staging never starts.
    root = _project(tmp_path)
    cfg = _write(root, "pipelines/orders/pipeline.yaml", _two_tables(root, "m.csv", "m.csv"))
    db = str(tmp_path / "missing.duckdb")
    result = runner.invoke(app, ["run", str(cfg), "--json", "--duckdb-source", f"a={db}"])
    assert result.exit_code == EXIT_USAGE, result.output
    assert _first_code(result.output) == SHARED
    assert COLLISION not in result.output
    assert acquire_spy == []
    assert not (root / "out").exists()
