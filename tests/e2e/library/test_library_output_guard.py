"""The record library root is one more destination in the output-collision rule (LIB L3a).

A run stores its records under the resolved library root, so an output or side file at or inside
that root is refused by the gate with the usual collision refusal, before anything is written.
The root comes from `DECOY_LIBRARY` (relative or absolute) or the project's `.decoy`.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
import yaml

from decoy.cli.exit_codes import EXIT_USAGE
from decoy.cli.io import DECOY_DIR
from tests.e2e.library.test_run_evidence_records import (
    PIPELINE,
    _run,
    project,  # noqa: F401  (fixture)
)

ROOTS = ["unset", "relative", "absolute"]
FLAGS = ["--result", "--evidence-out", "--integrity-out", "target"]


def _root(project: Path, how: str, monkeypatch: pytest.MonkeyPatch) -> Path:  # noqa: F811
    if how == "unset":
        return project / DECOY_DIR
    if how == "relative":
        monkeypatch.setenv("DECOY_LIBRARY", "mylib")
        return project / "mylib"
    chosen = project.parent / "abs-lib"
    monkeypatch.setenv("DECOY_LIBRARY", str(chosen))
    return chosen


@pytest.mark.parametrize("inside", [False, True], ids=["at-root", "inside-root"])
@pytest.mark.parametrize("flag", FLAGS)
@pytest.mark.parametrize("how", ROOTS)
def test_an_output_on_the_library_root_is_refused_before_any_write(
    project: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    how: str,
    flag: str,
    inside: bool,
) -> None:
    root = _root(project, how, monkeypatch)
    destination = root / "named.json" if inside else root
    args: list[str] = []
    if flag == "target":
        path = project / PIPELINE
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        config["targets"]["customers"]["path"] = str(root / "masked.csv")
        path.write_text(yaml.safe_dump(config), encoding="utf-8")
    else:
        args = [flag, str(destination)]
    with mock.patch("decoy_engine.run_pipeline") as engine:
        result = _run(*args)
    assert result.exit_code == EXIT_USAGE, result.output
    assert "resolve to one destination" in result.output
    assert "record library" in result.output
    engine.assert_not_called()
    assert not root.exists()


def test_a_relative_library_env_cannot_take_the_result_file(
    project: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DECOY_LIBRARY", "r.json")
    result = _run("--result", "r.json")
    assert result.exit_code == EXIT_USAGE, result.output
    assert "resolve to one destination" in result.output
    assert not (project / "r.json").exists()


def test_no_library_leaves_the_root_free_for_an_output(project: Path) -> None:  # noqa: F811
    result = _run("--no-library", "--result", str(project / DECOY_DIR / "r.json"))
    assert "output_path_collision" not in result.output
