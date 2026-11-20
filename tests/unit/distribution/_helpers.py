"""Shared fixtures for the release-signing tests. MAC-V1a reuses `_signed_release`."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
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


def ssh_verify(tmp_path: Path, blob: str, sig: Path, data: bytes):
    """The contract's verify command (design note 4) against a one-line allowed_signers file."""
    signers = tmp_path / "allowed_signers"
    signers.write_text(f'{IDENTITY} namespaces="{NAMESPACE}" ssh-ed25519 {blob}\n')
    cmd = [
        "ssh-keygen",
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
