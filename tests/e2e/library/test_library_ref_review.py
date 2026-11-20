"""`decoy library ref` and the command group's one error path (review round 1 on #215).

- V1 1: a ref never points at a record of another kind: `library ref scan-set/main <a
  sample-run id>` exits 1 with `ref_kind_mismatch` and writes no ref file; a committed ref that
  names a record of another kind is refused when it is read.
- V1 2: a ref write through a linked `refs/<kind>` or scope folder is refused and the file it
  would have replaced outside the library is unchanged.
- V1 3: a ref read through a linked `refs/<kind>` or scope folder is refused; the outside file
  is never reported as a ref.
- DESIGN 4: `path`, `fsck`, `list`, `show`, `diff` and `ref` share one root, error and exit
  path: the same library error exits with the same code from each, through the one emitter.
- DESIGN 5: `_resolve` uses `_paths.record_prefix`, the one id-prefix rule.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_RUNTIME, EXIT_USAGE
from decoy.cli.io import DECOY_DIR
from decoy.cli.library import LibraryError, open_library
from decoy.cli.library._errors import LIBRARY_LOCK_UNAVAILABLE
from tests.unit.library._helpers import ROOT, envelope

runner = CliRunner()
posix_only = pytest.mark.skipif(os.name != "posix", reason="symlinks without privilege")


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".git").mkdir()
    monkeypatch.chdir(root)
    monkeypatch.delenv("DECOY_LIBRARY", raising=False)
    monkeypatch.delenv("DECOY_PROJECT", raising=False)
    return root


@pytest.fixture
def stored(project: Path) -> list[str]:
    library = open_library(project / DECOY_DIR)
    return [library.put(envelope(n)).id for n in range(2)]


def _invoke(*args: str) -> object:
    return runner.invoke(app, ["library", *args])


def _snapshot(folder: Path) -> dict[str, bytes | None]:
    return {
        p.relative_to(folder).as_posix(): (p.read_bytes() if p.is_file() else None)
        for p in sorted(folder.rglob("*"))
    }


# -- V1 1 -----------------------------------------------------------------------------------------


def test_a_ref_of_another_kind_is_refused_and_not_written(project: Path, stored: list[str]) -> None:
    result = _invoke("ref", "scan-set/main", stored[0])
    assert result.exit_code == EXIT_USAGE, result.output
    assert "ref_kind_mismatch" in result.output
    assert not (project / DECOY_DIR / "library" / "refs" / "scan-set" / "main").exists()
    ok = _invoke("ref", "sample-run/main", stored[0])  # control: the matching kind is stored
    assert ok.exit_code == 0, ok.output


def test_a_committed_ref_of_another_kind_is_refused_on_read(
    project: Path, stored: list[str]
) -> None:
    refs = project / DECOY_DIR / "library" / "refs" / "scan-set"
    refs.mkdir(parents=True)
    (refs / "main").write_text(stored[0] + "\n", encoding="utf-8")
    for args in (("ref", "scan-set/main"), ("show", "scan-set/main")):
        result = _invoke(*args)
        assert result.exit_code != 0, args
        assert "ref_kind_mismatch" in result.output, args


# -- V1 2 and 3 -----------------------------------------------------------------------------------


def _linked_kind(project: Path, outside: Path) -> None:
    refs = project / DECOY_DIR / "library" / "refs"
    refs.mkdir(parents=True, exist_ok=True)
    (refs / "sample-run").symlink_to(outside, target_is_directory=True)


@posix_only
@pytest.mark.parametrize("name", ["sample-run/notes.md", "sample-run/scope/notes.md"])
def test_a_ref_write_through_a_linked_folder_changes_nothing_outside(
    project: Path, stored: list[str], tmp_path: Path, name: str
) -> None:
    outside = tmp_path / "docs"
    (outside / "scope").mkdir(parents=True)
    (outside / "notes.md").write_bytes(b"the user's notes")
    (outside / "scope" / "notes.md").write_bytes(b"more notes")
    before = _snapshot(outside)
    _linked_kind(project, outside)
    result = _invoke("ref", name, stored[0])
    assert result.exit_code == EXIT_RUNTIME, result.output
    assert "library_path_unsafe" in result.output
    assert _snapshot(outside) == before


@posix_only
@pytest.mark.parametrize("name", ["sample-run/main", "sample-run/scope/main"])
def test_a_ref_read_through_a_linked_folder_is_refused(
    project: Path, stored: list[str], tmp_path: Path, name: str
) -> None:
    outside = tmp_path / "docs"
    (outside / "scope").mkdir(parents=True)
    (outside / "main").write_text(stored[1] + "\n", encoding="utf-8")
    (outside / "scope" / "main").write_text(stored[1] + "\n", encoding="utf-8")
    _linked_kind(project, outside)
    for args in (("ref", name), ("show", name)):
        result = _invoke(*args)
        assert result.exit_code != 0, (args, result.output)
        assert stored[1] not in result.output, args
        assert "library_path_unsafe" in result.output, args


# -- DESIGN 4 -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        ("path",),
        ("fsck",),
        ("list",),
        ("show", "sample-run/latest"),
        ("ref", "sample-run/main"),
        ("diff", "sample-run/latest", "sample-run/latest~1"),
    ],
)
def test_the_same_library_error_exits_the_same_way_from_every_command(
    project: Path, stored: list[str], monkeypatch: pytest.MonkeyPatch, args: tuple[str, ...]
) -> None:
    """The library cannot be locked: every command says so with the same code and exit."""
    from decoy.cli.library import _fsck, _store

    def unlockable(*_a: object, **_k: object) -> object:
        raise LibraryError(LIBRARY_LOCK_UNAVAILABLE)

    monkeypatch.setattr(_store, "open_library", unlockable)
    monkeypatch.setattr(_fsck, "check", unlockable)
    result = _invoke(*args)
    assert result.exit_code == EXIT_RUNTIME, (args, result.output)
    assert "library_lock_unavailable" in result.output


def test_a_bad_library_flag_is_one_usage_error_everywhere(project: Path, tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    codes = {
        cmd: _invoke(cmd, "--library", str(blocker / "sub")).exit_code
        for cmd in ("path", "fsck", "list")
    }
    assert len(set(codes.values())) == 1, codes


def test_the_old_second_error_path_is_gone() -> None:
    source = (ROOT / "src" / "decoy" / "cli" / "library" / "_commands.py").read_text("utf-8")
    for name in ("def _root", "def _usage", "_LIBRARY_HELP", "_SOURCE"):
        assert name not in source


def test_a_json_error_is_one_error_object(project: Path, stored: list[str]) -> None:
    result = _invoke("list", "--json", "--since", "not-a-date")
    assert result.exit_code == EXIT_USAGE
    doc = json.loads(result.stdout)
    assert doc["command"] == "library list" and doc["status"] == "error"


# -- DESIGN 5 -------------------------------------------------------------------------------------


def test_resolve_has_no_second_prefix_rule() -> None:
    source = (ROOT / "src" / "decoy" / "cli" / "library" / "_resolve.py").read_text("utf-8")
    assert "record_prefix" in source
    for copy in ("_MIN_PREFIX", "_HEX", '"sha256:"'):
        assert copy not in source
