"""RG-F3: the launch pin check passes only on the D-4 tag, with agreeing pins and versions."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "launch_pin_check", ROOT / "scripts" / "release" / "launch_pin_check.py"
)
assert _spec is not None and _spec.loader is not None
lpc = importlib.util.module_from_spec(_spec)
sys.modules["launch_pin_check"] = lpc
_spec.loader.exec_module(lpc)

TAG = "v0.26.0"
SPEC = f"git+https://github.com/louiskeep/decoy-engine@{TAG}"


def _version() -> str:
    text = (ROOT / "src" / "decoy" / "_version.py").read_text(encoding="utf-8")
    return text.split('__version__ = "')[1].split('"')[0]


class FakeRunner:
    """Answers each step by its argv so no real script or pytest run is needed."""

    def __init__(self, spec_out: str = SPEC + "\n", failing: str | None = None) -> None:
        self.spec_out = spec_out
        self.failing = failing

    def __call__(self, argv: Sequence[str]) -> tuple[int, str]:
        joined = " ".join(argv)
        if "--engine-spec" in joined:
            return 0, self.spec_out
        if self.failing and self.failing in joined:
            return 1, "boom\n"
        if "--version" in joined:
            return 0, f"decoy {_version()}\n"
        return 0, ""


def test_spec_on_the_d4_tag_passes() -> None:
    results = lpc.check(TAG, FakeRunner(), ROOT)
    assert [r.ok for r in results] == [True] * len(results)
    assert lpc.main(["--engine-tag", TAG], runner=FakeRunner()) == 0


def test_spec_on_another_tag_fails() -> None:
    results = lpc.check("v0.27.0", FakeRunner(), ROOT)
    assert results[0].code == "launch_pin_not_d4_tag"
    assert lpc.main(["--engine-tag", "v0.27.0"], runner=FakeRunner()) == 1


def test_a_failing_agreement_step_fails() -> None:
    for step, needle in (("sentry", "test_ci_lock_installs"), ("lock_check", "lock.sh")):
        results = lpc.check(TAG, FakeRunner(failing=needle), ROOT)
        failed = [r for r in results if not r.ok]
        assert [r.code for r in failed] == ["pin_agreement_failed"]
        assert step in failed[0].line


def test_spec_with_trailing_newline_or_second_line_fails_closed() -> None:
    for out in (SPEC + "\n\n", SPEC + "\nsecond\n", SPEC + "\r\n", "x\n" + SPEC + "\n"):
        results = lpc.check(TAG, FakeRunner(spec_out=out), ROOT)
        assert results[0].code == "launch_pin_not_d4_tag", repr(out)


def test_version_disagreement_names_all_three() -> None:
    def runner(argv: Sequence[str]) -> tuple[int, str]:
        if "--version" in " ".join(argv):
            return 0, "decoy 9.9.9\n"
        return FakeRunner()(argv)

    failed = [r for r in lpc.check(TAG, runner, ROOT) if not r.ok]
    assert [r.code for r in failed] == ["version_disagreement"]
    assert "9.9.9" in failed[0].line and _version() in failed[0].line


def test_bad_tag_is_a_usage_error() -> None:
    assert lpc.main(["--engine-tag", "latest"], runner=FakeRunner()) == 2
    assert lpc.main([], runner=FakeRunner()) == 2
