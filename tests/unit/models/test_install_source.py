"""AT-C1c and AT-C1e: what `--from` accepts, and that pip reads only the private copy.

AT-C1c (class row 6): a source distribution, a directory holding one, a symlink, a symlink loop
and other non-wheel input are refused with `models.source_invalid` before any installer runs, and
every installer call carries `--only-binary :all:` (M-C1c drops it). AT-C1e (class row 7): a wheel
added to, or swapped in, the user's directory after the check is never installed (M-C1e points
`--find-links` at the user's directory).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from tests.unit.models._rig import make_rig, wheel

MODEL = "en_core_web_sm-3.8.0-py3-none-any.whl"
CLOSURE = ("spacy-3.8.18-cp310-cp310-manylinux_2_28_x86_64.whl", "click-8.5.1-py3-none-any.whl")


def _wheelhouse(root: Path) -> Path:
    for name in (MODEL, *CLOSURE):
        wheel(root, name, data=name.encode())
    return root


def _bad_source(kind: str, tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    if kind == "sdist":
        return wheel(src, "en_core_web_sm-3.8.0.tar.gz")
    if kind == "not_a_wheel":
        return wheel(src, "en_core_web_sm-3.8.0.zip")
    if kind == "dir_with_sdist":
        _wheelhouse(src)
        wheel(src, "evil-1.0.tar.gz")
        return src
    if kind == "dir_with_subdir":
        _wheelhouse(src)
        (src / "nested").mkdir()
        return src
    if kind == "empty_dir":
        return src
    if kind == "symlink":
        target = wheel(tmp_path / "elsewhere", MODEL)
        link = src / MODEL
        link.symlink_to(target)
        return link
    if kind == "dir_symlink":
        _wheelhouse(tmp_path / "real")
        link = tmp_path / "linked"
        link.symlink_to(tmp_path / "real", target_is_directory=True)
        return link
    if kind == "dir_with_symlink":
        _wheelhouse(src)
        (src / "extra-1.0-py3-none-any.whl").symlink_to(src / MODEL)
        return src
    if kind == "symlink_loop":
        a, b = src / "a.whl", src / "b.whl"
        a.symlink_to(b)
        b.symlink_to(a)
        return a
    if kind == "missing":
        return src / "nothing-here.whl"
    if kind == "dir_without_model":
        for name in CLOSURE:
            wheel(src, name)
        return src
    raise AssertionError(kind)


@pytest.mark.parametrize(
    "kind",
    [
        "sdist",
        "not_a_wheel",
        "dir_with_sdist",
        "dir_with_subdir",
        "empty_dir",
        "symlink",
        "dir_symlink",
        "dir_with_symlink",
        "symlink_loop",
        "missing",
        "dir_without_model",
    ],
)
def test_from_corpus_is_refused_before_any_installer_runs(
    kind: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    source = _bad_source(kind, tmp_path)
    code, doc = rig.json("--from", str(source), "--yes")
    assert code == 1, doc
    assert doc["code"] == "models.source_invalid"
    assert str(source) not in doc["error"]
    assert rig.calls == []
    assert rig.leftovers() == []


def test_every_installer_call_is_wheels_only_with_constraints(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for route in ("online", "dir"):
        rig = make_rig(monkeypatch, tmp_path / route)
        args = (
            ["--yes"]
            if route == "online"
            else ["--from", str(_wheelhouse(tmp_path / "wh")), "--yes"]
        )
        code, doc = rig.json(*args)
        assert code == 0, doc
        assert rig.calls, "the install ran no installer"
        for call in rig.calls:
            i = call.argv.index("--only-binary")
            assert call.argv[i + 1] == ":all:", call.argv
            assert "--constraint" in call.argv, call.argv
            assert not any("decoy-engine" in a or "decoy_engine" in a for a in call.argv)


def test_a_wheel_added_or_swapped_after_the_check_is_never_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    user_dir = _wheelhouse(tmp_path / "wh")
    original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in user_dir.iterdir()}

    def tamper(argv: list[str]) -> None:
        wheel(user_dir, "evil-1.0-py3-none-any.whl", b"evil")
        (user_dir / MODEL).write_bytes(b"swapped")

    rig.hook = tamper
    code, doc = rig.json("--from", str(user_dir), "--yes")
    assert code == 0, doc
    for call in rig.calls:
        links = call.argv[call.argv.index("--find-links") + 1]
        assert Path(links).resolve() != user_dir.resolve()
        assert call.files["--find-links"] == original
        assert "--no-index" in call.argv
        assert not any(str(user_dir) in a for a in call.argv)
    assert rig.leftovers() == []


def test_the_private_copy_is_owner_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    modes: list[int] = []

    def look(argv: list[str]) -> None:
        links = argv[argv.index("--find-links") + 1]
        modes.append(os.stat(links).st_mode & 0o777)

    rig.hook = look
    code, _ = rig.json("--from", str(_wheelhouse(tmp_path / "wh")), "--yes")
    assert code == 0
    assert modes and all(m == 0o700 for m in modes)


def test_from_content_is_stated_as_trusted_before_installing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rig = make_rig(monkeypatch, tmp_path)
    result = rig.invoke("--from", str(_wheelhouse(tmp_path / "wh")), "--yes")
    assert result.exit_code == 0, result.output
    text = " ".join(result.stdout.split())
    assert "trusted" in text
    assert "certified" in text
