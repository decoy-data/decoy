"""Drift guard for the release-smoke CI workflow file (OSS.1 commit 3).

The workflow file at `.github/workflows/release-smoke.yml` is the
launch-day DX gate the README §8 R2 risk depends on. If a future
contributor silently empties the file, drops the Python matrix, or
removes one of the canonical smoke cells, this test trips before the
gate goes quiet.

This is a SHAPE check, not an execution test. The real verification
is the workflow itself running in CI; this only catches "did someone
delete the gate?" between releases.

The second half covers the canonical smoke (`smoke_install.py
--from-dist`, REL-GATE 5.4) against a fake signed candidate set: random
tarball bytes signed with a throwaway key, the real installers with
that key in place of the placeholder, and a signed version document.
The fake bundle cannot install, so the green path stubs the steps after
the key checks; a real run is AT-S6 evidence, not a unit test.
"""

from __future__ import annotations

import base64
import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from packaging_tools import candidate as cand
from packaging_tools import smoke_install as smoke

from decoy import _native_gate
from decoy.distribution import version_document as vd
from decoy.distribution.release_key import PLACEHOLDER_MARKER
from decoy.distribution.targets import SUPPORTED_TARGETS, detect_target

WORKFLOW = (
    Path(__file__).resolve().parent.parent.parent
    / ".github"
    / "workflows"
    / "release-smoke.yml"
)


def test_release_smoke_workflow_file_exists() -> None:
    assert WORKFLOW.exists(), (
        f"{WORKFLOW.name} was deleted; the OSS-CLI launch gate is gone. "
        "Recreate the file or call out the removal in a sprint spec."
    )


def test_release_smoke_workflow_pins_three_python_versions() -> None:
    """OSS.1 commits to a Python 3.10 + 3.11 + 3.12 matrix. Adding a
    version requires a deliberate edit to this test."""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = data["jobs"]["fresh-install"]
    python_versions = set(job["strategy"]["matrix"]["python"])
    assert python_versions == {"3.10", "3.11", "3.12"}, (
        f"release-smoke Python matrix drifted from {{3.10, 3.11, 3.12}}: "
        f"now {python_versions}. If this is intentional, update both "
        f"the matrix and this assertion in the same commit."
    )


def test_release_smoke_workflow_runs_canonical_smoke_cells() -> None:
    """The three canonical CLI cells (`decoy --version`, `decoy demo
    --json`, the `decoy run` cell against the bundled minimal template)
    must all appear in the workflow's step list. The check is on the
    `run:` text of each step; spelling matters."""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = data["jobs"]["fresh-install"]["steps"]
    run_bodies = "\n".join(s.get("run", "") for s in steps)
    assert "decoy --version" in run_bodies, "smoke cell 1 (--version) missing"
    assert "decoy demo --json" in run_bodies, "smoke cell 2 (demo --json) missing"
    assert "decoy run" in run_bodies, "smoke cell 3 (decoy run) missing"
    assert "decoy show template minimal" in run_bodies, (
        "the run cell must source its pipeline from the bundled minimal "
        "template, not from examples/ (which is repo-only, not in the wheel). "
        "S3b redesign: `templates show` folded into `show <kind> <name>`."
    )


def test_release_smoke_workflow_does_not_publish() -> None:
    """OSS.1 is a smoke gate, not a publish pipeline. Any real publish
    action here is a scope violation; publishing belongs to OSS.7.

    The check scans the EXECUTABLE step entries (both ``run:`` shell
    bodies AND ``uses:`` action invocations). Mentioning PyPI in a
    comment that explains the eventual transition is fine; running
    ``twine upload`` (run body) or invoking ``pypa/gh-action-pypi-publish``
    (uses entry) is not.

    Dennis M1 follow-up (2026-06-02, FC-2/OSS.1 merge clearance):
    pre-fix this test only scanned ``run:`` bodies; a step that uses
    the trusted-publish action via ``uses:`` (no ``run:`` body) would
    have slipped past. Now both surfaces gate.
    """
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = data["jobs"]["fresh-install"]
    run_bodies = "\n".join(s.get("run", "") for s in job["steps"]).lower()
    uses_entries = [
        (s.get("uses", "") or "").lower()
        for s in job["steps"]
    ]
    assert "twine upload" not in run_bodies, (
        "OSS.1 must not publish; twine upload belongs to OSS.7"
    )
    assert "upload-pypi" not in run_bodies, (
        "OSS.1 must not publish; the trusted-publish action belongs to OSS.7"
    )
    # The well-known PyPA trusted-publish action + any author/fork of
    # it. Pattern check on the `uses:` field, since trusted-publish
    # actions never have a `run:` body.
    publish_action_substrings = ("pypi-publish", "pypa/gh-action-pypi", "twine")
    for uses in uses_entries:
        for substring in publish_action_substrings:
            assert substring not in uses, (
                f"OSS.1 must not publish; step uses {uses!r} matches "
                f"publish-action pattern {substring!r} (belongs to OSS.7)"
            )



# --- canonical smoke: candidate mode (REL-GATE 5.4) ------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
HOST = detect_target()
VERSION = "1.0.0"
needs_host = pytest.mark.skipif(HOST is None, reason="this host maps to no supported target")
needs_installer = pytest.mark.skipif(
    HOST is None or shutil.which("openssl") is None, reason="needs a supported host with openssl"
)


def _sign(key: Ed25519PrivateKey, data: bytes) -> str:
    return base64.b64encode(key.sign(data)).decode("ascii") + "\n"


def _write_document(dist: Path, key: Ed25519PrivateKey, artifacts: dict, latest: str = VERSION):
    payload = vd.build_document(latest=latest, min_supported=VERSION, artifacts=artifacts, serial=1)
    data = vd.canonical_document_bytes(payload)
    (dist / "version.json").write_bytes(data)
    (dist / "version.json.sig").write_text(_sign(key, data))


def _artifacts(dist: Path) -> dict:
    base = f"https://downloads.example.invalid/cli/{VERSION}"
    out = {}
    for target in SUPPORTED_TARGETS:
        name = f"decoy-{VERSION}-{target}.tar.gz"
        out[target] = {
            "url": f"{base}/{name}",
            "sha256": cand.sha256_file(dist / name),
            "sig": f"{base}/{name}.sig",
        }
    return out


def _seal(dist: Path) -> dict:
    return cand.write(
        dist, cli_version=VERSION, cli_sha="a" * 40, engine_tag="v0.27.0", engine_commit="b" * 40
    )


@pytest.fixture
def candidate_set(tmp_path, monkeypatch):
    key = Ed25519PrivateKey.generate()
    pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    body = "".join(pem.strip().splitlines()[1:-1])
    dist = tmp_path / "dist"
    dist.mkdir()
    for target in SUPPORTED_TARGETS:
        tarball = dist / f"decoy-{VERSION}-{target}.tar.gz"
        tarball.write_bytes(target.encode() * 512)
        (dist / f"{tarball.name}.sig").write_text(_sign(key, tarball.read_bytes()))
    for name in cand.INSTALLERS:
        text = (ROOT / "packaging_tools" / "install" / name).read_text(encoding="utf-8")
        (dist / name).write_text(text.replace(PLACEHOLDER_MARKER, body), encoding="utf-8")
    _write_document(dist, key, _artifacts(dist))
    _seal(dist)
    pubkey = tmp_path / "release.pub.pem"
    pubkey.write_text(pem)
    temp_roots: list[Path] = []
    real_mkdtemp = tempfile.mkdtemp

    def recording_mkdtemp(*args, **kwargs):
        temp_roots.append(Path(real_mkdtemp(*args, dir=tmp_path, **kwargs)))
        return str(temp_roots[-1])

    monkeypatch.setattr(smoke.tempfile, "mkdtemp", recording_mkdtemp)
    monkeypatch.delenv("DECOY_RELEASE_PUBKEY_FILE", raising=False)
    argv = ["--from-dist", str(dist), "--candidate", str(dist / cand.CANDIDATE_NAME),
            "--pubkey", str(pubkey), "--target", HOST or "linux-x86_64"]  # fmt: skip
    return SimpleNamespace(dist=dist, key=key, pubkey=pubkey, argv=argv, temp_roots=temp_roots)


def _run(argv: list[str], capsys) -> tuple[int, dict | None, str]:
    rc = smoke.main(argv)
    out, err = capsys.readouterr()
    return rc, (json.loads(out) if out.strip() else None), err


def test_candidate_mode_requires_dist_and_native_state(candidate_set, capsys) -> None:
    without_dist = candidate_set.argv[2:]
    assert smoke.main(without_dist) == 2
    assert smoke.main(candidate_set.argv[:2]) == 2
    assert candidate_set.temp_roots == []
    assert "--from-dist" in capsys.readouterr().err
    assert smoke.native_route_ok(
        json.dumps({"native_route": {"applicable": True, "state": "native"}})
    )
    for route in ({"applicable": True, "state": "unified_slice"}, {"applicable": True}, None):
        assert not smoke.native_route_ok(json.dumps({"native_route": route}))
    assert not smoke.native_route_ok("not json")


def test_native_smoke_pipeline_is_native_eligible_with_every_strategy() -> None:
    config = yaml.safe_load(smoke.NATIVE_PIPELINE.read_text(encoding="utf-8"))
    assert _native_gate.static_native_eligibility(config)
    strategies = {c["strategy"] for c in config["tables"][0]["columns"]}
    assert strategies == set(_native_gate._NATIVE_STRATEGIES)


def test_windows_and_foreign_targets_are_usage_errors(candidate_set, capsys) -> None:
    argv = candidate_set.argv[:-1]
    assert smoke.main([*argv, "windows-x86_64"]) == 2
    assert "gated" in capsys.readouterr().err
    other = next(t for t in SUPPORTED_TARGETS if t != HOST)
    assert smoke.main([*argv, other]) == 2
    assert smoke.main([*candidate_set.argv, "--work", "x"]) == 2
    assert candidate_set.temp_roots == []


@needs_host
def test_failed_step_still_removes_the_temp_root(candidate_set, capsys) -> None:
    tarball = candidate_set.dist / f"decoy-{VERSION}-{HOST}.tar.gz"
    tarball.write_bytes(b"changed after the candidate was sealed")
    rc, summary, err = _run(candidate_set.argv, capsys)
    assert rc == 1
    assert summary["steps"] == {"candidate": "fail"}
    assert "smoke_candidate_mismatch" in err
    assert len(candidate_set.temp_roots) == 1
    assert not candidate_set.temp_roots[0].exists()


def test_keep_is_refused_in_candidate_mode(candidate_set, capsys) -> None:
    assert smoke.main([*candidate_set.argv, "--keep"]) == 2
    assert "--keep" in capsys.readouterr().err
    assert candidate_set.temp_roots == []


@needs_host
def test_sums_must_match_the_candidate_record_not_themselves(candidate_set, capsys) -> None:
    tarball = candidate_set.dist / f"decoy-{VERSION}-{HOST}.tar.gz"
    tarball.write_bytes(b"swapped and relisted")
    (candidate_set.dist / cand.SUMS_NAME).write_text(cand.sums_text(candidate_set.dist))
    rc, summary, err = _run(candidate_set.argv, capsys)
    assert (rc, summary["steps"]) == (1, {"candidate": "fail"})
    assert "smoke_candidate_mismatch" in err


@needs_installer
def test_swapped_bundle_after_candidate_compare_fails_install(
    candidate_set, capsys, monkeypatch
) -> None:
    rc, summary, err = _run(candidate_set.argv, capsys)
    assert rc == 1 and summary["steps"]["install"] == "fail"
    assert "checksum MISMATCH" not in err, "the unswapped fake bundle passes the checksum"
    compare = smoke._Candidate.candidate

    def compare_then_swap(self) -> None:
        compare(self)
        (self.copy / f"decoy-{VERSION}-{HOST}.tar.gz").write_bytes(b"swapped after the compare")

    monkeypatch.setattr(smoke._Candidate, "candidate", compare_then_swap)
    rc, summary, err = _run(candidate_set.argv, capsys)
    assert rc == 1
    assert summary["steps"] == {
        "candidate": "pass",
        "version_document": "pass",
        "installer_key": "pass",
        "install": "fail",
    }
    assert "checksum MISMATCH" in err


@needs_host
def test_placeholder_key_or_env_override_is_refused(candidate_set, capsys, monkeypatch) -> None:
    monkeypatch.setenv("DECOY_RELEASE_PUBKEY_FILE", str(candidate_set.pubkey))
    assert smoke.main(candidate_set.argv) == 2
    assert candidate_set.temp_roots == []
    monkeypatch.delenv("DECOY_RELEASE_PUBKEY_FILE")

    for name in cand.INSTALLERS:
        installer = candidate_set.dist / name
        original = installer.read_text(encoding="utf-8")
        shipped = (ROOT / "packaging_tools" / "install" / name).read_text(encoding="utf-8")
        installer.write_text(shipped, encoding="utf-8")
        _seal(candidate_set.dist)
        rc, summary, err = _run(candidate_set.argv, capsys)
        assert (rc, summary["steps"]["installer_key"]) == (1, "fail"), name
        assert "smoke_placeholder_key" in err
        installer.write_text(original, encoding="utf-8")
    _seal(candidate_set.dist)

    monkeypatch.setattr(smoke._Candidate, "install", lambda self: None)
    other = Ed25519PrivateKey.generate().public_key()
    other_pem = other.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    monkeypatch.setattr(smoke._Candidate, "_bundle_python", lambda self, code: other_pem)
    rc, summary, err = _run(candidate_set.argv, capsys)
    assert (rc, summary["steps"]["bundle_key"]) == (1, "fail")
    assert "smoke_placeholder_key" in err


@needs_host
def test_version_document_whose_sha256_disagrees_with_the_tarball_is_refused(
    candidate_set, capsys
) -> None:
    artifacts = _artifacts(candidate_set.dist)
    artifacts[HOST]["sha256"] = "0" * 64
    _write_document(candidate_set.dist, candidate_set.key, artifacts)
    _seal(candidate_set.dist)
    rc, summary, err = _run(candidate_set.argv, capsys)
    assert (rc, summary["steps"]["version_document"]) == (1, "fail")
    assert "smoke_version_document_invalid" in err

    _write_document(
        candidate_set.dist, Ed25519PrivateKey.generate(), _artifacts(candidate_set.dist)
    )
    _seal(candidate_set.dist)
    rc, summary, _ = _run(candidate_set.argv, capsys)
    assert (rc, summary["steps"]["version_document"]) == (1, "fail")

    _write_document(candidate_set.dist, candidate_set.key, _artifacts(candidate_set.dist), "1.0.1")
    _seal(candidate_set.dist)
    rc, summary, _ = _run(candidate_set.argv, capsys)
    assert (rc, summary["steps"]["version_document"]) == (1, "fail")


@needs_host
def test_green_summary_names_every_step_and_the_candidate(
    candidate_set, capsys, monkeypatch
) -> None:
    for step in ("install", "version", "doctor", "native", "template"):
        monkeypatch.setattr(smoke._Candidate, step, lambda self: None)
    pem = candidate_set.pubkey.read_text()
    answers = {True: pem, False: "0.27.0\n"}
    monkeypatch.setattr(
        smoke._Candidate, "_bundle_python", lambda self, code: answers["release_key" in code]
    )
    rc, summary, _ = _run(candidate_set.argv, capsys)
    record = cand.read_candidate(candidate_set.dist / cand.CANDIDATE_NAME)
    assert rc == 0
    assert summary["steps"] == dict.fromkeys(cand.SMOKE_STEPS, "pass")
    assert summary["schema"] == cand.SUMMARY_SCHEMA
    assert (summary["platform"], summary["engine_version"]) == (HOST, "0.27.0")
    assert summary["sha256sums_sha256"] == record["sha256sums_sha256"]
    assert not candidate_set.temp_roots[0].exists()
