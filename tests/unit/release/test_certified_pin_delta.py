"""Row 24zc: the certified pin file moved exactly four pins, and its header matches the pins."""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

from decoy_engine.quality.dp_provenance import compute_lock_fingerprint

ROOT = Path(__file__).resolve().parents[3]
LIVE = ROOT / "requirements-certified.txt"
FIXTURE = ROOT / "tests" / "fixtures" / "sbom_runtime" / "requirements-certified-pre-24zc.txt"
# sha256 of the pre-repin requirements-certified.txt (CLI main 7c0fe61d).
FIXTURE_SHA256 = "8df82fedaf73747d4f01abc0f4d3602c9b6180913178e0643acd60df0822aba9"

DELTA = {
    "certifi": ("2026.7.22", "2026.10.18"),
    "cryptography": ("49.0.0", "50.0.0"),
    "pyasn1": ("0.6.4", "0.6.5"),
    "urllib3": ("2.7.0", "2.8.0"),
}


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sbom_checks = _load("sbom_checks", ROOT / "scripts" / "release" / "sbom_checks.py")
cert_smoke = _load("cert_smoke", ROOT / "scripts" / "cert_smoke.py")


def _parse(path: Path) -> dict[str, tuple[str, str]]:
    """canonical name -> (version, requirement text); names must be unique."""
    parsed: dict[str, tuple[str, str]] = {}
    for name, version, req in sbom_checks.pins(path.read_text(encoding="utf-8")):
        key = sbom_checks.canonical_name(name)
        assert key not in parsed, f"duplicate pin for {key}"
        parsed[key] = (version, req)
    return parsed


def test_pin_delta_is_exactly_the_four_named_moves() -> None:
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert digest == FIXTURE_SHA256, (
        "this fixture proves row 24zc only: delete it and this test on "
        "re-certification, never edit it"
    )
    before, after = _parse(FIXTURE), _parse(LIVE)
    assert len(before) == 70
    assert len(after) == 70
    assert before.keys() == after.keys()
    for name in before:
        if name not in DELTA:
            assert after[name] == before[name], f"{name}: {before[name][1]} -> {after[name][1]}"
    moved = {n: (before[n][0], after[n][0]) for n in before if before[n][0] != after[n][0]}
    assert moved == DELTA


def test_header_fingerprint_matches_pins_engine_and_cli() -> None:
    text = LIVE.read_text(encoding="utf-8")
    assert not [line for line in text.splitlines() if not line.startswith("#") and ";" in line], (
        "a marker on a pin line makes the set platform-dependent"
    )
    dists = {n: v for n, (v, _) in _parse(LIVE).items()}
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    engine = re.search(r'"decoy-engine==([^"]+)"', pyproject)
    assert engine is not None
    dists["decoy-engine"] = engine.group(1)
    version = (ROOT / "src" / "decoy" / "_version.py").read_text(encoding="utf-8")
    dists["decoy-cli"] = version.split('__version__ = "')[1].split('"')[0]
    computed = compute_lock_fingerprint(sorted(dists.items()))
    assert cert_smoke._recorded_fingerprint() == computed
