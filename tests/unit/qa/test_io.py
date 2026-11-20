"""The QA writer: 0600, create-once, atomic, and clean after an interruption."""

from __future__ import annotations

import os
import stat
import threading
from pathlib import Path

import pytest
from scripts.qa import io as qio


def test_publish_writes_a_private_file(tmp_path: Path) -> None:
    target = tmp_path / "a" / "rec.toml"
    qio.publish_private_once(target, b"hello")
    assert target.read_bytes() == b"hello"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert [p.name for p in target.parent.iterdir()] == ["rec.toml"]


def test_a_second_publish_is_refused_and_the_first_stays(tmp_path: Path) -> None:
    target = tmp_path / "rec.toml"
    qio.publish_private_once(target, b"first")
    with pytest.raises(qio.AlreadyPublished) as err:
        qio.publish_private_once(target, b"second-secret-text")
    assert target.read_bytes() == b"first"
    assert "second-secret-text" not in str(err.value)
    assert [p.name for p in tmp_path.iterdir()] == ["rec.toml"]


def test_an_interruption_leaves_no_target_and_a_retry_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "rec.toml"

    def interrupted(*_a: object, **_k: object) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as m:
        m.setattr(os, "link", interrupted)
        with pytest.raises(KeyboardInterrupt):
            qio.publish_private_once(target, b"x")
    assert list(tmp_path.iterdir()) == []
    qio.publish_private_once(target, b"retry")
    assert target.read_bytes() == b"retry"


def test_an_error_while_writing_leaves_nothing(tmp_path: Path) -> None:
    target = tmp_path / "rec.toml"
    with pytest.raises(RuntimeError), qio.staged_private(target) as staged:
        staged.write(b"partial")
        raise RuntimeError("boom")
    assert list(tmp_path.iterdir()) == []


def test_racing_writers_give_one_complete_record(tmp_path: Path) -> None:
    target = tmp_path / "rec.toml"
    outcomes: list[str] = []
    gate = threading.Barrier(8)

    def writer(i: int) -> None:
        gate.wait()
        try:
            qio.publish_private_once(target, f"writer-{i}".encode() * 1000)
            outcomes.append("won")
        except qio.AlreadyPublished:
            outcomes.append("lost")

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == ["lost"] * 7 + ["won"]
    body = target.read_bytes()
    assert len(body) in {len(f"writer-{i}") * 1000 for i in range(8)}
    assert len({body[i : i + 8] for i in range(0, len(body), 8)}) == 1
    assert [p.name for p in tmp_path.iterdir()] == ["rec.toml"]


def test_the_scratch_dir_is_private_and_removed() -> None:
    with qio.private_scratch_dir() as scratch:
        assert stat.S_IMODE(scratch.stat().st_mode) == 0o700
        kept = scratch
    assert not kept.exists()


def test_make_private_dir_sets_exact_mode_and_needs_a_parent(tmp_path: Path) -> None:
    old = os.umask(0o077)
    try:
        qio.make_private_dir(tmp_path / "d", 0o750)
    finally:
        os.umask(old)
    assert stat.S_IMODE((tmp_path / "d").stat().st_mode) == 0o750
    with pytest.raises(FileNotFoundError):
        qio.make_private_dir(tmp_path / "missing" / "d")


def test_make_private_dir_refuses_symlinks_and_other_existing_paths(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    (tmp_path / "link").symlink_to(real)
    with pytest.raises(FileExistsError):
        qio.make_private_dir(tmp_path / "link")
    wrong = tmp_path / "wrong"
    wrong.mkdir()
    wrong.chmod(0o755)
    with pytest.raises(FileExistsError):
        qio.make_private_dir(wrong)
    plain = tmp_path / "file"
    plain.write_bytes(b"")
    with pytest.raises(FileExistsError):
        qio.make_private_dir(plain)
    qio.make_private_dir(real)  # same owner and mode: accepted


def test_open_private_capture_is_create_once_0600_append(tmp_path: Path) -> None:
    target = tmp_path / "cap.out"
    fd = qio.open_private_capture(target)
    try:
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
        assert not os.get_inheritable(fd)
        os.write(fd, b"ab")
        os.write(fd, b"cd")
    finally:
        os.close(fd)
    assert target.read_bytes() == b"abcd"
    with pytest.raises(FileExistsError):
        qio.open_private_capture(target)


def test_open_private_capture_refuses_a_symlink_and_can_be_inheritable(tmp_path: Path) -> None:
    (tmp_path / "victim").write_bytes(b"keep")
    (tmp_path / "cap.out").symlink_to(tmp_path / "victim")
    with pytest.raises(OSError):
        qio.open_private_capture(tmp_path / "cap.out")
    assert (tmp_path / "victim").read_bytes() == b"keep"
    fd = qio.open_private_capture(tmp_path / "other.out", inheritable=True)
    try:
        assert os.get_inheritable(fd)
    finally:
        os.close(fd)


def test_a_crash_after_the_temp_write_and_before_the_link_leaves_no_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Crash(BaseException):  # stands in for a kill: nothing after the link call runs
        pass

    target = tmp_path / "rec.toml"
    seen: list[bool] = []

    def die(src: object, dst: object) -> None:
        seen.append(Path(str(dst)).exists())
        raise Crash

    with monkeypatch.context() as m:
        m.setattr(os, "link", die)
        with pytest.raises(Crash):
            qio.publish_private_once(target, b"complete")
    assert seen == [False]
    assert not target.exists()
    qio.publish_private_once(target, b"complete")
    assert target.read_bytes() == b"complete"


def test_the_target_is_never_visible_empty(tmp_path: Path) -> None:
    target = tmp_path / "rec.toml"
    with qio.staged_private(target) as staged:
        staged.write(b"x" * 1000)
        assert not target.exists()
        staged.publish()
    assert target.read_bytes() == b"x" * 1000


def test_missing_parents_are_made_private_one_level_at_a_time(tmp_path: Path) -> None:
    qio.publish_private_once(tmp_path / "a" / "b" / "rec", b"x")
    for level in (tmp_path / "a", tmp_path / "a" / "b"):
        assert stat.S_IMODE(level.stat().st_mode) == 0o700


def test_a_symlinked_parent_is_refused(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real)
    with pytest.raises(NotADirectoryError):
        qio.publish_private_once(tmp_path / "link" / "rec", b"x")
    with pytest.raises(NotADirectoryError):
        qio.publish_private_once(tmp_path / "link" / "sub" / "rec", b"x")
    assert list(real.iterdir()) == []


@pytest.fixture
def locked_umask():
    old = os.umask(0o777)
    yield
    os.umask(old)


def test_every_create_path_is_exact_under_umask_0777(tmp_path: Path, locked_umask: None) -> None:
    qio.publish_private_once(tmp_path / "a" / "b" / "rec", b"x")
    assert stat.S_IMODE((tmp_path / "a" / "b" / "rec").stat().st_mode) == 0o600
    for level in (tmp_path / "a", tmp_path / "a" / "b"):
        assert stat.S_IMODE(level.stat().st_mode) == 0o700
    qio.make_private_dir(tmp_path / "d", 0o750)
    assert stat.S_IMODE((tmp_path / "d").stat().st_mode) == 0o750
    fd = qio.open_private_capture(tmp_path / "cap.out")
    os.close(fd)
    assert stat.S_IMODE((tmp_path / "cap.out").stat().st_mode) == 0o600
    with qio.private_scratch_dir() as scratch:
        assert stat.S_IMODE(scratch.stat().st_mode) == 0o700


def test_a_capture_that_cannot_be_made_private_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(fd: int, mode: int) -> None:
        raise PermissionError("no chmod here")

    monkeypatch.setattr(os, "fchmod", refuse)
    with pytest.raises(PermissionError):
        qio.open_private_capture(tmp_path / "cap.out")
    assert list(tmp_path.iterdir()) == []


def test_safe_errors_carry_no_cause_or_context(tmp_path: Path) -> None:
    qio.publish_private_once(tmp_path / "rec", b"x")
    with pytest.raises(qio.AlreadyPublished) as first:
        qio.publish_private_once(tmp_path / "rec", b"y")
    (tmp_path / "plain").write_bytes(b"")
    with pytest.raises(FileExistsError) as second:
        qio.make_private_dir(tmp_path / "plain")
    for err in (first.value, second.value):
        assert err.__cause__ is None and err.__context__ is None
