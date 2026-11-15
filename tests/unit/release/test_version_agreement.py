"""AT-F2d: the CLI version literal, `pyproject.toml` and `decoy --version` say one thing."""

from __future__ import annotations

import sys
from pathlib import Path

from typer.testing import CliRunner

import decoy
from decoy.__main__ import app
from decoy._version import __version__

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"


def test_version_literal_matches_pyproject_and_cli_output() -> None:
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    assert __version__ == declared
    assert decoy.__version__ == declared
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert declared in result.stdout.split()
