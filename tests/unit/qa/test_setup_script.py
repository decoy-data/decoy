"""AT-10 (setup script): filesystem behavior without root, plus a static guard on raw root writes.

`QA_SETUP_TEST_ROOT` moves the QA root under a temp folder and skips users, groups, chown and
mounts, so staging, replacing, source checks and modes run for real. Real OS users and mounts
are probed in slice S3. The plan's rules are in section 10a."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
from tests.unit.qa._paths import QA_SCRIPTS

SCRIPT = QA_SCRIPTS / "setup-testers.sh"
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None or os.name != "posix", reason="needs bash on POSIX")
ALLOWED_FUNCTIONS = ("qa_root_dir", "qa_stage_swap", "qa_new_file")


class Env:
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path.resolve() / "root"
        self.qa = self.root / "var" / "lib" / "decoy-qa"
        self.src = self.qa / "src"
        self.bundle = self.src / "bundle"
        self.docs = self.src / "docs"
        self.corpus = self.src / "corpus"
        (self.bundle / "bin").mkdir(parents=True)
        (self.bundle / "bin" / "decoy").write_text("#!/bin/sh\n")
        (self.bundle / "VERSION").write_text("1.2.3\n")
        self.docs.mkdir()
        (self.docs / "index.md").write_text("docs\n")
        (self.corpus / "item").mkdir(parents=True)
        (self.corpus / "item" / "data.csv").write_text("x")
        self.src.chmod(0o755)

    def home(self, slug: str = "p1") -> Path:
        return self.qa / "testers" / f"qatester-{slug}"

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


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


def test_setup_builds_each_tester_layout_with_the_plan_modes(env: Env) -> None:
    done = env.run()
    assert done.returncode == 0, done.stderr
    t = env.home()
    assert (t / "bundle" / "bin" / "decoy").is_file()
    assert (t / "docs" / "index.md").read_text() == "docs\n"
    assert _mode(t) == 0o750 and _mode(t / "work") == 0o700
    assert not (t / "work" / "inbox").exists(), "the tester makes its own inbox"
    assert not (t / "secret").exists(), "the secret is for p3 only"
    secret = env.home("p3") / "secret" / "ci-secret"
    assert _mode(secret) == 0o640 and secret.stat().st_size > 20
    assert _mode(env.home("p3") / "secret") == 0o750
    for path in (t / "bundle").rglob("*"):
        assert _mode(path) & 0o007 == 0 and _mode(path) & 0o022 == 0, path
    assert not list(t.glob(".new.*")) and not list(t.glob("*.stage.*"))


def test_the_corpus_is_a_staged_copy_with_no_access_for_other(env: Env) -> None:
    (env.corpus / "item" / "data.csv").chmod(0o666)
    (env.corpus / "item").chmod(0o777)
    assert env.run().returncode == 0
    out = env.qa / "corpus"
    assert (out / "item" / "data.csv").read_text() == "x"
    for path in [out, *out.rglob("*")]:
        assert _mode(path) & 0o027 == 0, f"{path} is writable by group or open to other"
    assert _mode(out / "item" / "data.csv") & 0o007 == 0


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


def test_a_rerun_never_changes_the_tester_owned_work_folder(env: Env) -> None:
    assert env.run().returncode == 0
    work = env.home() / "work"
    (work / "keep.txt").write_text("tester data")
    assert env.run().returncode == 0
    assert (work / "keep.txt").read_text() == "tester data"
    work.chmod(0o755)
    done = env.run()
    assert done.returncode != 0 and "wrong owner or mode" in done.stderr


def test_a_symlink_or_hardlink_planted_as_the_secret_is_not_followed(
    env: Env, tmp_path: Path
) -> None:
    assert env.run().returncode == 0
    outside = tmp_path / "outside.txt"
    outside.write_text("precious")
    outside.chmod(0o644)
    secret = env.home("p3") / "secret" / "ci-secret"
    secret.unlink()
    os.link(outside, secret)  # a "tester" with write access plants a hardlink
    assert env.run().returncode == 0
    assert outside.read_text() == "precious" and _mode(outside) == 0o644
    secret.unlink()
    secret.symlink_to(outside)
    done = env.run()
    assert done.returncode != 0 and "symlink" in done.stderr
    assert outside.read_text() == "precious" and _mode(outside) == 0o644


def test_a_planted_symlink_for_a_tester_tree_is_refused_and_nothing_goes_through_it(
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
def test_a_source_outside_the_qa_src_folder_is_refused(
    env: Env, tmp_path: Path, which: str
) -> None:
    elsewhere = tmp_path.resolve() / "app" / "secrets"
    elsewhere.mkdir(parents=True)
    done = env.run(**{which: elsewhere})
    assert done.returncode != 0 and "must be under" in done.stderr
    assert not env.home().exists()


@pytest.mark.parametrize("which", ["bundle", "docs", "corpus"])
def test_a_symlinked_source_root_is_refused(env: Env, which: str) -> None:
    link = env.src / "link"
    link.symlink_to(env.docs)
    done = env.run(**{which: link})
    assert done.returncode != 0 and "symlink" in done.stderr


@pytest.mark.parametrize("bad", ["/", "/tmp", "relative/path", "src/bundle/../bundle"])
def test_broad_or_relative_sources_are_refused(env: Env, bad: str) -> None:
    assert env.run(bundle=bad).returncode != 0


def test_a_source_file_with_two_links_is_refused(env: Env, tmp_path: Path) -> None:
    other = tmp_path / "other-name"
    os.link(env.bundle / "bin" / "decoy", other)
    done = env.run()
    assert done.returncode != 0 and "more than one link" in done.stderr
    assert not env.home().exists()


def test_a_bundle_decoy_symlink_pointing_outside_the_bundle_is_refused(env: Env) -> None:
    (env.bundle / "bin" / "decoy").unlink()
    (env.bundle / "bin" / "decoy").symlink_to("/bin/sh")
    done = env.run()
    assert done.returncode != 0 and "points outside" in done.stderr


def test_a_relative_symlink_inside_the_bundle_is_allowed(env: Env) -> None:
    (env.bundle / "bin" / "decoy-real").write_text("x")
    (env.bundle / "bin" / "decoy2").symlink_to("decoy-real")
    assert env.run().returncode == 0
    assert (env.home() / "bundle" / "bin" / "decoy2").is_symlink()


def test_overlapping_sources_are_refused(env: Env) -> None:
    assert env.run(docs=env.bundle / "bin").returncode != 0


def test_a_group_writable_src_folder_is_refused(env: Env) -> None:
    env.src.chmod(0o775)
    done = env.run()
    assert done.returncode != 0 and "writable" in done.stderr


def test_the_dry_run_changes_nothing(env: Env) -> None:
    argv = [str(BASH), str(SCRIPT), "--bundle", str(env.bundle), "--docs", str(env.docs)]
    done = subprocess.run(
        [*argv, "--corpus", str(env.corpus)],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "QA_SETUP_TEST_ROOT": ""},
    )
    # Without the test root the source check fails first on this machine, so nothing changes.
    assert done.returncode != 0
    assert not (env.qa / "testers").exists()


# ---- Static guard: raw root writes outside the three functions ----

RAW = re.compile(r"(?<![\w-])(mkdir|chown|chmod|cp|touch|mv|mktemp|rm|ln|install|tee)(?![\w-])")
REDIRECT = re.compile(r"(?<![0-9&])>>?(?!&|\s*/dev/null)")


def raw_root_writes(text: str) -> list[str]:
    """Lines that change the file system outside qa_root_dir, qa_stage_swap and qa_new_file."""
    hits: list[str] = []
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(rf"({'|'.join(ALLOWED_FUNCTIONS)})\(\) \{{", stripped):
            inside = True
            continue
        if inside:
            if line == "}":
                inside = False
            continue
        if not stripped or stripped.startswith("#"):
            continue
        code = re.sub(r'"[^"]*"', '""', stripped)  # words inside messages do not count
        code = re.sub(r"2> */dev/null|> */dev/null|2>&1|>&2", "", code)
        if RAW.search(code) or REDIRECT.search(code):
            hits.append(stripped)
    return hits


def test_the_script_has_no_raw_root_writes_outside_the_three_functions() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert raw_root_writes(text) == []
    assert "chown -R" not in text and "chown -hR" not in text
    assert "—" not in text


@pytest.mark.parametrize(
    "bypass",
    [
        'mkdir -p "$t/inbox"',
        'chmod 0777 "$t/work"',
        'chown -R "$user" "$t"',
        'cp -R "$BUNDLE" "$t/bundle"',
        'touch "$t/fault/.qa-bounded"',
        'mv "$stage" "$dest"',
        'echo x > "$t/secret/ci-secret"',
        "echo x >> /etc/fstab",
        'ln -s "$CORPUS" "$t/corpus"',
    ],
)
def test_a_planted_bypass_is_caught_by_the_guard(bypass: str) -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    planted = text.replace('echo "done.', f'{bypass}\necho "done.')
    assert planted != text
    assert raw_root_writes(planted) == [bypass]


def test_the_guard_accepts_messages_and_dev_null_redirects() -> None:
    assert raw_root_writes('die "a mkdir or chmod word in a message" >&2\nfoo 2> /dev/null\n') == []
