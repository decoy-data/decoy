"""AT-10 (launcher): command construction, workspace and PATH behavior, probe gate, tester-scoped
ids, capture through the central writer, and the counts-and-ids hand-back with a real exit
status. The OS-user checkout probe itself is slice S3."""

from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

import pytest
from tests.unit.qa._paths import QA_SCRIPTS, load_qa_module

launch = load_qa_module("launch")


def _publish(path: Path, data: bytes) -> None:
    """Stand-in for io.publish_private_once: create once or raise."""
    with open(path, "xb") as fh:  # test double, not QA tooling
        fh.write(data)


def _mkdir(path: Path, mode: int = 0o700) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(mode)


def _capture(path: Path) -> int:
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)


IO = launch.IoApi(_publish, _mkdir, _capture)


class Node:
    """A fake node: probe marker present, `decoy` resolving in the bundle, scripted probes."""

    def __init__(self, tmp_path: Path, *, resolves: bool = True, marker: bool = True) -> None:
        self.tmp = tmp_path
        self.marker_root = tmp_path / "probes"
        if marker:
            m = launch.probe_marker_path("node1", "p1", self.marker_root)
            m.parent.mkdir(parents=True)
            m.write_text("")
        self.resolves = resolves
        self.calls: list[list[str]] = []
        self.inbox_listing = ""

    def probe(self, argv: list[str]) -> tuple[int, str]:
        self.calls.append(argv)
        tail = argv[argv.index("--") + 1 :]
        if "command -v decoy" in tail:
            home = tail[tail.index("-i") + 1].removeprefix("HOME=").removesuffix("/work")
            return (0, f"{home}/bundle/bin/decoy\n") if self.resolves else (1, "")
        if tail[-2:-1] == ["-1"] or "ls" in tail:
            return 0, self.inbox_listing
        return 0, ""

    def run(self, **kw):
        runner = kw.pop("runner", lambda argv, fd, text: 0)
        return launch.launch(
            system="linux",
            slug="p1",
            brief="p1-solo-developer",
            pass_dir=self.tmp / "pass",
            id_count=2,
            findings_tool="/opt/decoy-qa/findings.py",
            io=IO,
            runner=runner,
            probe=self.probe,
            node="node1",
            marker_root=self.marker_root,
            **kw,
        )


def _cmd(system: str = "linux", slug: str = "p1", **kw):
    return launch.build_command(
        system=system,
        slug=slug,
        agent_argv=["sh", "-c", "pwd"],
        pass_dir=Path("/var/lib/decoy-qa/pass-x"),
        ids=("f-p1-aaa",),
        findings_tool="/opt/decoy-qa/findings.py",
        **kw,
    )


@pytest.mark.parametrize(("system", "home_root"), [("linux", "/home"), ("darwin", "/Users")])
def test_the_command_runs_as_the_tester_user_with_the_bundle_first_on_path(
    system: str, home_root: str
) -> None:
    cmd = _cmd(system)
    assert cmd[:6] == ["sudo", "-n", "-u", "qatester-p1", "-H", "--"]
    home = f"{home_root}/qatester-p1"
    assert f"PATH={home}/bundle/bin:" in " ".join(cmd)
    assert f"HOME={home}/work" in cmd


def test_an_unknown_system_or_bad_slug_is_refused() -> None:
    with pytest.raises(launch.LaunchError):
        _cmd("windows")
    for slug in ("", "P1", "p1;rm", "../p1", "x" * 40):
        with pytest.raises(launch.LaunchError):
            _cmd(slug=slug)


def _inner(cmd: list[str]) -> list[str]:
    return cmd[cmd.index("env") :]


def test_the_agent_starts_in_the_tester_workspace_not_the_callers_folder(tmp_path: Path) -> None:
    root = tmp_path / "homes"
    (root / "qatester-p1" / "work").mkdir(parents=True)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    cmd = _cmd(home_root=str(root))
    done = subprocess.run(_inner(cmd), cwd=checkout, capture_output=True, text=True, check=True)
    assert Path(done.stdout.strip()).resolve() == (root / "qatester-p1" / "work").resolve()


def test_the_bundle_bin_is_first_on_the_clean_path(tmp_path: Path) -> None:
    root = tmp_path / "homes"
    (root / "qatester-p1" / "work").mkdir(parents=True)
    cmd = launch.build_command(
        system="linux",
        slug="p1",
        agent_argv=["sh", "-c", 'printf %s "$PATH"; printf " %s" "${SLACK_TOKEN-unset}"'],
        pass_dir=tmp_path,
        ids=(),
        findings_tool="x",
        home_root=str(root),
    )
    env = {**os.environ, "SLACK_TOKEN": "leak"}
    done = subprocess.run(_inner(cmd), capture_output=True, text=True, check=True, env=env)
    path, token = done.stdout.rsplit(" ", 1)
    assert path.split(":")[0] == f"{root}/qatester-p1/bundle/bin"
    assert token == "unset"


def test_the_secret_file_is_for_p3_only_and_never_in_argv_as_a_value() -> None:
    assert any(a.startswith("QA_SECRET_FILE=") for a in _cmd(slug="p3"))
    assert not any(a.startswith("QA_SECRET_FILE=") for a in _cmd(slug="p1"))


@pytest.mark.parametrize("bad", ["--mask-secret=abc", "--api-key", "TOKEN", "a b", "$(x)", "--x=1"])
def test_extra_agent_args_must_pass_the_allowlist(bad: str) -> None:
    with pytest.raises(launch.LaunchError):
        launch.check_agent_extras([bad])
    assert launch.check_agent_extras(["--model", "sonnet"]) == ["--model", "sonnet"]


def test_launch_refuses_without_the_s3_probe_marker(tmp_path: Path) -> None:
    node = Node(tmp_path, marker=False)
    with pytest.raises(launch.LaunchError, match="probe"):
        node.run()
    assert not (tmp_path / "pass").exists()


def test_launch_fails_closed_when_decoy_does_not_resolve_in_the_bundle(tmp_path: Path) -> None:
    node = Node(tmp_path, resolves=False)
    with pytest.raises(launch.LaunchError, match="bundle"):
        node.run(runner=lambda *a: pytest.fail("must not start"))


def test_pass_folders_have_the_right_modes_and_a_tester_inbox_is_made_by_the_tester(
    tmp_path: Path,
) -> None:
    node = Node(tmp_path)
    node.run()
    pass_dir = tmp_path / "pass"
    mode = lambda p: (pass_dir / p).stat().st_mode & 0o777  # noqa: E731
    assert mode("capture") == 0o700 and mode("issued") == 0o700
    assert mode("inbox") & 0o022 == 0 and mode(".") & 0o022 == 0, (
        "nothing is group or world writable"
    )
    mkdir_calls = [c for c in node.calls if "mkdir" in " ".join(c)]
    assert mkdir_calls and "qatester-p1" in mkdir_calls[0]


def test_ids_are_tester_scoped_opaque_unique_and_retried_on_collision(tmp_path: Path) -> None:
    (tmp_path / "issued").mkdir()
    tokens = iter(["aaaa", "aaaa", "bbbb"])
    ids = launch.allocate_ids(tmp_path, "p1", 2, publish=_publish, token=lambda: next(tokens))
    assert ids == ["f-p1-aaaa", "f-p1-bbbb"]


def test_the_capture_goes_through_the_writer_fd_and_the_tester_output_stays_in_it(
    tmp_path: Path,
) -> None:
    node = Node(tmp_path)

    def runner(argv: list[str], fd: int, text: str) -> int:
        assert "Mission" in text, "the brief goes in on stdin"
        assert not any("Mission" in a for a in argv)
        os.write(fd, b"tester said something with a value\n")
        return 0

    result = node.run(runner=runner)
    assert "value" not in result.line
    log = (tmp_path / "pass" / "capture" / "p1.log").read_bytes()
    assert log.startswith(b"tester said")
    assert (tmp_path / "pass" / "capture" / "p1.log").stat().st_mode & 0o777 == 0o600


def test_handback_is_counts_and_ids_only_and_never_reads_records(tmp_path: Path) -> None:
    node = Node(tmp_path)
    node.inbox_listing = ""
    first = node.run().line
    assert first.startswith("tester=p1 findings=0 issued=2 exit=0 ids=")
    assert (
        launch.handback("p1", ["f-p1-a", "f-p1-b"], ["f-p1-a.toml", "f-p2-z.toml"], exit_code=0)
        == "tester=p1 findings=1 issued=2 exit=0 ids=f-p1-a"
    )


def test_a_tester_exit_of_three_gives_a_nonzero_launcher_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    node = Node(tmp_path)
    result = node.run(runner=lambda *a: 3)
    assert result.exit_code == 3 and "exit=3" in result.line

    monkeypatch.setattr(launch, "launch", lambda **kw: result)
    code = launch.main(["p1", "--brief", "p1-solo-developer", "--pass-dir", str(tmp_path)])
    assert code != 0
    assert capsys.readouterr().out.strip() == result.line


def test_a_real_subprocess_exit_of_three_reaches_the_result(tmp_path: Path) -> None:
    root = tmp_path / "homes"
    (root / "qatester-p1" / "work").mkdir(parents=True)

    def real(argv: list[str], fd: int, text: str) -> int:
        # Drop the sudo prefix and swap the fixed agent argv for a shell that exits 3.
        inner = _inner(argv)
        assert inner[-2:] == ["claude", "-p"]
        return subprocess.run(
            [*inner[:-2], "sh", "-c", "exit 3"], stdout=fd, check=False
        ).returncode

    node = Node(tmp_path)
    assert node.run(runner=real, home_root=str(root)).exit_code == 3


def test_p5_without_a_bounded_volume_skips_the_disk_full_cell(tmp_path: Path) -> None:
    node = Node(tmp_path)
    m = launch.probe_marker_path("node1", "p5", node.marker_root)
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text("")
    skipping = launch.launch(
        system="linux", slug="p5", brief="p5-careless-user", pass_dir=tmp_path / "p5pass",
        id_count=1, findings_tool="x", io=IO, runner=lambda *a: 0,
        probe=lambda argv: (1, "") if "test" in argv else node.probe(argv),
        node="node1", marker_root=node.marker_root,
    )  # fmt: skip
    assert "skipped=disk-full" in skipping.line


def _calls(tree: ast.AST) -> list[str]:
    names = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            names.append(f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""))
    return names


def test_the_launcher_has_no_direct_file_writes_user_creation_or_product_imports() -> None:
    tree = ast.parse((QA_SCRIPTS / "launch.py").read_text())
    banned_calls = {
        "open",
        "mkdir",
        "makedirs",
        "write_text",
        "write_bytes",
        "touch",
        "copy",
        "copytree",
        "rmtree",
        "chmod",
        "chown",
    }
    assert banned_calls.isdisjoint(_calls(tree)), banned_calls & set(_calls(tree))
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            assert not any(a.name.split(".")[0] == "decoy" for a in n.names)
        if isinstance(n, ast.ImportFrom):
            assert (n.module or "").split(".")[0] != "decoy"
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            for word in ("useradd", "dscl", "adduser", "sysadminctl"):
                assert word not in n.value
    assert (QA_SCRIPTS / "launch.py").read_text().count("\n") < 400
