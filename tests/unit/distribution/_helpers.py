"""Shared fixtures for the release-signing tests. MAC-V1a reuses `_signed_release`."""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parents[3]
SIGNER = REPO_ROOT / "packaging_tools" / "sign_release.py"
INSTALL_SH = REPO_ROOT / "packaging_tools" / "install" / "install.sh"
IDENTITY, NAMESPACE = "decoy-release@decoy.dev", "decoy-release"


def _skip_reason() -> str:
    if not shutil.which("ssh-keygen"):
        return "ssh-keygen not installed"
    ver = subprocess.run(["ssh", "-V"], capture_output=True, text=True, check=False)
    m = re.search(r"OpenSSH_(\d+)\.(\d+)", ver.stderr + ver.stdout)
    if m and (int(m[1]), int(m[2])) < (8, 1):
        return f"ssh-keygen {m[1]}.{m[2]} is older than 8.1 (no SSHSIG support)"
    return ""


needs_ssh_keygen = pytest.mark.skipif(
    bool(_skip_reason()), reason=_skip_reason() or "ssh-keygen ok"
)


def private_pem(key: Ed25519PrivateKey, fmt=serialization.PrivateFormat.PKCS8) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, fmt, serialization.NoEncryption())


def write_key(path: Path, key: Ed25519PrivateKey) -> Path:
    path.write_bytes(private_pem(key))
    path.chmod(0o600)
    return path


def run_signer(*args: str, key_file: Path | None = None, **env: str):
    full = dict(os.environ, **env)
    full.pop("DECOY_RELEASE_KEY_PEM", None)
    if key_file:
        full["DECOY_RELEASE_KEY_FILE"] = str(key_file)
    cmd = [sys.executable, str(SIGNER), *args]
    return subprocess.run(cmd, env=full, capture_output=True, text=True, check=False)


def _signed_release(tmp_path: Path) -> SimpleNamespace:
    """A throwaway key, an install.sh with both pinned forms injected, and two files signed
    with `sign` (raw `.sig`) and `sshsig` (`.sshsig`)."""
    key = Ed25519PrivateKey.generate()
    key_file = write_key(tmp_path / "release.pem", key)
    install_sh = tmp_path / "install.sh"
    args = ("--key", str(key_file), "--in", str(INSTALL_SH), "--out", str(install_sh))
    assert run_signer("inject-keys", *args).returncode == 0
    files = []
    for name, body in (("version.json", b'{"x":1}'), ("bundle.tar.gz", b"\x00bundle\xff")):
        f = tmp_path / name
        f.write_bytes(body)
        files.append(f)
        assert run_signer("sign", str(f), key_file=key_file).returncode == 0
        assert (
            run_signer(
                "sshsig", "--in", str(f), "--out", f"{f}.sshsig", key_file=key_file
            ).returncode
            == 0
        )
    return SimpleNamespace(key=key, key_file=key_file, install_sh=install_sh, files=files)


def ssh_verify(tmp_path: Path, blob: str, sig: Path, data: bytes, binary: str = "ssh-keygen"):
    """The contract's verify command (design note 4) against a one-line allowed_signers file."""
    signers = tmp_path / "allowed_signers"
    signers.write_text(f'{IDENTITY} namespaces="{NAMESPACE}" ssh-ed25519 {blob}\n')
    cmd = [
        binary,
        "-Y",
        "verify",
        "-f",
        str(signers),
        "-I",
        IDENTITY,
        "-n",
        NAMESPACE,
        "-s",
        str(sig),
    ]
    return subprocess.run(cmd, input=data, capture_output=True, check=False)


# --- verifier capability gates (MAC-V1a) -------------------------------------------------
# RFC 8032 section 7.1 TEST 2: public key as SPKI PEM, message 0x72, signature. A gate that only
# asked `shutil.which("openssl")` passed on LibreSSL 3.3.6, which cannot load an Ed25519 key.
_RFC8032_PEM = (
    "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAPUAXw+hDiVqStwqnTRt+vJyYLM8uxJaMwM1V8Sr0Zgw=\n"
    "-----END PUBLIC KEY-----\n"
)
_RFC8032_SIG = (
    "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
    "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"
)


def install_constant(name: str) -> str:
    m = re.search(rf"(?m)^{name}='([^']*)'$", INSTALL_SH.read_text())
    assert m, name
    return m[1]


def _openssl_fallbacks() -> list[str]:
    m = re.search(r'(?m)^OPENSSL_FALLBACKS="([^"]*)"$', INSTALL_SH.read_text())  # AT-V13 pins the seam
    return [hit for pat in (m[1].split() if m else []) for hit in sorted(glob.glob(pat))]


def ed25519_openssl(candidates=None) -> str | None:
    """First candidate that accepts the RFC 8032 signature on 0x72 and rejects it on 0x73."""
    if candidates is None:
        candidates = [shutil.which("openssl"), shutil.which("openssl3"), *_openssl_fallbacks()]
    for cand in filter(None, candidates):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "pub.pem").write_text(_RFC8032_PEM)
            (Path(d) / "sig").write_bytes(bytes.fromhex(_RFC8032_SIG))

            def ok(msg: bytes, d=d, cand=cand) -> bool:
                (Path(d) / "m").write_bytes(msg)
                cmd = [cand, "pkeyutl", "-verify", "-pubin", "-inkey", f"{d}/pub.pem", "-rawin"]
                try:
                    r = subprocess.run(
                        [*cmd, "-in", f"{d}/m", "-sigfile", f"{d}/sig"],
                        stdin=subprocess.DEVNULL, capture_output=True, timeout=20, check=False,
                    )
                except OSError:
                    return False
                return r.returncode == 0

            if ok(b"r") and not ok(b"s"):
                return cand
    return None


def usable_ssh_keygen(candidates=None) -> str | None:
    """First candidate that passes the installer's committed SSHSIG known answer on 0x72 and fails 0x73."""
    if candidates is None:
        candidates = [shutil.which("ssh-keygen"), "/usr/bin/ssh-keygen"]
    for cand in filter(None, candidates):
        with tempfile.TemporaryDirectory() as d:
            sig = Path(d) / "sig"
            sig.write_text(install_constant("KAT_SSHSIG") + "\n")
            blob = install_constant("KAT_SSH_PUBKEY")
            try:
                good = ssh_verify(Path(d), blob, sig, b"r", binary=cand).returncode == 0
                bad = ssh_verify(Path(d), blob, sig, b"s", binary=cand).returncode == 0
            except OSError:
                continue
            if good and not bad:
                return cand
    return None


REAL_OPENSSL = ed25519_openssl()
REAL_SSH_KEYGEN = usable_ssh_keygen()
needs_openssl_route = pytest.mark.skipif(not REAL_OPENSSL, reason="needs an Ed25519-capable openssl")
needs_sshsig_route = pytest.mark.skipif(not REAL_SSH_KEYGEN, reason="needs a usable ssh-keygen")
