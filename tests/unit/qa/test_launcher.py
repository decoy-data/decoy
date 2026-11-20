"""AT-10 (launcher): command construction on Linux and macOS, tester-scoped ids, node-local
capture and a hand-back of counts and ids only. The real OS-user probe is slice S3."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.unit.qa._paths import QA_SCRIPTS, load_qa_module

launch = load_qa_module("launch")


def _plain_writer(path: Path, data: bytes) -> None:
    """Stand-in for scripts/qa/io.py publish_private_once: create once or raise."""
    with open(path, "xb") as fh:  # test double, not QA tooling
        fh.write(data)


def _cmd(system: str, tmp_path: Path, slug: str = "p1", ids: tuple[str, ...] = ("f-p1-aaa",)):
    return launch.build_command(
        system=system,
        slug=slug,
        agent_argv=["agent", "--brief", "b.md"],
        pass_dir=tmp_path / "pass",
        capture_path=tmp_path / "capture.log",
        ids=ids,
        findings_tool="/opt/decoy-qa/findings.py",
    )


@pytest.mark.parametrize(("system", "home_root"), [("linux", "/home"), ("darwin", "/Users")])
def test_the_command_runs_the_agent_as_the_tester_user_with_a_clean_env(
    system: str, home_root: str, tmp_path: Path
) -> None:
    cmd = _cmd(system, tmp_path)
    assert cmd[cmd.index("sudo") :][:6] == ["sudo", "-n", "-u", "qatester-p1", "-H", "--"]
    home = f"{home_root}/qatester-p1"
    assert "env" in cmd and "-i" in cmd
    assert f"HOME={home}" in cmd
    assert f"DECOY_HOME={home}/.decoy-home" in cmd
    assert cmd[-3:] == ["agent", "--brief", "b.md"]


def test_the_linux_and_macos_commands_differ_in_home_and_path(tmp_path: Path) -> None:
    linux, mac = _cmd("linux", tmp_path), _cmd("darwin", tmp_path)
    assert linux != mac
    assert any(a.startswith("PATH=") and "/opt/homebrew" in a for a in mac)
    assert not any("/opt/homebrew" in a for a in linux)


def test_an_unknown_system_is_refused(tmp_path: Path) -> None:
    with pytest.raises(launch.LaunchError):
        _cmd("windows", tmp_path)


@pytest.mark.parametrize("slug", ["", "P1", "p1;rm", "../p1", "p1 ", "x" * 40])
def test_a_bad_tester_slug_is_refused(slug: str, tmp_path: Path) -> None:
    with pytest.raises(launch.LaunchError):
        _cmd("linux", tmp_path, slug=slug)


def test_the_environment_carries_ids_and_the_findings_tool_and_no_host_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SLACK_TOKEN", "do-not-pass")
    cmd = _cmd("linux", tmp_path, ids=("f-p1-aaa", "f-p1-bbb"))
    assert "QA_FINDING_IDS=f-p1-aaa,f-p1-bbb" in cmd
    assert "QA_FINDINGS_TOOL=/opt/decoy-qa/findings.py" in cmd
    assert "QA_TESTER=p1" in cmd
    assert not any("do-not-pass" in a or "SLACK" in a for a in cmd)


def test_stdout_and_stderr_go_to_the_node_local_capture_file_by_shell_redirect(
    tmp_path: Path,
) -> None:
    cmd = _cmd("linux", tmp_path)
    assert cmd[:2] == ["sh", "-c"]
    assert ">>" in cmd[2] and "2>&1" in cmd[2]
    assert cmd[3] == str(tmp_path / "capture.log")


def test_ids_are_tester_scoped_opaque_and_unique(tmp_path: Path) -> None:
    pass_dir = tmp_path / "pass"
    a = launch.allocate_ids(pass_dir, "p1", 5, writer=_plain_writer)
    b = launch.allocate_ids(pass_dir, "p2", 5, writer=_plain_writer)
    assert len(set(a) | set(b)) == 10
    assert all(i.startswith("f-p1-") for i in a)
    assert all(i.startswith("f-p2-") for i in b)
    assert all("qamark" not in i for i in a + b)


def test_an_id_collision_is_retried_not_reissued(tmp_path: Path) -> None:
    pass_dir = tmp_path / "pass"
    tokens = iter(["aaaa", "aaaa", "bbbb"])
    ids = launch.allocate_ids(pass_dir, "p1", 2, writer=_plain_writer, token=lambda: next(tokens))
    assert ids == ["f-p1-aaaa", "f-p1-bbbb"]


def test_the_writer_is_called_for_every_id_and_nothing_else_writes(tmp_path: Path) -> None:
    calls: list[Path] = []

    def spy(path: Path, data: bytes) -> None:
        calls.append(path)
        _plain_writer(path, data)

    ids = launch.allocate_ids(tmp_path / "pass", "p3", 3, writer=spy)
    assert [p.name for p in calls] == ids


def test_handback_is_counts_and_ids_only_and_never_reads_record_contents(
    tmp_path: Path,
) -> None:
    pass_dir = tmp_path / "pass"
    ids = launch.allocate_ids(pass_dir, "p1", 3, writer=_plain_writer)
    findings = pass_dir / "findings"
    findings.mkdir()
    (findings / f"{ids[0]}.toml").write_text("actual = 'SECRET-CELL-VALUE'\n")
    (findings / "f-p2-zzzz.toml").write_text("x = 1\n")  # another tester's record
    text = launch.handback(pass_dir, "p1", exit_code=0)
    assert text == f"tester=p1 findings=1 issued=3 exit=0 ids={ids[0]}"
    assert "SECRET" not in text


def test_handback_with_no_findings_has_empty_ids(tmp_path: Path) -> None:
    pass_dir = tmp_path / "pass"
    launch.allocate_ids(pass_dir, "p5", 2, writer=_plain_writer)
    assert launch.handback(pass_dir, "p5", exit_code=130) == (
        "tester=p5 findings=0 issued=2 exit=130 ids="
    )


def test_launch_runs_the_built_command_and_returns_only_the_handback(tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def fake_run(argv: list[str]) -> int:
        seen.append(argv)
        return 0

    out = launch.launch(
        system="linux",
        slug="p2",
        agent_argv=["agent"],
        pass_dir=tmp_path / "pass",
        id_count=2,
        findings_tool="/opt/decoy-qa/findings.py",
        writer=_plain_writer,
        runner=fake_run,
    )
    assert len(seen) == 1 and "qatester-p2" in seen[0]
    assert out.startswith("tester=p2 findings=0 issued=2 exit=0")
    assert (tmp_path / "pass" / "capture" / "p2.log").exists()


def test_the_launcher_does_not_create_users_or_open_files_for_writing() -> None:
    source = (QA_SCRIPTS / "launch.py").read_text()
    for banned in (
        "useradd",
        "dscl",
        "adduser",
        "sysadminctl",
        "open(",
        "write_text",
        "write_bytes",
    ):
        assert banned not in source, banned


def test_the_launcher_imports_no_private_product_module() -> None:
    source = (QA_SCRIPTS / "launch.py").read_text()
    assert "import decoy" not in source and "from decoy" not in source
    assert source.count("\n") < 400
