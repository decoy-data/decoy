"""AT-F2f: a PR that changes the `--json` shape snapshot must also touch CHANGELOG.md."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "release" / "check_shape_changelog.py"
SHAPES = "tests/fixtures/release_freeze/json-shapes.json"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (tmp_path / "tests/fixtures/release_freeze").mkdir(parents=True)
    (tmp_path / SHAPES).write_text("{}\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path, _git(tmp_path, "rev-parse", "HEAD")


def _run(repo: Path, base: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--base", base],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def _commit(repo: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        (repo / rel).write_text(body, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")


def test_shape_change_without_changelog_fails(repo: tuple[Path, str]) -> None:
    path, base = repo
    _commit(path, {SHAPES: '{"a": 1}\n'})
    done = _run(path, base)
    assert done.returncode == 1
    assert "shape_change_without_changelog" in done.stderr + done.stdout


def test_shape_change_with_changelog_passes(repo: tuple[Path, str]) -> None:
    path, base = repo
    _commit(path, {SHAPES: '{"a": 1}\n', "CHANGELOG.md": "# Changelog\n\n- shape changed\n"})
    assert _run(path, base).returncode == 0


def test_a_change_elsewhere_passes(repo: tuple[Path, str]) -> None:
    path, base = repo
    _commit(path, {"other.txt": "x\n"})
    assert _run(path, base).returncode == 0
