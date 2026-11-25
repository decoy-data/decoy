"""LINTDEBT-A1: ``scripts/dev/lintdebt.py`` blocks new lint debt and lets the baseline only shrink.

The step counts hits of extra ruff rules per file and rule against the registered ``lint-debt``
baseline. This file is that baseline's one consumer. The scratch-project cases copy only the
ratchet helper and the registry, so they never read the real tree.

Named limit: the counts depend on the ruff version, which the dev lock pins.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from tests.sentry._ratchet import load_allowlist

ROOT = Path(__file__).resolve().parents[2]
LINTDEBT = ROOT / "scripts" / "dev" / "lintdebt.py"
RATCHET = ROOT / "scripts" / "dev" / "ratchet_check.py"
BASELINE = "tests/sentry/baselines/lint-debt.json"
REG = "scripts/dev/sentry_registry.toml"
HIT = "def f():\n    try:\n        return 1\n    except Exception:\n        return 2\n"
MARK = "zz_secret_marker_value"
RUFF = shutil.which("ruff") or str(Path(sys.executable).parent / "ruff")
needs_ruff = pytest.mark.skipif(not Path(RUFF).exists(), reason="ruff is not installed")


def _run(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    # A scratch project scans only src: its tests/ holds the copied ratchet helper, real code.
    scope = [] if root == ROOT else ["src"]
    cmd = [sys.executable, str(LINTDEBT), "--root", str(root), "--ruff", RUFF, *extra, *scope]
    return subprocess.run(cmd, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    """A scratch project holding one BLE001 hit, with its baseline written and committed."""
    for rel in ("tests/sentry/_ratchet.py", "src/decoy/distribution/release_identity.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    (tmp_path / REG).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / REG, tmp_path / REG)
    # Only the lint-debt row matters here; the others point at files this scratch tree lacks.
    row = (ROOT / REG).read_text(encoding="utf-8").split('[[sentry]]\nid = "lint-debt"')[1]
    # The real row's approved_growth keys are not in this scratch baseline; drop them.
    row = re.sub(r"approved_growth = \[.*?\n\]\n", "", row, flags=re.DOTALL)
    (tmp_path / REG).write_text('[[sentry]]\nid = "lint-debt"' + row, encoding="utf-8")
    (tmp_path / "src" / "mod.py").write_text(HIT, encoding="utf-8")
    assert _run(tmp_path, "--init").returncode == 0
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def test_the_baseline_is_well_formed_and_names_live_files() -> None:
    entries = load_allowlist("lint-debt")
    assert entries, "an empty baseline means the step is off"
    for key, entry in entries.items():
        file, rule = key.split("::")
        assert (ROOT / file).is_file(), f"{key}: the file is gone, shrink the baseline"
        assert isinstance(entry["count"], int) and entry["count"] > 0
        assert not rule.startswith(("S110", "S112")), "engine-only rules"
        assert not (rule.startswith("T20") and file == "src/decoy/ui/output.py")


@needs_ruff
def test_the_generated_baseline_passes_on_the_current_tree() -> None:
    res = _run(ROOT)
    assert res.returncode == 0, res.stdout + res.stderr


@needs_ruff
def test_a_new_hit_fails_naming_the_file_and_rule_without_contents(proj: Path) -> None:
    (proj / "src" / "new.py").write_text(HIT.replace("return 2", f"{MARK} = 2"), encoding="utf-8")
    res = _run(proj)
    out = res.stdout + res.stderr
    assert res.returncode == 1, out
    assert "src/new.py BLE001" in out
    assert MARK not in out and "except Exception" not in out


@needs_ruff
def test_a_second_hit_in_a_baselined_file_fails(proj: Path) -> None:
    (proj / "src" / "mod.py").write_text(HIT + "\n\n" + HIT.replace("f()", "g()"), encoding="utf-8")
    res = _run(proj)
    assert res.returncode == 1
    assert "src/mod.py BLE001: 2 hit(s), baseline allows 1" in res.stderr


@needs_ruff
def test_a_removed_hit_passes_and_says_to_shrink(proj: Path) -> None:
    (proj / "src" / "mod.py").write_text("X = 1\n", encoding="utf-8")
    res = _run(proj)
    assert res.returncode == 0, res.stderr
    assert "--shrink" in res.stdout and "src/mod.py BLE001" in res.stdout
    assert _run(proj, "--shrink").returncode == 0
    after = json.loads((proj / BASELINE).read_text(encoding="utf-8"))
    assert after["entries"] == {}


@needs_ruff
def test_shrink_never_raises_a_count_or_adds_a_key(proj: Path) -> None:
    before = (proj / BASELINE).read_text(encoding="utf-8")
    (proj / "src" / "new.py").write_text(HIT, encoding="utf-8")
    assert _run(proj, "--shrink").returncode == 1
    assert (proj / BASELINE).read_text(encoding="utf-8") == before


@needs_ruff
def test_init_refuses_to_overwrite_an_existing_baseline(proj: Path) -> None:
    (proj / "src" / "new.py").write_text(HIT, encoding="utf-8")
    assert _run(proj, "--init").returncode == 2
    assert "src/new.py" not in (proj / BASELINE).read_text(encoding="utf-8")


@needs_ruff
def test_print_is_flagged_everywhere_except_the_output_module(proj: Path) -> None:
    out = proj / "src" / "decoy" / "ui" / "output.py"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("print(1)\n", encoding="utf-8")
    assert _run(proj).returncode == 0
    (proj / "src" / "other.py").write_text("print(1)\n", encoding="utf-8")
    res = _run(proj)
    assert res.returncode == 1 and "src/other.py T201" in res.stderr


def _ratchet(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RATCHET), "--root", str(repo), "--base", "HEAD"],
        capture_output=True,
        text=True,
    )


def _edit(repo: Path, edit) -> None:
    doc = json.loads((repo / BASELINE).read_text(encoding="utf-8"))
    edit(doc["entries"])
    (repo / BASELINE).write_text(json.dumps(doc), encoding="utf-8")


@needs_ruff
def test_a_baseline_count_cannot_go_up_through_the_ratchet(proj: Path) -> None:
    assert _ratchet(proj).returncode == 0
    _edit(proj, lambda e: e["src/mod.py::BLE001"].update(count=2))
    res = _ratchet(proj)
    assert res.returncode == 1
    assert "src/mod.py::BLE001" in res.stderr


@needs_ruff
def test_a_baseline_count_cannot_be_dropped_or_moved_to_another_field(proj: Path) -> None:
    _edit(proj, lambda e: e["src/mod.py::BLE001"].pop("count"))
    assert _ratchet(proj).returncode == 1
    _edit(proj, lambda e: e["src/mod.py::BLE001"].update(max=5))
    assert _ratchet(proj).returncode == 1


@needs_ruff
def test_a_new_baseline_key_cannot_be_added(proj: Path) -> None:
    _edit(
        proj,
        lambda e: e.update({"src/new.py::BLE001": {"reason": "a long enough reason", "count": 1}}),
    )
    res = _ratchet(proj)
    assert res.returncode == 1 and "src/new.py::BLE001" in res.stderr


@needs_ruff
def test_a_lowered_count_passes_the_ratchet(proj: Path) -> None:
    (proj / "src" / "mod.py").write_text("X = 1\n", encoding="utf-8")
    assert _run(proj, "--shrink").returncode == 0
    assert _ratchet(proj).returncode == 0
