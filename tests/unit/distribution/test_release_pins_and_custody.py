"""UK1a of the UPGRADE-KEY plan: the backup pin (AT-UK1-17), the shared pin fixture and custody
commands (AT-UK1-31), the error leaf (AT-UK1-32), `signing.fingerprint` and `.gitattributes`."""

from __future__ import annotations

import ast
import getpass
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from packaging_tools import sign_release
from tests.conftest import public_pem

from decoy.distribution import errors, installer, release_key, signing

ROOT = Path(__file__).resolve().parents[3]
DIST = ROOT / "src" / "decoy" / "distribution"
RAW = (serialization.Encoding.Raw, serialization.PublicFormat.Raw)


# ---------------------------------------------------------------- signing.fingerprint (R2-M2)
def test_fingerprint_is_sha256_of_the_raw_key_in_lower_hex():
    key = Ed25519PrivateKey.generate()
    raw = key.public_key().public_bytes(*RAW)
    assert signing.raw_public_bytes(public_pem(key)) == raw
    assert signing.fingerprint(public_pem(key)) == hashlib.sha256(raw).hexdigest()


def test_fingerprint_ignores_pem_wrapping_and_rejects_non_ed25519():
    key = Ed25519PrivateKey.generate()
    crlf = public_pem(key).replace("\n", "\r\n")
    assert signing.fingerprint(crlf) == signing.fingerprint(public_pem(key))
    with pytest.raises(ValueError):
        signing.fingerprint("not a pem")


def test_the_private_helper_is_renamed_without_an_alias():
    assert not hasattr(signing, "_raw_public_bytes_from_pem")
    for path in (ROOT / "packaging_tools" / "sign_release.py", *DIST.glob("*.py")):
        assert "_raw_public_bytes_from_pem" not in path.read_text(encoding="utf-8"), path.name


# ---------------------------------------------------------------- AT-UK1-17: the backup pin
BACKUP_MARK = "__DECOY_RELEASE_BACKUP_PUBLIC_KEY__"


def _placeholder(path: Path, marker: str) -> Path:
    path.write_text(
        f"-----BEGIN PUBLIC KEY-----\n{marker}\n-----END PUBLIC KEY-----\n", encoding="utf-8"
    )
    return path


def test_the_committed_backup_pin_is_the_placeholder_until_the_owner_commits_the_key():
    text = (DIST / "release_backup_key.pub.pem").read_text(encoding="utf-8")
    assert BACKUP_MARK in text
    assert release_key.BACKUP_PLACEHOLDER_MARKER == BACKUP_MARK


def test_backup_override_is_honored_with_a_warning_while_both_pins_are_placeholders(
    tmp_path, monkeypatch, capsys
):
    override = tmp_path / "b.pem"
    override.write_text(public_pem(Ed25519PrivateKey.generate()), encoding="utf-8")
    monkeypatch.setattr(
        release_key, "_KEY_FILE", _placeholder(tmp_path / "m.pem", release_key.PLACEHOLDER_MARKER)
    )
    monkeypatch.setattr(
        release_key, "_BACKUP_KEY_FILE", _placeholder(tmp_path / "bk.pem", BACKUP_MARK)
    )
    monkeypatch.setenv("DECOY_RELEASE_BACKUP_PUBKEY_FILE", str(override))
    assert release_key.pinned_backup_pem() == override.read_text(encoding="utf-8")
    assert "WARNING" in capsys.readouterr().err


def test_backup_override_is_ignored_with_a_warning_when_a_real_backup_key_is_committed(
    tmp_path, monkeypatch, capsys, release_pins
):
    override = tmp_path / "evil.pem"
    override.write_text(public_pem(Ed25519PrivateKey.generate()), encoding="utf-8")
    monkeypatch.setenv("DECOY_RELEASE_BACKUP_PUBKEY_FILE", str(override))
    assert release_key.pinned_backup_pem() == public_pem(release_pins.b)
    assert "IGNORED" in capsys.readouterr().err


def test_backup_override_is_ignored_when_the_backup_is_a_placeholder_but_the_main_pin_is_real(
    tmp_path, monkeypatch, capsys, release_pins
):
    override = tmp_path / "evil.pem"
    override.write_text(public_pem(Ed25519PrivateKey.generate()), encoding="utf-8")
    monkeypatch.setattr(
        release_key, "_BACKUP_KEY_FILE", _placeholder(tmp_path / "bk.pem", BACKUP_MARK)
    )
    monkeypatch.setenv("DECOY_RELEASE_BACKUP_PUBKEY_FILE", str(override))
    with pytest.raises(release_key.NoPinnedKeyError):
        release_key.pinned_backup_pem()
    assert "IGNORED" in capsys.readouterr().err


def test_a_placeholder_backup_with_no_override_raises_no_pinned_key(tmp_path, monkeypatch):
    monkeypatch.delenv("DECOY_RELEASE_BACKUP_PUBKEY_FILE", raising=False)
    monkeypatch.setattr(
        release_key, "_BACKUP_KEY_FILE", _placeholder(tmp_path / "bk.pem", BACKUP_MARK)
    )
    with pytest.raises(release_key.NoPinnedKeyError):
        release_key.pinned_backup_pem()


def test_the_main_override_rules_are_unchanged(tmp_path, monkeypatch):
    override = tmp_path / "o.pem"
    override.write_text(public_pem(Ed25519PrivateKey.generate()), encoding="utf-8")
    monkeypatch.setattr(
        release_key, "_KEY_FILE", _placeholder(tmp_path / "m.pem", release_key.PLACEHOLDER_MARKER)
    )
    monkeypatch.setenv("DECOY_RELEASE_PUBKEY_FILE", str(override))
    assert release_key.pinned_public_pem() == override.read_text(encoding="utf-8")


# ----------------------------------------------------------- the shared fixture (R2-H3)
def test_the_fixture_pins_through_module_paths_and_ignores_environment_seams(
    release_pins, monkeypatch, tmp_path
):
    other = tmp_path / "other.pem"
    other.write_text(public_pem(Ed25519PrivateKey.generate()), encoding="utf-8")
    monkeypatch.setenv("DECOY_RELEASE_PUBKEY_FILE", str(other))
    monkeypatch.setenv("DECOY_RELEASE_BACKUP_PUBKEY_FILE", str(other))
    assert release_key.pinned_public_pem() == release_pins.pem(release_pins.k1)
    assert release_key.pinned_backup_pem() == release_pins.pem(release_pins.b)
    assert release_pins.k1 is not release_pins.k2 is not release_pins.k3


# ---------------------------------------------------------------- AT-UK1-31: custody commands
def _answers(monkeypatch, *answers: str) -> list[str]:
    queue, prompts = list(answers), []

    def fake(prompt: str = "") -> str:
        prompts.append(prompt)
        return queue.pop(0)

    monkeypatch.setattr(getpass, "getpass", fake)
    return prompts


def test_keygen_encrypt_writes_an_encrypted_key_that_needs_the_passphrase(
    tmp_path, monkeypatch, capsys
):
    _answers(monkeypatch, "correct horse", "correct horse")
    out, pub = tmp_path / "b.key", tmp_path / "b.pub"
    assert sign_release.main(["keygen", "--encrypt", "--out", str(out), "--pub", str(pub)]) == 0
    data = out.read_bytes()
    assert data.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----")
    assert oct(out.stat().st_mode & 0o777) == "0o600"
    with pytest.raises(TypeError):
        serialization.load_pem_private_key(data, password=None)
    with pytest.raises(ValueError):
        serialization.load_pem_private_key(data, password=b"wrong")
    key = serialization.load_pem_private_key(data, password=b"correct horse")
    assert public_pem(key) == pub.read_text()
    seen = capsys.readouterr()
    assert "correct horse" not in seen.out + seen.err and data.decode() not in seen.out + seen.err


def test_keygen_encrypt_refuses_a_mismatched_or_empty_passphrase_and_writes_nothing(
    tmp_path, monkeypatch
):
    out = tmp_path / "b.key"
    _answers(monkeypatch, "one", "two")
    assert sign_release.main(["keygen", "--encrypt", "--out", str(out)]) != 0
    _answers(monkeypatch, "", "")
    assert sign_release.main(["keygen", "--encrypt", "--out", str(out)]) != 0
    assert not out.exists()


def test_keygen_without_encrypt_is_unchanged(tmp_path, monkeypatch):
    _answers(monkeypatch)  # any prompt would pop an empty queue and fail
    out = tmp_path / "k.key"
    assert sign_release.main(["keygen", "--out", str(out)]) == 0
    assert out.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----")


def _encrypted_key(path: Path, key: Ed25519PrivateKey, password: bytes = b"pw") -> Path:
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(password),
        )
    )
    return path


def test_backup_check_prints_only_the_fingerprint_when_the_key_matches_the_pin(
    tmp_path, monkeypatch, capsys, release_pins
):
    f = _encrypted_key(tmp_path / "b.key", release_pins.b)
    _answers(monkeypatch, "pw")
    assert sign_release.main(["backup-check", "--backup-key-file", str(f)]) == 0
    seen = capsys.readouterr()
    assert seen.out == signing.fingerprint(release_pins.pem(release_pins.b)) + "\n"
    assert "pw" not in seen.err and "PRIVATE" not in seen.out + seen.err


@pytest.mark.parametrize(
    "case", ["other key", "wrong passphrase", "not encrypted", "placeholder pin"]
)
def test_backup_check_exits_one_with_one_fixed_line_otherwise(
    tmp_path, monkeypatch, capsys, release_pins, case
):
    key = Ed25519PrivateKey.generate() if case == "other key" else release_pins.b
    f = _encrypted_key(tmp_path / "b.key", key)
    answer = "bad" if case == "wrong passphrase" else "pw"
    if case == "not encrypted":
        f.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    if case == "placeholder pin":
        monkeypatch.setattr(
            release_key, "_BACKUP_KEY_FILE", _placeholder(tmp_path / "bk.pem", BACKUP_MARK)
        )
    _answers(monkeypatch, answer)
    assert sign_release.main(["backup-check", "--backup-key-file", str(f)]) == 1
    seen = capsys.readouterr()
    assert seen.out == "" and len(seen.err.strip().splitlines()) == 1
    if case == "placeholder pin":
        # Not "does not match": no backup key is committed yet, and the line says what to do.
        assert (
            seen.err.strip()
            == "backup-check: no backup key is committed yet; commit the public half first"
        )
    else:
        assert "does not match the committed backup key" in seen.err
    text = seen.err
    for secret in (answer, str(f), signing.fingerprint(release_pins.pem(release_pins.b))):
        assert secret not in text


def test_backup_check_reads_the_module_pin_not_the_installed_file(release_pins):
    src = (ROOT / "packaging_tools" / "sign_release.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_cmd_backup_check"
    )
    body = ast.get_source_segment(src, fn)
    assert "pinned_backup_pem" in body and "release_backup_key.pub.pem" not in body


# ------------------------------------------------------- AT-UK1-32: the acyclic error leaf
def _fresh(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)


MODULES = ["installer", "version_document", "errors"] + (
    ["key_rotation"] if importlib.util.find_spec("decoy.distribution.key_rotation") else []
)


@pytest.mark.parametrize("order", [MODULES, list(reversed(MODULES))])
def test_the_modules_import_in_both_orders_in_a_fresh_process(order):
    code = "; ".join(f"import decoy.distribution.{m}" for m in order)
    r = _fresh(code)
    assert r.returncode == 0, r.stderr


def test_install_error_is_the_leaf_class_and_installer_re_exports_it():
    assert installer.InstallError is errors.InstallError
    assert issubclass(errors.InstallError, RuntimeError)
    assert errors.InstallError.__module__ == "decoy.distribution.errors"


def test_the_error_leaf_imports_no_distribution_module():
    tree = ast.parse((DIST / "errors.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [("." * node.level) + (node.module or "")] + [a.name for a in node.names]
        for name in names:
            assert "decoy" not in name and not name.startswith("."), name


@pytest.mark.skipif(
    importlib.util.find_spec("decoy.distribution.key_rotation") is None,
    reason="key_rotation lands in the next slice (UK1b); this row is paired with it",
)
def test_trust_refusal_is_an_install_error():
    from decoy.distribution import key_rotation

    assert issubclass(key_rotation.TrustRefusal, errors.InstallError)


# ------------------------------------------------------------------------- .gitattributes
def test_gitattributes_keeps_key_files_byte_exact():
    rules = {
        tuple(line.split())
        for line in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    for pattern in ("src/decoy/distribution/*.pub.pem", "src/decoy/distribution/key_rotation.json"):
        assert (pattern, "text", "eol=lf") in rules, pattern


# ---------------------------------------------------- unknown-OID keys never escape (Dennis M1)
def _unknown_oid_pem() -> str:
    import base64

    der = serialization.load_pem_public_key(
        public_pem(Ed25519PrivateKey.generate()).encode()
    ).public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    assert der.count(bytes.fromhex("2b6570")) == 1
    der = der.replace(bytes.fromhex("2b6570"), bytes.fromhex("2b6578"))  # OID 1.3.101.120, unknown
    body = base64.encodebytes(der).decode().strip()
    return f"-----BEGIN PUBLIC KEY-----\n{body}\n-----END PUBLIC KEY-----\n"


def test_an_unknown_oid_key_is_a_value_error_with_no_context():
    from cryptography.exceptions import UnsupportedAlgorithm

    pem = _unknown_oid_pem()
    with pytest.raises(UnsupportedAlgorithm):  # the precondition: the library really raises this
        serialization.load_pem_public_key(pem.encode())
    for call in (signing.raw_public_bytes, signing.fingerprint):
        with pytest.raises(ValueError) as info:
            call(pem)
        assert info.value.__cause__ is None and info.value.__context__ is None


def test_verify_functions_return_false_for_an_unknown_oid_key():
    pem = _unknown_oid_pem()
    assert signing.verify_detached(b"x", "AAAA", expected_public_pem=pem) is False
    key = Ed25519PrivateKey.generate()
    envelope = {
        "alg": "ed25519",
        "payload": {"schema_version": "s"},
        "signature": "AAAA",
        "public_key": public_pem(key),
    }
    assert signing.verify_envelope(envelope, expected_public_pem=pem, schema_version="s") is False
    envelope["public_key"] = pem
    assert (
        signing.verify_envelope(envelope, expected_public_pem=public_pem(key), schema_version="s")
        is False
    )


def test_a_trust_state_with_an_unknown_oid_main_key_is_the_fixed_refusal(tmp_path):
    import json

    from decoy.distribution import errors, trust_state

    (tmp_path / "trust_state.json").write_text(
        json.dumps(
            {"serial": 1, "key_epoch": 2, "main_key": _unknown_oid_pem(), "revoked_keys": []}
        )
    )
    with pytest.raises(errors.InstallError, match="trust state unreadable"):
        trust_state.read_trust_state(tmp_path)


# ------------------------------------------- one loader behind both pins (Codex, class 8)
MAIN_MARK = release_key.PLACEHOLDER_MARKER
_KEYS = {
    "main": SimpleNamespace(
        attr="_KEY_FILE",
        mark=MAIN_MARK,
        env="DECOY_RELEASE_PUBKEY_FILE",
        load=release_key.pinned_public_pem,
        label="release",
    ),
    "backup": SimpleNamespace(
        attr="_BACKUP_KEY_FILE",
        mark=BACKUP_MARK,
        env="DECOY_RELEASE_BACKUP_PUBKEY_FILE",
        load=release_key.pinned_backup_pem,
        label="backup",
    ),
}


@pytest.fixture(params=sorted(_KEYS))
def pin(request, tmp_path, monkeypatch):
    """A key under test, with both pins starting as dev placeholders and no override set."""
    spec = _KEYS[request.param]
    monkeypatch.setattr(release_key, "_KEY_FILE", _placeholder(tmp_path / "m.pem", MAIN_MARK))
    monkeypatch.setattr(
        release_key, "_BACKUP_KEY_FILE", _placeholder(tmp_path / "b.pem", BACKUP_MARK)
    )
    for k in _KEYS.values():
        monkeypatch.delenv(k.env, raising=False)
    spec.dir = tmp_path
    spec.file = lambda: getattr(release_key, spec.attr)
    return spec


def _commit_real(pin, monkeypatch) -> str:
    real = public_pem(Ed25519PrivateKey.generate())
    path = pin.dir / f"real-{pin.label}.pem"
    path.write_text(real, encoding="utf-8")
    monkeypatch.setattr(release_key, pin.attr, path)
    return real


def test_core_a_missing_pin_file_is_an_error_not_a_silent_accept(pin, monkeypatch):
    monkeypatch.setattr(release_key, pin.attr, pin.dir / "absent.pem")
    with pytest.raises(OSError):
        pin.load()


def test_core_a_placeholder_with_no_override_refuses_with_a_fixed_line(pin):
    with pytest.raises(release_key.NoPinnedKeyError) as info:
        pin.load()
    assert str(info.value) == (
        f"this decoy build has no pinned {pin.label} key (placeholder present); "
        f"a release build commits it. Dev/test builds may set {pin.env}."
    )


def test_core_a_dev_override_is_honored_with_a_fixed_warning_that_names_no_path(
    pin, monkeypatch, capsys
):
    override = pin.dir / "secret-dir-name.pem"
    override.write_text(public_pem(Ed25519PrivateKey.generate()), encoding="utf-8")
    monkeypatch.setenv(pin.env, str(override))
    assert pin.load() == override.read_text(encoding="utf-8")
    err = capsys.readouterr().err
    assert pin.env in err and "WARNING" in err and "dev/test build" in err
    assert str(pin.dir) not in err and "secret-dir-name" not in err


def test_core_an_override_in_a_release_build_is_ignored_with_a_fixed_warning(
    pin, monkeypatch, capsys
):
    real = _commit_real(pin, monkeypatch)
    if pin.label == "backup":  # the main pin must stay a placeholder-free release pin too
        _commit_main = public_pem(Ed25519PrivateKey.generate())
        (pin.dir / "main-real.pem").write_text(_commit_main, encoding="utf-8")
        monkeypatch.setattr(release_key, "_KEY_FILE", pin.dir / "main-real.pem")
    override = pin.dir / "evil-dir-name.pem"
    override.write_text(public_pem(Ed25519PrivateKey.generate()), encoding="utf-8")
    monkeypatch.setenv(pin.env, str(override))
    assert pin.load() == real
    err = capsys.readouterr().err
    assert "IGNORED" in err and pin.env in err
    assert str(pin.dir) not in err and "evil-dir-name" not in err


def test_core_a_set_but_empty_override_counts_as_unset(pin, monkeypatch, capsys):
    monkeypatch.setenv(pin.env, "")
    with pytest.raises(release_key.NoPinnedKeyError):
        pin.load()
    assert capsys.readouterr().err == ""


def test_both_entry_points_load_through_the_one_private_core():
    src = (DIST / "release_key.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for name in ("pinned_public_pem", "pinned_backup_pem"):
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
        called = {
            c.func.id
            for c in ast.walk(fn)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
        }
        assert "_load_pin" in called, name
        assert not any(
            isinstance(n, ast.Attribute) and n.attr == "read_text" for n in ast.walk(fn)
        ), name


def test_verify_detached_returns_false_for_a_non_string_expected_key():
    for bad in (None, 5, b"-----BEGIN PUBLIC KEY-----", ["x"]):
        assert signing.verify_detached(b"x", "AAAA", expected_public_pem=bad) is False  # type: ignore[arg-type]
