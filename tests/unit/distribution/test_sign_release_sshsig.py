"""AT-K1..AT-K4 and AT-C1 of the MAC ed25519 verify plan: signer subcommands, SSHSIG sidecars
and the endpoint contract."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from packaging_tools import sign_release
from tests.unit.distribution._helpers import (
    INSTALL_SH,
    REPO_ROOT,
    _signed_release,
    needs_ssh_keygen,
    private_pem,
    run_signer,
    ssh_verify,
    write_key,
)

from decoy.distribution import version_document as vd

RAW = (serialization.Encoding.Raw, serialization.PublicFormat.Raw)
CONTRACT = REPO_ROOT / "docs" / "distribution" / "version-endpoint-contract.md"
OPENSSH = serialization.PrivateFormat.OpenSSH


def _blob(key: Ed25519PrivateKey) -> str:
    return sign_release.pinned_forms(key)[1]


def _leaked(key: Ed25519PrivateKey, text: str) -> bool:
    """Any base64 body line of either private form, or a PRIVATE KEY header, in ``text``."""
    pems = private_pem(key) + private_pem(key, OPENSSH)
    lines = [ln for ln in pems.decode().splitlines() if not ln.startswith("-----")]
    return "PRIVATE KEY" in text or any(ln in text for ln in lines)


@needs_ssh_keygen
def test_at_k1_pubkeys_two_forms_one_key(tmp_path):
    key = Ed25519PrivateKey.generate()
    r = run_signer("pubkeys", "--key", str(write_key(tmp_path / "k.pem", key)))
    assert r.returncode == 0, r.stderr
    forms = json.loads(r.stdout)
    pem = serialization.load_pem_public_key(
        f"-----BEGIN PUBLIC KEY-----\n{forms['pem']}\n-----END PUBLIC KEY-----\n".encode()
    )
    ssh = serialization.load_ssh_public_key(b"ssh-ed25519 " + forms["ssh"].encode())
    assert pem.public_bytes(*RAW) == ssh.public_bytes(*RAW) == key.public_key().public_bytes(*RAW)
    openssh_key = tmp_path / "k.ssh"
    openssh_key.write_bytes(private_pem(key, OPENSSH))
    openssh_key.chmod(0o600)
    y = subprocess.run(["ssh-keygen", "-y", "-f", str(openssh_key)], capture_output=True, text=True)
    assert y.stdout.split()[1] == forms["ssh"]


def _installer_with(pem_key, ssh_key) -> str:
    """install.sh text with each placeholder filled from its own key (None leaves it)."""
    text = INSTALL_SH.read_text()
    if pem_key is not None:
        text = text.replace("__DECOY_RELEASE_PUBLIC_KEY__", sign_release.pinned_forms(pem_key)[0])
    if ssh_key is not None:
        text = text.replace("__DECOY_RELEASE_SSH_PUBLIC_KEY__", _blob(ssh_key))
    return text


def test_at_k2_check_keys_refuses_bad_installers_and_passes_injected(tmp_path):
    a, b = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    good = _installer_with(a, a)
    cases = {
        "two different keys": _installer_with(a, b),
        "pem placeholder left": _installer_with(None, a),
        "ssh placeholder left": _installer_with(a, None),
        "both placeholders left": INSTALL_SH.read_text(),
        "malformed ssh": re.sub(r"(PINNED_SSH_PUBKEY=')[^']*", r"\1AAAAnotakey", good),
        "malformed pem": good.replace(sign_release.pinned_forms(a)[0], "bm90LXBlbQ=="),
        # cryptography decodes base64 leniently; ssh-keygen does not, so the text must match exactly.
        # sh runs the last assignment, so a later one with another key must not pass on the first
        "later ssh assignment with another key": good + f"\nPINNED_SSH_PUBKEY='{_blob(b)}'\n",
        "later pem assignment": good + "\nPINNED_PUBKEY='x'\n",
        "stray character in ssh blob": good.replace(_blob(a), _blob(a)[:10] + "!" + _blob(a)[10:]),
        "stray character in pem body": good.replace(
            sign_release.pinned_forms(a)[0],
            sign_release.pinned_forms(a)[0][:10] + "!" + sign_release.pinned_forms(a)[0][10:],
        ),
    }
    path = tmp_path / "case.sh"
    for name, text in cases.items():
        path.write_text(text)
        r = run_signer("check-keys", str(path))
        assert (r.returncode != 0, r.stderr.strip()) == (True, sign_release._KEYS_BAD), name
    path.write_text(good)
    assert run_signer("check-keys", str(path)).returncode == 0
    out = tmp_path / "injected.sh"
    args = (
        "--key",
        str(write_key(tmp_path / "k.pem", a)),
        "--in",
        str(INSTALL_SH),
        "--out",
        str(out),
    )
    assert run_signer("inject-keys", *args).returncode == 0
    assert run_signer("check-keys", str(out)).returncode == 0


@needs_ssh_keygen
def test_at_k3_sshsig_verifies_and_leaves_nothing_behind(tmp_path):
    rel = _signed_release(tmp_path)
    (tmp_path / "aux").mkdir()
    data_file = rel.files[0]
    sig, raw_sig = Path(f"{data_file}.sshsig"), Path(f"{data_file}.sig")
    raw_before = raw_sig.read_bytes()
    assert sig.read_text().startswith("-----BEGIN SSH SIGNATURE-----")
    assert ssh_verify(tmp_path, _blob(rel.key), sig, data_file.read_bytes()).returncode == 0
    assert ssh_verify(tmp_path, _blob(rel.key), sig, data_file.read_bytes() + b"x").returncode != 0
    args = ("sshsig", "--in", str(data_file), "--out", str(sig))
    r = run_signer(*args, key_file=rel.key_file, TMPDIR=str(tmp_path / "aux"))
    assert r.returncode == 0
    assert raw_sig.read_bytes() == raw_before
    assert list((tmp_path / "aux").iterdir()) == []
    assert not _leaked(rel.key, r.stdout + r.stderr)


@needs_ssh_keygen
def test_at_k3_failed_ssh_keygen_leaves_existing_sidecar_unchanged(tmp_path):
    rel = _signed_release(tmp_path)
    data_file = rel.files[0]
    sig, raw_sig = Path(f"{data_file}.sshsig"), Path(f"{data_file}.sig")
    before, raw_before = sig.read_bytes(), raw_sig.read_bytes()
    aux = tmp_path / "aux"
    (aux / "bin").mkdir(parents=True)
    (aux / "tmp").mkdir()
    fake = aux / "bin" / "ssh-keygen"
    fake.write_text("#!/bin/sh\nprintf 'partial output'\nexit 1\n")
    fake.chmod(0o755)
    listing = sorted(os.listdir(tmp_path))
    r = run_signer(
        "sshsig",
        "--in",
        str(data_file),
        "--out",
        str(sig),
        key_file=rel.key_file,
        PATH=f"{aux / 'bin'}:{os.environ['PATH']}",
        TMPDIR=str(aux / "tmp"),
    )
    assert r.returncode != 0
    assert (sig.read_bytes(), raw_sig.read_bytes()) == (before, raw_before)
    assert sorted(os.listdir(tmp_path)) == listing  # no temp file beside the sidecar
    assert list((aux / "tmp").iterdir()) == []
    assert not _leaked(rel.key, r.stdout + r.stderr)


@needs_ssh_keygen
def test_at_k4_known_answer_constants_verify_with_real_ssh_keygen(tmp_path):
    text = INSTALL_SH.read_text()
    blob = re.search(r"^KAT_SSH_PUBKEY='([^']+)'", text, re.M)[1]
    sig = tmp_path / "kat.sshsig"
    sig.write_text(re.search(r"^KAT_SSHSIG='([^']+)'", text, re.M)[1] + "\n")
    assert ssh_verify(tmp_path, blob, sig, b"\x72").returncode == 0
    assert ssh_verify(tmp_path, blob, sig, b"\x73").returncode != 0


def test_at_c1_contract_names_sshsig_urls_namespace_identity_and_command():
    text = CONTRACT.read_text()
    for needle in (
        "https://decoy.dev/cli/version.json.sshsig",
        "https://decoy.dev/cli/<version>/decoy-<version>-<target>.tar.gz.sshsig",
        "decoy-release@decoy.dev",
        'namespaces="decoy-release"',
        "ssh-keygen -Y verify -f allowed_signers -I decoy-release@decoy.dev "
        "-n decoy-release -s version.json.sshsig < version.json",
    ):
        assert needle in text
    assert "sshsig" not in re.search(r"```json\n(.*?)```", text, re.S)[1]


def test_at_c1_version_document_has_no_sshsig_field():
    art = {"linux-x86_64": {"url": "u", "sha256": "0" * 64, "sig": "u.sig"}}
    doc = vd.build_document(latest="1.0.0", min_supported="1.0.0", artifacts=art, serial=1)
    assert set(doc) == {
        "schema_version",
        "latest",
        "min_supported",
        "yanked",
        "message",
        "generated",
        "serial",
        "expires",
        "artifacts",
    }
    assert set(vd.select_artifact(doc, "linux-x86_64")) == {"url", "sha256", "sig"}
    assert vd.parse_document(vd.canonical_document_bytes(doc)) == doc


def test_at_c1_generated_artifacts_carry_no_sshsig_field(tmp_path):
    """The generator (not only build_document) must leave the artifact entry at url, sha256, sig."""
    from packaging_tools import make_version_document as mvd

    name = "decoy-1.0.0-linux-x86_64.tar.gz"
    (tmp_path / name).write_bytes(b"x")
    import hashlib

    (tmp_path / f"{name}.sig").write_text("c2ln\n")
    (tmp_path / f"{name}.sha256").write_text(hashlib.sha256(b"x").hexdigest() + f"  {name}\n")
    art = mvd.collect_artifacts(tmp_path, version="1.0.0", base_url="https://decoy.dev/cli")
    assert {k for entry in art.values() for k in entry} == {"url", "sha256", "sig"}


def test_at_k2_inject_keys_refuses_a_bad_template_and_writes_nothing(tmp_path):
    key = write_key(tmp_path / "k.pem", Ed25519PrivateKey.generate())
    text = INSTALL_SH.read_text()
    templates = {
        # placeholder removed
        "no ssh placeholder": text.replace("__DECOY_RELEASE_SSH_PUBLIC_KEY__", "x"),
        # a second copy, as a literal in a case pattern, must not be rewritten into the real key
        "repeated ssh placeholder": text + "\n# __DECOY_RELEASE_SSH_PUBLIC_KEY__\n",
        # one placeholder, but not in the single-quoted assignment check-keys reads
        "ssh placeholder in a double-quoted line": text.replace(
            "PINNED_SSH_PUBKEY='__DECOY_RELEASE_SSH_PUBLIC_KEY__'",
            'PINNED_SSH_PUBKEY="__DECOY_RELEASE_SSH_PUBLIC_KEY__"',
        ),
    }
    for name, body in templates.items():
        src, out = tmp_path / "in.sh", tmp_path / "out.sh"
        out.unlink(missing_ok=True)
        src.write_text(body)
        r = run_signer("inject-keys", "--key", str(key), "--in", str(src), "--out", str(out))
        assert r.returncode == 1 and r.stderr.strip() == "inject-keys: failed", name
        assert not out.exists() and not list(tmp_path.glob("out.sh.*")), name
