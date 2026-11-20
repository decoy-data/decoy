"""AT-10 (setup script): filesystem behavior without root. `QA_SETUP_TEST_ROOT` keeps every path
under a temp folder and skips users, groups, chown and mounts, so staging, replacing and modes
run for real. Real OS users and mounts are probed in slice S3."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
from tests.unit.qa._paths import QA_SCRIPTS

SCRIPT = QA_SCRIPTS / "setup-testers.sh"
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None or os.name != "posix", reason="needs bash on POSIX")


class Env:
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path.resolve() / "root"
        self.bundle = tmp_path.resolve() / "src" / "bundle"
        self.docs = tmp_path.resolve() / "src" / "docs"
        self.corpus = tmp_path.resolve() / "data" / "corpus"
        (self.bundle / "bin").mkdir(parents=True)
        (self.bundle / "bin" / "decoy").write_text("#!/bin/sh\n")
        self.docs.mkdir(parents=True)
        (self.docs / "index.md").write_text("docs\n")
        self.root.mkdir()
        self.corpus.parent.mkdir()

    def home(self, slug: str = "p1") -> Path:
        return self.root / "home" / f"qatester-{slug}"

    def run(self, **override: Path | str) -> subprocess.CompletedProcess[str]:
        args = {"bundle": self.bundle, "docs": self.docs, "corpus": self.corpus} | override
        argv = [str(BASH), str(SCRIPT)]
        for key, value in args.items():
            argv += [f"--{key}", str(value)]
        env = {**os.environ, "QA_SETUP_TEST_ROOT": str(self.root)}
        return subprocess.run(argv, env=env, capture_output=True, text=True, check=False)


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(tmp_path)


def test_setup_builds_each_home_with_a_locked_bundle_docs_link_and_workspace(env: Env) -> None:
    done = env.run()
    assert done.returncode == 0, done.stderr
    home = env.home()
    assert (home / "bundle" / "bin" / "decoy").is_file()
    assert (home / "docs" / "index.md").read_text() == "docs\n"
    assert (home / "corpus").is_symlink() and (home / "corpus").resolve() == env.corpus
    assert stat.S_IMODE(home.stat().st_mode) == 0o750
    assert stat.S_IMODE((home / "work").stat().st_mode) == 0o700
    assert stat.S_IMODE((home / "secret" / "ci-secret").stat().st_mode) == 0o600
    assert (home / "secret" / "ci-secret").stat().st_size > 20
    assert not (env.home("p1") / "fault").exists(), "the fault volume is for p5 on real nodes only"
    for path in (home / "bundle").rglob("*"):
        assert stat.S_IMODE(path.stat().st_mode) & 0o027 == 0, path


def test_the_corpus_tree_has_no_access_for_other(env: Env) -> None:
    assert env.run().returncode == 0  # makes the folder and its marker
    (env.corpus / "marker-owner-file").write_text("x")
    (env.corpus / "marker-owner-file").chmod(0o666)
    sub = env.corpus / "item"
    sub.mkdir()
    (sub / "data.csv").write_text("x")
    sub.chmod(0o777)
    (sub / "data.csv").chmod(0o644)
    assert env.run().returncode == 0
    for path in [env.corpus, *env.corpus.rglob("*")]:
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode & 0o007 == 0, f"{path} has other bits {oct(mode)}"
        assert mode & 0o020 == 0, f"{path} is group writable {oct(mode)}"


def test_a_second_setup_drops_a_file_removed_from_the_source(env: Env) -> None:
    (env.bundle / "bin" / "old-tool").write_text("x")
    assert env.run().returncode == 0
    assert (env.home() / "bundle" / "bin" / "old-tool").exists()
    (env.bundle / "bin" / "old-tool").unlink()
    (env.docs / "index.md").unlink()
    assert env.run().returncode == 0
    assert not (env.home() / "bundle" / "bin" / "old-tool").exists()
    assert not (env.home() / "docs" / "index.md").exists()
    assert (env.home() / "bundle" / "bin" / "decoy").exists()
    assert not [p for p in env.home().iterdir() if p.name.startswith(".stage")]


def test_a_planted_symlink_in_a_tester_home_is_refused_and_nothing_is_written_through_it(
    env: Env, tmp_path: Path
) -> None:
    assert env.run().returncode == 0
    victim = tmp_path / "victim"
    victim.mkdir()
    shutil.rmtree(env.home() / "bundle")
    (env.home() / "bundle").symlink_to(victim)
    done = env.run()
    assert done.returncode != 0 and "symlink" in done.stderr
    assert list(victim.iterdir()) == []


@pytest.mark.parametrize("which", ["bundle", "docs", "corpus"])
def test_a_symlinked_source_root_is_refused(env: Env, tmp_path: Path, which: str) -> None:
    real = tmp_path.resolve() / "real"
    real.mkdir()
    link = tmp_path.resolve() / "link"
    link.symlink_to(real)
    done = env.run(**{which: link})
    assert done.returncode != 0 and "symlink" in done.stderr


def test_a_symlink_in_the_middle_of_a_root_path_is_refused(env: Env, tmp_path: Path) -> None:
    link = tmp_path.resolve() / "via"
    link.symlink_to(env.bundle.parent)
    assert env.run(bundle=link / "bundle").returncode != 0


@pytest.mark.parametrize("bad", ["/", "/tmp", "relative/path", "bundle/../bundle"])
def test_broad_or_relative_roots_are_refused(env: Env, bad: str) -> None:
    for which in ("bundle", "corpus"):
        assert env.run(**{which: bad}).returncode != 0
    assert not (env.root / "home" / "qatester-p1" / "bundle").exists()


def test_overlapping_roots_are_refused(env: Env) -> None:
    assert env.run(docs=env.bundle / "bin").returncode != 0
    assert env.run(corpus=env.bundle.parent).returncode != 0


def test_a_corpus_folder_with_foreign_files_and_no_marker_is_refused(env: Env) -> None:
    env.corpus.mkdir()
    (env.corpus / "someone-elses-file").write_text("x")
    before = (env.corpus / "someone-elses-file").stat().st_mode
    done = env.run()
    assert done.returncode != 0 and "not empty" in done.stderr
    assert (env.corpus / "someone-elses-file").stat().st_mode == before


def test_the_dry_run_changes_nothing(env: Env) -> None:
    argv = [str(BASH), str(SCRIPT), "--bundle", str(env.bundle), "--docs", str(env.docs)]
    done = subprocess.run(
        [*argv, "--corpus", str(env.corpus)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0 and "dry run" in done.stdout
    assert not env.corpus.exists()
    assert not list(env.root.iterdir())


def test_the_script_never_chowns_recursively_and_has_a_root_check() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "chown -R" not in text and "chown -hR" not in text
    assert "id -u" in text and "--apply" in text
    assert "—" not in text
