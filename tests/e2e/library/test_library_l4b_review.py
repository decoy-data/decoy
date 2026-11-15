"""`library prune`, `clean` and `export` review fixes (review round 1 on #219).

Every link cell plants the link, runs the command and proves nothing outside the root changed;
each delete goes through `cli/library/_fs.py`.

- V1 1: `clean --yes` never follows a linked `scratch/` (to `library/` or to the project); a
  link inside scratch is removed as an entry.
- V1 2: prune never fails open: a ref with a byte order mark still protects its record, and an
  entry prune cannot explain (an unreadable ref, an unreadable kept record) makes `--yes`
  refuse with `library_unexplained_entries` while the preview names the count.
- V1 3: prune never deletes through a linked `library/` or `objects/` folder.
- V1 4: `export --output` refuses a destination inside the library or a final symlink.
- V1 5: `export --ref` with `--kind` or `--since` is a usage error.
- V1 6: a record this version cannot verify (a newer envelope major) makes export fail closed.
- V1 7: an unreadable refs folder is a coded refusal, never an internal error.
- DESIGN 9: prune and export share one link-closure walk, `_index.reachable`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from decoy_engine import records
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_OK, EXIT_RUNTIME, EXIT_USAGE
from decoy.cli.io import DECOY_DIR
from decoy.cli.library import open_library
from tests.e2e.library._records import run_result, sample, table
from tests.unit.library._helpers import object_path

runner = CliRunner()
posix_only = pytest.mark.skipif(os.name != "posix", reason="symlinks without privilege")
OLD = "2026-01-01T00:00:00Z"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    monkeypatch.chdir(root)
    monkeypatch.delenv("DECOY_LIBRARY", raising=False)
    monkeypatch.delenv("DECOY_PROJECT", raising=False)
    return root


@pytest.fixture
def root(project: Path) -> Path:
    return project / DECOY_DIR


def _cli(*args: str) -> Any:
    return runner.invoke(app, ["library", *args])


def _snapshot(folder: Path) -> dict[str, bytes | None]:
    return {
        p.relative_to(folder).as_posix(): (p.read_bytes() if p.is_file() else None)
        for p in sorted(folder.rglob("*"))
        if not p.is_symlink()
    }


def _put(root: Path, *envs: Any) -> list[str]:
    library = open_library(root)
    return [library.put(e).id for e in envs]


def _old_samples(root: Path, count: int) -> list[str]:
    return _put(root, *(sample(n, 1) for n in range(count)))


# -- V1 1: clean ---------------------------------------------------------------------------------


@posix_only
def test_clean_never_follows_a_scratch_linked_to_the_library(root: Path) -> None:
    ids = _old_samples(root, 2)
    before = _snapshot(root / "library")
    (root / "scratch").symlink_to(root / "library", target_is_directory=True)
    result = _cli("clean", "--yes")
    assert result.exit_code == EXIT_RUNTIME, result.output
    assert "library_path_unsafe" in result.output
    assert _snapshot(root / "library") == before
    assert [open_library(root).get(i).id for i in ids] == ids


@posix_only
def test_clean_never_follows_a_scratch_linked_to_the_project(project: Path, root: Path) -> None:
    _old_samples(root, 1)
    (project / "keep.txt").write_bytes(b"the user's file")
    before = _snapshot(project / ".git")
    (root / "scratch").symlink_to(project, target_is_directory=True)
    result = _cli("clean", "--yes")
    assert result.exit_code == EXIT_RUNTIME, result.output
    assert (project / "keep.txt").read_bytes() == b"the user's file"
    assert _snapshot(project / ".git") == before


@posix_only
def test_clean_removes_a_link_inside_scratch_and_not_its_target(root: Path, tmp_path: Path) -> None:
    _old_samples(root, 1)
    outside = tmp_path / "outside"
    (outside / "sub").mkdir(parents=True)
    (outside / "sub" / "rows.csv").write_bytes(b"the user's rows")
    before = _snapshot(outside)
    scratch = root / "scratch"
    scratch.mkdir(mode=0o700)
    (scratch / "job").mkdir()
    (scratch / "job" / "part.csv").write_bytes(b"a")
    (scratch / "out").symlink_to(outside, target_is_directory=True)
    result = _cli("clean", "--yes")
    assert result.exit_code == EXIT_OK, result.output
    assert not os.path.lexists(scratch / "out") and not (scratch / "job").exists()
    assert _snapshot(outside) == before


# -- V1 2: prune fails closed ---------------------------------------------------------------------


def test_a_ref_with_a_bom_still_protects_its_record(root: Path) -> None:
    ids = _old_samples(root, 2)
    assert _cli("ref", "sample-run/main", ids[0], "--library", str(root)).exit_code == 0
    ref = root / "library" / "refs" / "sample-run" / "main"
    ref.write_bytes(b"\xef\xbb\xbf" + ref.read_bytes())  # saved by an editor that adds a BOM
    result = _cli("prune", "--keep-last", "0", "--yes")
    assert result.exit_code == EXIT_OK, result.output
    assert object_path(root, ids[0]).exists()
    assert not object_path(root, ids[1]).exists()  # control: the unprotected one went


def test_an_unreadable_ref_makes_prune_refuse(root: Path) -> None:
    ids = _old_samples(root, 2)
    refs = root / "library" / "refs" / "sample-run"
    refs.mkdir(parents=True)
    (refs / "main").write_bytes(ids[0].encode() + b"\n" + b" " * 200)  # over the ref cap
    preview = _cli("prune", "--keep-last", "0")
    assert preview.exit_code == EXIT_OK and "1 entr" in preview.output, preview.output
    result = _cli("prune", "--keep-last", "0", "--yes")
    assert result.exit_code == EXIT_RUNTIME, result.output
    assert "library_unexplained_entries" in result.output
    assert all(object_path(root, i).exists() for i in ids)


def test_an_unreadable_kept_record_makes_prune_refuse(root: Path) -> None:
    base = _put(root, sample(1, 1))[0]
    linker = _put(
        root, run_result(2, "succeeded", [table(0, "orders", 3)], links=[("baseline", base)])
    )[0]
    object_path(root, linker).write_bytes(b"{not a record")  # no index row, still a root
    result = _cli("prune", "--kind", "sample-run", "--keep-last", "0", "--yes")
    assert result.exit_code == EXIT_RUNTIME, result.output
    assert "library_unexplained_entries" in result.output
    assert object_path(root, base).exists()


# -- V1 3: prune never deletes through a link -----------------------------------------------------


@posix_only
def test_prune_never_deletes_through_a_linked_objects_folder(root: Path, tmp_path: Path) -> None:
    other = tmp_path / "other" / DECOY_DIR
    other.parent.mkdir()
    theirs = _old_samples(other, 2)
    before = _snapshot(other)
    _old_samples(root, 1)
    objects = root / "library" / "objects"
    objects.rename(root / "library" / "objects.moved")
    objects.symlink_to(other / "library" / "objects", target_is_directory=True)
    result = _cli("prune", "--keep-last", "0", "--yes")
    assert result.exit_code == EXIT_RUNTIME, result.output
    assert "library_path_unsafe" in result.output
    assert _snapshot(other) == before
    assert all(object_path(other, i).exists() for i in theirs)


# -- V1 4: export placement -----------------------------------------------------------------------


def test_export_into_the_library_is_refused(root: Path) -> None:
    ids = _old_samples(root, 1)
    assert _cli("ref", "sample-run/main", ids[0], "--library", str(root)).exit_code == 0
    ref = root / "library" / "refs" / "sample-run" / "main"
    before = ref.read_bytes()
    for out in (ref, object_path(root, ids[0]), root / "scratch" / "x.jsonl"):
        result = _cli("export", "-o", str(out))
        assert result.exit_code == EXIT_USAGE, (out, result.output)
        assert "export_destination_unsafe" in result.output
    assert ref.read_bytes() == before
    assert open_library(root).get(ids[0]).id == ids[0]


@posix_only
def test_export_through_a_final_symlink_is_refused(root: Path, tmp_path: Path) -> None:
    _old_samples(root, 1)
    victim = tmp_path / "bashrc"
    victim.write_bytes(b"the user's shell setup")
    link = tmp_path / "export.jsonl"
    link.symlink_to(victim)
    result = _cli("export", "-o", str(link))
    assert result.exit_code == EXIT_USAGE, result.output
    assert victim.read_bytes() == b"the user's shell setup"


# -- V1 5: --ref with filters ---------------------------------------------------------------------


@pytest.mark.parametrize("extra", [("--kind", "scan-set"), ("--since", "2026-01-01")])
def test_ref_with_a_filter_is_a_usage_error(root: Path, tmp_path: Path, extra: tuple) -> None:
    ids = _old_samples(root, 1)
    out = tmp_path / "e.jsonl"
    result = _cli("export", "-o", str(out), "--ref", ids[0], *extra)
    assert result.exit_code == EXIT_USAGE, result.output
    assert not out.exists()


# -- V1 6 and 7: export fails closed --------------------------------------------------------------


def test_a_record_this_version_cannot_verify_makes_export_fail_closed(
    root: Path, tmp_path: Path
) -> None:
    _old_samples(root, 1)
    raw = json.loads(records.encode(sample(5, 1)))
    raw["record_schema"] = "decoy-record/v2"
    raw["id"] = records.record_id(raw)
    target = object_path(root, raw["id"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(records.canonical_bytes(raw))
    for extra in ((), ("--keep-paths",)):
        out = tmp_path / f"e{len(extra)}.jsonl"
        result = _cli("export", "-o", str(out), *extra)
        assert result.exit_code == EXIT_RUNTIME, result.output
        assert "library_unexplained_entries" in result.output
        assert not out.exists()


def test_an_unreadable_refs_folder_is_a_coded_refusal(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _old_samples(root, 1)
    assert _cli("ref", "sample-run/main", ids[0], "--library", str(root)).exit_code == 0
    kind_dir = root / "library" / "refs" / "sample-run"
    real = os.scandir

    def scandir(path: object = ".") -> object:
        if Path(str(path)) == kind_dir:
            raise PermissionError(13, "Permission denied", str(path))
        return real(path)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "scandir", scandir)
    result = _cli("export", "-o", str(tmp_path / "e.jsonl"))
    assert result.exit_code == EXIT_RUNTIME, result.output
    assert "internal error" not in result.output
    assert "library_unexplained_entries" in result.output


# -- DESIGN 9 -------------------------------------------------------------------------------------


def test_prune_and_export_share_one_closure_walk(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from decoy.cli.library import _index

    ids = _old_samples(root, 2)
    calls: list[str] = []
    real = _index.reachable

    def spy(roots: Any, rows: Any) -> set[str]:
        calls.append("walk")
        return real(roots, rows)

    monkeypatch.setattr(_index, "reachable", spy)
    assert _cli("prune", "--keep-last", "0").exit_code == EXIT_OK
    assert _cli("export", "-o", str(tmp_path / "e.jsonl"), "--ref", ids[0]).exit_code == EXIT_OK
    assert len(calls) == 2
