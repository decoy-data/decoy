"""Release signing: Ed25519 key custody + detached signatures (build host only).

Established methodology: Ed25519 via `cryptography`, the same scheme and key format as
the platform's output-passport / air-gapped-manifest signer
(`decoy-platform/api/passport/signing.py`, `api/crypto/signed_envelope.py`). No
hand-rolled crypto. The verify side ships in `decoy.distribution.signing`; this is the only
place a private key is ever read.

Key custody (config-secrets-and-supply-chain): the private key is sourced from the
environment, NEVER committed. ``DECOY_RELEASE_KEY_FILE`` points at a PEM/PKCS8 private
key (0600) held in the release secret store; ``DECOY_RELEASE_KEY_PEM`` may carry the
PEM inline for a CI secret. The public key is published in the repo
(`packaging_tools/release-key (public half shipped in the CLI)`) and on the site, and is what `install.sh` pins and
`decoy upgrade` trusts. Rotation: generate a new key, publish the new public key in a
signed release, and keep the old public key in a documented trust set for one
deprecation window so in-flight installers still verify prior releases.

Signatures are DETACHED and over the EXACT on-disk bytes of the file being signed, so
the identical signature verifies three ways: `openssl pkeyutl -verify -rawin` in the
shell installer, `decoy.distribution.signing.verify_detached` in `decoy upgrade`, and the
platform primitive on an auditor's host.

A second sidecar, ``<file>.sshsig``, carries the same key's signature in the SSHSIG format
(PROTOCOL.sshsig, OpenSSH 8.1+), made by the established ``ssh-keygen -Y sign`` and checked by
``ssh-keygen -Y verify``. It exists for hosts that ship ``ssh-keygen`` but an OpenSSL too old for
``pkeyutl -rawin`` (stock macOS). ``pubkeys``/``inject-keys``/``check-keys`` keep the two pinned
forms of the public key in ``install.sh`` as one key; ``sshsig`` writes the sidecar.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

# Single source of truth for the public key: the one shipped in the CLI package
# (also what `decoy upgrade` pins). install.sh embeds a copy of the same key.
_PUBLIC_KEY_FILE = (
    Path(__file__).resolve().parents[1] / "src" / "decoy" / "distribution" / "release_key.pub.pem"
)


def load_private_key() -> Ed25519PrivateKey:
    """Load the release private key from the environment. Raises if neither source is
    set -- signing must never silently proceed without the real release key."""
    pem_inline = os.environ.get("DECOY_RELEASE_KEY_PEM")
    key_file = os.environ.get("DECOY_RELEASE_KEY_FILE")
    if pem_inline:
        data = pem_inline.encode("utf-8")
    elif key_file:
        data = Path(key_file).read_bytes()
    else:
        raise RuntimeError(
            "no release signing key: set DECOY_RELEASE_KEY_FILE or DECOY_RELEASE_KEY_PEM"
        )
    key = serialization.load_pem_private_key(data, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("release key is not an Ed25519 private key")
    return key


_PEM_PLACEHOLDER = "__DECOY_RELEASE_PUBLIC_KEY__"
_SSH_PLACEHOLDER = "__DECOY_RELEASE_SSH_PUBLIC_KEY__"
_SSHSIG_NAMESPACE = "decoy-release"
_PEM_RE = re.compile(r"^PINNED_PUBKEY='-----BEGIN PUBLIC KEY-----\n(.*?)\n-----END PUBLIC KEY-----'", re.M | re.S)
_SSH_RE = re.compile(r"^PINNED_SSH_PUBKEY='([^'\n]*)'", re.M)
# One fixed line per failure: key material or tool output must never reach a CI log.
_KEYS_BAD = "release keys in install.sh are not one valid key"


def public_key_pem(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def published_public_key_pem() -> str:
    """The committed public key the installer pins. Build tooling asserts the loaded
    private key matches this before signing, so a release can never be signed with a key
    the installer will not trust."""
    return _PUBLIC_KEY_FILE.read_text(encoding="utf-8")


def sign_bytes(data: bytes, key: Ed25519PrivateKey) -> str:
    """Return a base64 detached Ed25519 signature over exactly ``data``."""
    return base64.b64encode(key.sign(data)).decode("ascii")


def sign_file(path: str | Path, key: Ed25519PrivateKey) -> Path:
    """Write ``<path>.sig`` holding the base64 detached signature over the file's bytes.
    Returns the signature path."""
    path = Path(path)
    sig = sign_bytes(path.read_bytes(), key)
    sig_path = path.with_name(path.name + ".sig")
    sig_path.write_text(sig + "\n", encoding="utf-8")
    return sig_path


def _public_forms(pub: Ed25519PublicKey) -> tuple[str, str]:
    pem = pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    ssh = pub.public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
    return "".join(pem.decode("ascii").splitlines()[1:-1]), ssh.decode("ascii").split()[1]


def pinned_forms(key: Ed25519PrivateKey) -> tuple[str, str]:
    """The two forms install.sh pins for one key: the PEM body line and the base64 ssh-ed25519 blob."""
    return _public_forms(key.public_key())


def check_keys(text: str) -> None:
    """Raise ValueError unless install.sh pins one valid Ed25519 key in both forms. Each pinned
    string must equal the form re-derived from the PEM key, character for character: a lenient
    base64 decoder would accept a stray character that ssh-keygen rejects. A placeholder is
    checked by name for the same reason."""
    # Exactly one assignment of each: the shell runs the last one, so a validated first
    # assignment would say nothing about the key the installer really uses.
    pems, sshs = _PEM_RE.findall(text), _SSH_RE.findall(text)
    if len(pems) != 1 or len(sshs) != 1 or text.count("PINNED_PUBKEY=") != 1 or text.count("PINNED_SSH_PUBKEY=") != 1:
        raise ValueError(_KEYS_BAD)
    pem_body, ssh_body = pems[0], sshs[0]
    if _PEM_PLACEHOLDER in pem_body or _SSH_PLACEHOLDER in ssh_body:
        raise ValueError(_KEYS_BAD)
    try:
        key = serialization.load_pem_public_key(
            f"-----BEGIN PUBLIC KEY-----\n{pem_body}\n-----END PUBLIC KEY-----\n".encode()
        )
    except Exception:
        raise ValueError(_KEYS_BAD) from None
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError(_KEYS_BAD)
    pem_form, ssh_form = _public_forms(key)
    if (pem_body, ssh_body) != (pem_form, ssh_form):
        raise ValueError(_KEYS_BAD)


def sshsig_file(path: str | Path, out: str | Path, key: Ed25519PrivateKey) -> None:
    """Write the SSHSIG over ``path`` to ``out`` via ``ssh-keygen -Y sign`` (stdin form, so it
    never writes ``<path>.sig``). The output is a 0600 temp file beside ``out`` and is renamed
    over it only after a clean exit, so a failed run leaves an existing ``out`` untouched."""
    out = Path(out)
    keydir = Path(tempfile.mkdtemp(prefix="decoy-sshsig-"))
    tmpout: str | None = None
    try:
        keyfile = keydir / "key"
        fd = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.OpenSSH,
                    serialization.NoEncryption(),
                )
            )
        # Open the input first so a missing file cannot leak the temp file's descriptor.
        with open(path, "rb") as fin:
            fd, tmpout = tempfile.mkstemp(dir=out.parent, prefix=out.name + ".", suffix=".tmp")
            with os.fdopen(fd, "wb") as fout:
                r = subprocess.run(
                    ["ssh-keygen", "-Y", "sign", "-f", str(keyfile), "-n", _SSHSIG_NAMESPACE],
                    stdin=fin, stdout=fout, stderr=subprocess.DEVNULL, check=False,
                )
        if r.returncode != 0:
            raise RuntimeError("ssh-keygen failed")
        # mkstemp makes 0600; a sidecar is a public download like its .sig, so publish it 0644.
        os.chmod(tmpout, 0o644)
        os.replace(tmpout, out)
        tmpout = None
    finally:
        shutil.rmtree(keydir, ignore_errors=True)
        if tmpout:
            Path(tmpout).unlink(missing_ok=True)


def _write_atomic(out: str | Path, text: str) -> None:
    """Write ``out`` through a temp file in its directory so a failure leaves nothing behind."""
    out = Path(out)
    fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=out.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, out)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _key_file(path: str) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("not an Ed25519 key")
    return key


def _cmd_pubkeys(args: argparse.Namespace) -> int:
    pem, ssh = pinned_forms(_key_file(args.key))
    sys.stdout.write(json.dumps({"pem": pem, "ssh": ssh}) + "\n")
    return 0


def _cmd_inject_keys(args: argparse.Namespace) -> int:
    text = Path(args.infile).read_text(encoding="utf-8")
    # Exactly one of each: replacing a second copy (a literal in a case pattern, say) would make
    # the released installer read its own real key as a placeholder.
    if text.count(_PEM_PLACEHOLDER) != 1 or text.count(_SSH_PLACEHOLDER) != 1:
        raise ValueError("placeholder missing or repeated")
    pem, ssh = pinned_forms(_key_file(args.key))
    text = text.replace(_PEM_PLACEHOLDER, pem).replace(_SSH_PLACEHOLDER, ssh)
    check_keys(text)
    _write_atomic(args.out, text)
    return 0


def _cmd_check_keys(args: argparse.Namespace) -> int:
    check_keys(Path(args.installer).read_text(encoding="utf-8"))
    sys.stdout.write("release keys ok\n")
    return 0


def _cmd_sshsig(args: argparse.Namespace) -> int:
    sshsig_file(args.infile, args.out, load_private_key())
    return 0


def _new_passphrase() -> bytes | None:
    """Ask twice, without echo. None (nothing written) on a mismatch or an empty passphrase."""
    first = getpass.getpass("passphrase for the new key: ")
    if not first or first != getpass.getpass("repeat the passphrase: "):
        return None
    return first.encode("utf-8")


def _cmd_keygen(args: argparse.Namespace) -> int:
    """Dev/bootstrap helper: generate a release keypair. Writes the private key 0600 and
    prints the public key (to commit as release-key.pub.pem). The real launch key is
    generated once in the secret store, not here. ``--encrypt`` asks for a passphrase and writes
    encrypted PKCS8, for the offline backup key."""
    key = Ed25519PrivateKey.generate()
    protection: serialization.KeySerializationEncryption = serialization.NoEncryption()
    if args.encrypt:
        passphrase = _new_passphrase()
        if passphrase is None:
            sys.stderr.write("keygen: passphrases differ or are empty; no key written\n")
            return 2
        protection = serialization.BestAvailableEncryption(passphrase)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=protection,
    )
    out = Path(args.out)
    fd = os.open(str(out), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(priv_pem)
    pub = public_key_pem(key)
    if args.pub:
        Path(args.pub).write_text(pub, encoding="utf-8")
    sys.stderr.write(f"wrote private key (0600) to {out}\n")
    sys.stdout.write(pub)
    return 0


_BACKUP_BAD = "backup-check: failed; the key file does not match the committed backup key"


def _cmd_backup_check(args: argparse.Namespace) -> int:
    """Restore test for the offline backup key: decrypt the file and confirm its public half is
    the committed backup pin. Prints the fingerprint only. One fixed line and exit 1 on any
    failure; the passphrase, the path and key bytes never reach output."""
    from decoy.distribution import release_key, signing

    try:
        data = Path(args.backup_key_file).read_bytes()
        if not data.lstrip().startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----"):
            raise ValueError("not encrypted")
        key = serialization.load_pem_private_key(
            data, password=getpass.getpass("backup key passphrase: ").encode("utf-8")
        )
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("not Ed25519")
        pinned = signing.fingerprint(release_key.pinned_backup_pem())
        if signing.fingerprint(public_key_pem(key)) != pinned:
            raise ValueError("pin mismatch")
    except Exception:
        sys.stderr.write(_BACKUP_BAD + "\n")
        return 1
    sys.stdout.write(pinned + "\n")
    return 0


def _cmd_sign(args: argparse.Namespace) -> int:
    key = load_private_key()
    if args.assert_published:
        from decoy.distribution.signing import raw_public_bytes

        if raw_public_bytes(public_key_pem(key)) != raw_public_bytes(
            published_public_key_pem()
        ):
            sys.stderr.write("refusing to sign: loaded key != committed release-key.pub.pem\n")
            return 2
    for f in args.files:
        sig_path = sign_file(f, key)
        sys.stderr.write(f"signed {f} -> {sig_path}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sign_release")
    sub = ap.add_subparsers(dest="cmd", required=True)
    kg = sub.add_parser("keygen", help="generate a release keypair")
    kg.add_argument("--out", required=True, help="private key output path (written 0600)")
    kg.add_argument("--pub", help="also write the public key PEM here")
    kg.add_argument(
        "--encrypt", action="store_true", help="protect the private key with a passphrase (asked twice)"
    )
    kg.set_defaults(func=_cmd_keygen)
    sg = sub.add_parser("sign", help="detached-sign one or more files")
    sg.add_argument("files", nargs="+")
    sg.add_argument(
        "--assert-published",
        action="store_true",
        help="refuse unless the loaded key matches the committed public key",
    )
    sg.set_defaults(func=_cmd_sign)
    for name, func, helptext in (
        ("pubkeys", _cmd_pubkeys, "print both public forms of a key as JSON"),
        ("inject-keys", _cmd_inject_keys, "fill both key placeholders in install.sh"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--key", required=True, help="private key PEM")
        if name == "inject-keys":
            p.add_argument("--in", dest="infile", required=True)
            p.add_argument("--out", required=True)
        p.set_defaults(func=func)
    ck = sub.add_parser("check-keys", help="fail unless install.sh pins one key in both forms")
    ck.add_argument("installer")
    ck.set_defaults(func=_cmd_check_keys)
    ss = sub.add_parser("sshsig", help="write an SSHSIG sidecar (key from the sign env vars)")
    ss.add_argument("--in", dest="infile", required=True)
    ss.add_argument("--out", required=True)
    ss.set_defaults(func=_cmd_sshsig)
    bc = sub.add_parser("backup-check", help="confirm an encrypted backup key file matches the committed pin")
    bc.add_argument("--backup-key-file", required=True, help="encrypted PKCS8 backup private key")
    bc.set_defaults(func=_cmd_backup_check)
    args = ap.parse_args(argv)
    if args.cmd in {"pubkeys", "inject-keys", "check-keys", "sshsig"}:
        try:
            return args.func(args)
        except Exception:
            sys.stderr.write(f"{args.cmd}: failed\n" if args.cmd != "check-keys" else _KEYS_BAD + "\n")
            return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
