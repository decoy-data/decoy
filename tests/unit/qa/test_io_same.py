"""`publish_or_same`: the retry primitive, and the executable mode for launcher-owned shims."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from scripts.qa import io as qio


def test_identical_bytes_count_as_done_and_other_bytes_are_refused(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    assert qio.publish_or_same(target, b"one") is True
    assert qio.publish_or_same(target, b"one") is False
    with pytest.raises(qio.AlreadyPublished) as err:
        qio.publish_or_same(target, b"two-secret")
    assert "two-secret" not in str(err.value) and err.value.__context__ is None
    assert target.read_bytes() == b"one"
    assert [p.name for p in tmp_path.iterdir()] == ["a.txt"]


def test_a_symlink_at_the_target_is_not_read_through(tmp_path: Path) -> None:
    (tmp_path / "real.txt").write_bytes(b"one")
    (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")
    with pytest.raises(qio.AlreadyPublished):
        qio.publish_or_same(tmp_path / "link.txt", b"one")


def test_an_executable_private_file(tmp_path: Path) -> None:
    target = tmp_path / "shim"
    qio.publish_private_once(target, b"#!/bin/sh\n", mode=qio.PRIVATE_EXEC)
    assert stat.S_IMODE(target.stat().st_mode) == 0o700


def test_a_fifo_a_directory_and_a_loose_mode_file_are_refused_not_hung(tmp_path: Path) -> None:
    import os

    os.mkfifo(tmp_path / "fifo")
    (tmp_path / "dir").mkdir()
    loose = tmp_path / "loose"
    loose.write_bytes(b"one")
    loose.chmod(0o644)
    for name in ("fifo", "dir", "loose"):
        with pytest.raises(qio.AlreadyPublished):
            qio.publish_or_same(tmp_path / name, b"one")
