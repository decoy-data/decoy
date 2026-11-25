"""CL4 (24zf), AT-1 e2e and AT-12: `decoy demo` and `decoy fit` take their exit from
`exit_code_for` (plan 7.2). Each row that differs from the old map names its 7.2 line."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_CAPACITY, EXIT_FINDINGS, EXIT_RUNTIME, EXIT_USAGE

runner = CliRunner()


def _capacity():
    from decoy_engine.execution import ExecutionError

    return ExecutionError(code="out_of_core_insufficient_memory", message="m")


def _post_scan():
    from decoy_engine.verification.postmask import PostScanBlockedError

    return PostScanBlockedError({})


def _config_file_error():
    from decoy._config_file import ConfigFileError

    return ConfigFileError("yaml.empty", "x")


def _pipeline_validation():
    from decoy_engine import PipelineValidationError

    return PipelineValidationError("m", code="source_file.file_not_found")


DEMO_EXITS = [
    # 7.2 demo: capacity 3 to 5; PostScanBlockedError 3 to 4; ConfigFileError 3 to 1.
    ("capacity", _capacity, EXIT_CAPACITY),
    ("memory error", MemoryError, EXIT_CAPACITY),
    ("post-scan block", _post_scan, EXIT_FINDINGS),
    ("config file error", _config_file_error, EXIT_USAGE),
    ("pipeline validation", _pipeline_validation, EXIT_USAGE),
    # Unchanged at 3.
    ("runtime error", lambda: RuntimeError("boom"), EXIT_RUNTIME),
    ("os error", lambda: OSError("disk"), EXIT_RUNTIME),
]


@pytest.mark.parametrize(
    ("name", "factory", "expected"), DEMO_EXITS, ids=[d[0] for d in DEMO_EXITS]
)
def test_demo_exits_with_the_owner_map(tmp_path: Path, name: str, factory, expected: int) -> None:
    with mock.patch("decoy.cli.demo._run_single_demo", side_effect=factory()):
        result = runner.invoke(app, ["demo", "--dir", str(tmp_path / "out")])

    assert result.exit_code == expected, result.output


def test_demo_text_does_not_change(tmp_path: Path) -> None:
    with mock.patch("decoy.cli.demo._run_single_demo", side_effect=RuntimeError("boom")):
        result = runner.invoke(app, ["demo", "--dir", str(tmp_path / "out"), "--json"])

    assert json.loads(result.stdout) == {"command": "demo", "status": "error", "error": "boom"}


# AT-12
def test_fit_with_an_unreadable_csv_exits_1(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("", encoding="utf-8")

    result = runner.invoke(app, ["fit", str(bad)])

    assert result.exit_code == EXIT_USAGE, result.output


def test_fit_exits_through_the_owner_for_a_source_error(tmp_path: Path) -> None:
    from decoy.cli.gen._fit import FitSourceError

    good = tmp_path / "good.csv"
    good.write_text("a,b\n1,2\n", encoding="utf-8")
    with mock.patch("decoy.cli.fit._command.exit_code_for", return_value=EXIT_RUNTIME, create=True):
        with mock.patch(
            "decoy.cli.fit._command.fit_exact_snapshot",
            side_effect=FitSourceError("x", code="fit_x"),
        ):
            result = runner.invoke(app, ["fit", str(good)])

    assert result.exit_code == EXIT_RUNTIME, result.output


def test_fit_joint_max_cells_validation_stays_1(tmp_path: Path) -> None:
    good = tmp_path / "good.csv"
    good.write_text("a,b\n1,2\n", encoding="utf-8")

    result = runner.invoke(app, ["fit", str(good), "--joint-max-cells", "0"])

    assert result.exit_code == EXIT_USAGE, result.output
