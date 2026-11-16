"""install.sh verifier selection (MAC-V1a): the OpenSSL route, the SSHSIG route, exit 69.

Shims are small `sh` scripts in tmp_path. Tests that control the fallbacks run a copy of
install.sh with the one OPENSSL_FALLBACKS= line (and the ssh-keygen fallback line) rewritten.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import threading
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tests.unit.distribution._helpers import (
    INSTALL_SH,
    NAMESPACE,
    REAL_OPENSSL,
    REAL_SSH_KEYGEN,
    _openssl_fallbacks,
    _signed_release,
    ed25519_openssl,
    needs_openssl_route,
    needs_ssh_keygen,
    needs_sshsig_route,
    run_signer,
    usable_ssh_keygen,
    write_key,
)

from decoy.distribution import targets
from decoy.distribution import version_document as vd

pytestmark = pytest.mark.skipif(not shutil.which("curl"), reason="needs curl")
SH = shutil.which("sh") or "/bin/sh"
INVALID_VDOC = "version-document signature INVALID -- refusing (possible tampering)"
INVALID_BUNDLE = "bundle signature INVALID -- refusing (possible tampering)"


# ---------------------------------------------------------------------------- helpers
def _sh(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return path


def _libressl(d: Path, log: Path | None = None) -> Path:
    """`openssl` and `openssl3` that cannot load an Ed25519 key, like stock macOS."""
    note = f'echo "$0 $*" >> {log}\n' if log else ""
    body = note + 'case "$1" in version) echo "LibreSSL 3.3.6";; *) echo "unsupported algorithm" >&2; exit 1;; esac\n'
    _sh(d / "openssl3", body)
    return _sh(d / "openssl", body)


def _accept_all_openssl(path: Path, log: Path) -> Path:
    return _sh(path, f'echo "$0 $*" >> {log}\ncase "$1" in version) echo "OpenSSL 3.0.0 shim";;\n'
               'base64) while [ $# -gt 0 ]; do [ "$1" = -out ] && : > "$2"; shift; done;; esac\nexit 0\n')


def _wrap(path: Path, real: str, log: Path) -> Path:
    """Logs its own path and arguments, then runs the real tool with the same stdin."""
    return _sh(path, f'echo "$0 $*" >> {log}\nexec {real} "$@"\n')


def _variant(tmp_path: Path, script: Path, *, fallbacks: str = "", ssh_fallback: str = "/nonexistent/ssh-keygen") -> Path:
    text = script.read_text()
    text, n1 = re.subn(r'(?m)^OPENSSL_FALLBACKS=.*$', lambda _: f'OPENSSL_FALLBACKS="{fallbacks}"', text)
    text, n2 = re.subn(r'(?m)^SSH_KEYGEN_FALLBACK=.*$', lambda _: f'SSH_KEYGEN_FALLBACK="{ssh_fallback}"', text)
    assert (n1, n2) == (1, 1)
    out = tmp_path / "install_variant.sh"
    out.write_text(text)
    return out


def _env(tmp_path: Path, *dirs: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("DECOY_")}
    env.update(
        DECOY_HOME=str(tmp_path / "home"), DECOY_BIN_DIR=str(tmp_path / "bin"),
        PATH=os.pathsep.join([*map(str, dirs), env["PATH"]]),
    )
    env.update(extra)
    return env


def _run(script: Path, env: dict[str, str], *args: str, stdin=subprocess.DEVNULL):
    return subprocess.run([SH, str(script), *args], env=env, capture_output=True, text=True, stdin=stdin, timeout=120, check=False)


def _lines(log: Path) -> list[str]:
    return log.read_text().splitlines() if log.exists() else []


def _sha_sidecar(bundle: Path) -> Path:
    Path(f"{bundle}.sha256").write_text(f"{hashlib.sha256(bundle.read_bytes()).hexdigest()}  {bundle.name}\n")
    return bundle


def _local_bundle(rel) -> Path:
    return _sha_sidecar(rel.files[1])


def _force(kind: str, tmp_path: Path, rel) -> tuple[Path, dict[str, str], Path]:
    """Script and env that select `kind`: a capable openssl on PATH, or only the LibreSSL shim."""
    shims = tmp_path / "shims"
    if kind == "openssl":
        _wrap(shims / "openssl", REAL_OPENSSL, tmp_path / "ossl.log")
        return _variant(tmp_path, rel.install_sh), _env(tmp_path, shims), tmp_path / "ossl.log"
    _libressl(shims)
    return _variant(tmp_path, rel.install_sh, ssh_fallback=REAL_SSH_KEYGEN), _env(tmp_path, shims), tmp_path / "x"


# ---------------------------------------------------------------------- OpenSSL route
def test_at_v1_no_usable_verifier_exits_69_before_any_download(tmp_path):
    shims = tmp_path / "shims"
    _libressl(shims)
    script = _variant(tmp_path, INSTALL_SH)  # placeholder keys: no SSHSIG route
    r = _run(script, _env(tmp_path, shims, DECOY_VERSION_URL="file:///nonexistent/version.json"))
    assert r.returncode == 69, r.stderr
    assert "cannot verify Ed25519 signatures" in r.stderr and "Nothing was downloaded" in r.stderr
    assert re.search(r"tried: .*LibreSSL 3\.3\.6", r.stderr)
    for fix in ("macOS: /usr/bin/ssh-keygen", "Linux: OpenSSL 3.0 or newer", "DECOY_OPENSSL=/path/to/openssl sh install.sh"):
        assert fix in r.stderr
    assert "INVALID" not in r.stderr and "tampering" not in r.stderr
    assert not (tmp_path / "home").exists()


def test_at_v2_openssl_that_accepts_everything_is_rejected(tmp_path):
    shims, log = tmp_path / "shims", tmp_path / "log"
    _accept_all_openssl(shims / "openssl", log)
    r = _run(_variant(tmp_path, INSTALL_SH), _env(tmp_path, shims, DECOY_VERSION_URL="file:///nonexistent/v.json"))
    assert r.returncode == 69, r.stderr
    verifies = [x for x in _lines(log) if "pkeyutl" in x]
    assert len(verifies) == 2 and "/kat/good" in verifies[0] and "/kat/bad" in verifies[1]


@needs_openssl_route
@needs_ssh_keygen
def test_at_v3_fallback_candidate_is_used_when_path_openssl_is_incapable(tmp_path):
    rel, shims, log = _signed_release(tmp_path), tmp_path / "shims", tmp_path / "log"
    _libressl(shims)
    wrapper = _wrap(tmp_path / "fb" / "openssl", REAL_OPENSSL, log)
    script = _variant(tmp_path, rel.install_sh, fallbacks=str(wrapper), ssh_fallback="/nonexistent")
    r = _run(script, _env(tmp_path, shims, DECOY_VERSION_URL=f"file://{rel.files[0]}"))
    assert f"verifier: openssl {wrapper}" in r.stderr
    assert "version document signature verified" in r.stderr
    assert r.returncode == 1 and "unexpected schema_version" in r.stderr
    assert any(str(wrapper) in x and "pkeyutl" in x for x in _lines(log))


@needs_openssl_route
@needs_ssh_keygen
def test_at_v3b_bundle_check_uses_the_binary_that_passed(tmp_path):
    rel, shims, log = _signed_release(tmp_path), tmp_path / "shims", tmp_path / "log"
    _libressl(shims)
    wrapper = _wrap(tmp_path / "fb" / "openssl", REAL_OPENSSL, log)
    script = _variant(tmp_path, rel.install_sh, fallbacks=str(wrapper), ssh_fallback="/nonexistent")
    r = _run(script, _env(tmp_path, shims, DECOY_LOCAL_BUNDLE=str(_local_bundle(rel))))
    assert "bundle signature verified" in r.stderr, r.stderr
    verifies = [x for x in _lines(log) if "pkeyutl" in x]
    assert len(verifies) == 3 and all(x.startswith(str(wrapper)) for x in verifies)  # two known-answer calls, one check


@needs_openssl_route
@needs_ssh_keygen
def test_at_v4_invalid_signatures_keep_their_exit_code_and_text(tmp_path):
    rel = _signed_release(tmp_path)
    script, env, _ = _force("openssl", tmp_path, rel)
    rel.files[0].write_bytes(rel.files[0].read_bytes() + b" ")
    r = _run(script, {**env, "DECOY_VERSION_URL": f"file://{rel.files[0]}"})
    assert r.returncode == 1 and INVALID_VDOC in r.stderr
    bundle = _local_bundle(rel)
    bundle.write_bytes(bundle.read_bytes() + b" ")
    _sha_sidecar(bundle)
    r = _run(script, {**env, "DECOY_LOCAL_BUNDLE": str(bundle)})
    assert r.returncode == 1 and INVALID_BUNDLE in r.stderr


@needs_openssl_route
@needs_ssh_keygen
def test_at_v5_decoy_openssl_is_the_only_candidate_and_runs_every_check(tmp_path):
    rel, shims, log, bare = _signed_release(tmp_path), tmp_path / "shims", tmp_path / "log", tmp_path / "bare"
    _libressl(shims, bare)
    wrapper = _wrap(tmp_path / "named" / "openssl", REAL_OPENSSL, log)
    script = _variant(tmp_path, rel.install_sh)
    env = _env(tmp_path, shims, DECOY_OPENSSL=str(wrapper), DECOY_LOCAL_BUNDLE=str(_local_bundle(rel)))
    r = _run(script, env)
    assert f"verifier: openssl {wrapper}" in r.stderr and "bundle signature verified" in r.stderr
    assert not any("pkeyutl" in x for x in _lines(bare))


@needs_openssl_route
@needs_ssh_keygen
@pytest.mark.parametrize("value", ["/nonexistent/openssl", "SHIM", "openssl"], ids=["missing", "incapable", "relative"])
def test_at_v6_bad_decoy_openssl_exits_69_without_fallback(tmp_path, value):
    rel = _signed_release(tmp_path)
    capable = _wrap(tmp_path / "good" / "openssl", REAL_OPENSSL, tmp_path / "log")
    bad = _libressl(tmp_path / "bad")
    if value == "SHIM":
        value = str(bad)
    # a capable openssl on PATH, a real ssh-keygen and injected keys: nothing may rescue the install
    r = _run(_variant(tmp_path, rel.install_sh, ssh_fallback=REAL_SSH_KEYGEN or "/x"), _env(tmp_path, capable.parent, DECOY_OPENSSL=value, DECOY_VERSION_URL="file:///nonexistent/v.json"))
    assert r.returncode == 69, r.stderr
    assert "verifier:" not in r.stderr and value in r.stderr


@needs_openssl_route
@needs_ssh_keygen
def test_at_v6b_empty_decoy_openssl_is_unset_and_a_bare_name_is_not_resolved(tmp_path):
    rel = _signed_release(tmp_path)
    capable = _wrap(tmp_path / "good" / "openssl", REAL_OPENSSL, tmp_path / "log")
    script = _variant(tmp_path, rel.install_sh)
    url = {"DECOY_VERSION_URL": f"file://{rel.files[0]}"}
    r = _run(script, _env(tmp_path, capable.parent, DECOY_OPENSSL="", **url))
    assert f"verifier: openssl {capable}" in r.stderr
    r = _run(script, _env(tmp_path, capable.parent, DECOY_OPENSSL="openssl", **url))
    assert r.returncode == 69 and "absolute path" in r.stderr


def test_at_v9_known_answer_files_are_removed_with_the_workdir(tmp_path):
    shims, scratch = tmp_path / "shims", tmp_path / "tmp"
    scratch.mkdir()
    _libressl(shims)
    script = _variant(tmp_path, INSTALL_SH)
    r = _run(script, _env(tmp_path, shims, TMPDIR=str(scratch)))
    assert r.returncode == 69
    assert list(scratch.iterdir()) == []
    _accept_all_openssl(shims / "openssl", tmp_path / "log")  # a failure after selection cleans up too
    r = _run(script, _env(tmp_path, shims, TMPDIR=str(scratch)))
    assert list(scratch.iterdir()) == []


@needs_ssh_keygen
def test_at_v10_uninstall_and_existing_install_refusal_need_no_verifier(tmp_path):
    tools = tmp_path / "tools"
    tools.mkdir()
    for name in ("uname", "tar", "mktemp", "rm", "mkdir", "find", "head", "cut", "tr", "date", "grep", "sed", "cat", "dirname"):
        if shutil.which(name):
            (tools / name).symlink_to(shutil.which(name))
    env = {"PATH": str(tools), "HOME": str(tmp_path), "DECOY_HOME": str(tmp_path / "home"), "DECOY_BIN_DIR": str(tmp_path / "bin")}
    assert shutil.which("openssl", path=str(tools)) is None and shutil.which("ssh-keygen", path=str(tools)) is None
    (tmp_path / "home" / "versions" / "0.1.0").mkdir(parents=True)
    r = _run(INSTALL_SH, env)
    assert r.returncode == 1 and "refusing to overwrite an existing install" in r.stderr
    assert "cannot verify" not in r.stderr and "required tool" not in r.stderr
    r = _run(INSTALL_SH, env, "uninstall")
    assert r.returncode == 0 and not (tmp_path / "home").exists()


def test_at_v11_capability_gate_asks_for_ed25519_not_a_binary_named_openssl(tmp_path):
    shim, accept_all = _libressl(tmp_path / "a"), _accept_all_openssl(tmp_path / "b" / "openssl", tmp_path / "log")
    assert ed25519_openssl([str(shim)]) is None  # LibreSSL 3.3.6 is on PATH and cannot verify
    assert ed25519_openssl([str(accept_all)]) is None  # accepts the known good and the known bad
    assert ed25519_openssl([str(shim), "/nonexistent/openssl"]) is None
    if REAL_OPENSSL:
        assert ed25519_openssl([str(shim), REAL_OPENSSL]) == REAL_OPENSSL


@needs_ssh_keygen
def test_at_v13_the_rewrite_seam_changes_only_the_fallback_lines(tmp_path):
    rel = _signed_release(tmp_path)
    before = rel.install_sh.read_text().splitlines()
    after = _variant(tmp_path, rel.install_sh, fallbacks="/x/openssl").read_text().splitlines()
    assert len(before) == len(after) and sum(a != b for a, b in zip(before, after)) == 2
    assert sum(1 for line in before if line.startswith("OPENSSL_FALLBACKS=")) == 1
    assert subprocess.run([SH, "-n", str(tmp_path / "install_variant.sh")], check=False).returncode == 0


# ----------------------------------------------------------------------- SSHSIG route
@needs_sshsig_route
@needs_ssh_keygen
def test_at_s1_sshsig_route_checks_both_files_with_the_pinned_key(tmp_path):
    rel, shims, log = _signed_release(tmp_path), tmp_path / "shims", tmp_path / "log"
    _libressl(shims)
    wrapper = _wrap(shims / "ssh-keygen", REAL_SSH_KEYGEN, log)
    script = _variant(tmp_path, rel.install_sh)
    r = _run(script, _env(tmp_path, shims, DECOY_VERSION_URL=f"file://{rel.files[0]}"))
    assert f"verifier: sshsig {wrapper}" in r.stderr and "version document signature verified" in r.stderr
    assert r.returncode == 1 and "unexpected schema_version" in r.stderr
    bundle = _local_bundle(rel)
    r = _run(script, _env(tmp_path, shims, DECOY_LOCAL_BUNDLE=str(bundle)))
    assert "bundle signature verified" in r.stderr
    real = [x.split() for x in _lines(log) if "/kat/" not in x]
    assert len(real) == 2  # one `-Y verify` per signed file
    for argv, sidecar in zip(real, (None, f"{bundle}.sshsig")):
        flags = dict(zip(argv[3::2], argv[4::2]))
        assert argv[1:3] == ["-Y", "verify"]
        assert flags["-I"] == "decoy-release@trydecoy.com" and flags["-n"] == NAMESPACE
        assert flags["-f"].endswith("/allowed_signers") and "/kat/" not in flags["-f"]
        # the data file and the sidecar base have different names for the downloaded version document
        assert flags["-s"] == sidecar if sidecar else flags["-s"].endswith("/vdoc.sshsig")


@needs_ssh_keygen
def test_at_s2_ssh_keygen_that_accepts_everything_is_rejected(tmp_path):
    rel, shims, log = _signed_release(tmp_path), tmp_path / "shims", tmp_path / "log"
    _libressl(shims)
    _sh(shims / "ssh-keygen", f'echo "$0 $* stdin=$(cat)" >> {log}\nexit 0\n')
    r = _run(_variant(tmp_path, rel.install_sh), _env(tmp_path, shims, DECOY_VERSION_URL="file:///nonexistent/v.json"))
    assert r.returncode == 69, r.stderr
    calls = _lines(log)
    assert len(calls) == 2 and calls[0].endswith("stdin=r") and calls[1].endswith("stdin=s")


def _fake_bundle(d: Path, version: str, target: str) -> Path:
    """A tarball whose interpreter is a shell script: verify and self-check succeed and
    first_install lays down a launcher. Enough to reach the end of install.sh without Python."""
    root = f"decoy-{version}-{target}"
    py = (
        '#!/bin/sh\ncase "$*" in *first_install*)\n  mkdir -p "$DECOY_HOME/versions" "$DECOY_BIN_DIR" || exit 1\n'
        '  mv "$5" "$DECOY_HOME/versions/$6" || exit 1\n  ln -s "versions/$6" "$DECOY_HOME/current"\n'
        '  printf \'#!/bin/sh\\necho "decoy %s"\\n\' "$6" > "$DECOY_BIN_DIR/decoy"; chmod +x "$DECOY_BIN_DIR/decoy";;\nesac\nexit 0\n'
    )
    info = json.dumps({"schema_version": "cli-bundle-info/v1", "target": target, "version": version}, separators=(",", ":"), sort_keys=True)
    tarball = d / f"{root}.tar.gz"
    with tarfile.open(tarball, "w:gz") as tf:
        for name, data, mode in ((f"{root}/python/bin/python3", py.encode(), 0o755), (f"{root}/BUNDLE_INFO.json", info.encode(), 0o644)):
            ti = tarfile.TarInfo(name)
            ti.size, ti.mode = len(data), mode
            tf.addfile(ti, io.BytesIO(data))
    return tarball


def _sign_both(rel, path: Path) -> None:
    assert run_signer("sign", str(path), key_file=rel.key_file).returncode == 0
    assert run_signer("sshsig", "--in", str(path), "--out", f"{path}.sshsig", key_file=rel.key_file).returncode == 0


@needs_sshsig_route
@needs_ssh_keygen
def test_at_s3_ssh_keygen_never_reads_the_script_from_stdin(tmp_path):
    target = targets.detect_target()
    if target is None:
        pytest.skip("no supported bundle target for this host")
    rel, shims = _signed_release(tmp_path), tmp_path / "shims"
    _libressl(shims)
    bundle = _fake_bundle(tmp_path, "0.1.0", target)
    _sha_sidecar(bundle)
    _sign_both(rel, bundle)
    script = _variant(tmp_path, rel.install_sh, ssh_fallback=REAL_SSH_KEYGEN)
    env = _env(tmp_path, shims, DECOY_LOCAL_BUNDLE=str(bundle))
    with script.open() as stdin:  # `curl | sh`
        r = subprocess.run([SH], env=env, stdin=stdin, capture_output=True, text=True, timeout=120, check=False)
    assert r.returncode == 0, r.stderr
    assert "verifier: sshsig" in r.stderr and "bundle signature verified" in r.stderr and "done. run: decoy --version" in r.stderr
    shutil.rmtree(tmp_path / "home")
    bundle.write_bytes(bundle.read_bytes() + b"x")
    _sha_sidecar(bundle)
    with script.open() as stdin:
        r = subprocess.run([SH], env=env, stdin=stdin, capture_output=True, text=True, timeout=120, check=False)
    assert r.returncode == 1 and INVALID_BUNDLE in r.stderr


@needs_openssl_route
@needs_sshsig_route
@needs_ssh_keygen
def test_at_s4_a_capable_openssl_is_preferred_over_ssh_keygen(tmp_path):
    rel, shims, olog, slog = _signed_release(tmp_path), tmp_path / "shims", tmp_path / "olog", tmp_path / "slog"
    _wrap(shims / "openssl", REAL_OPENSSL, olog)
    _wrap(shims / "ssh-keygen", REAL_SSH_KEYGEN, slog)
    r = _run(_variant(tmp_path, rel.install_sh), _env(tmp_path, shims, DECOY_VERSION_URL=f"file://{rel.files[0]}"))
    assert f"verifier: openssl {shims / 'openssl'}" in r.stderr and _lines(slog) == [] and _lines(olog)


@needs_ssh_keygen
def test_at_s5_one_placeholder_is_a_broken_release_and_two_are_a_dev_build(tmp_path):
    rel, shims = _signed_release(tmp_path), tmp_path / "shims"
    _libressl(shims)
    text = rel.install_sh.read_text()
    env = _env(tmp_path, shims, DECOY_VERSION_URL="file:///nonexistent/v.json")
    no_ssh = tmp_path / "no_ssh.sh"
    no_ssh.write_text(re.sub(r"(?m)^PINNED_SSH_PUBKEY='.*'$", "PINNED_SSH_PUBKEY='__DECOY_RELEASE_SSH_PUBLIC_KEY__'", text))
    r = _run(no_ssh, env)
    assert r.returncode == 1 and "release keys incomplete" in r.stderr
    no_pem = tmp_path / "no_pem.sh"
    no_pem.write_text(re.sub(r"(?s)PINNED_PUBKEY='-----BEGIN.*?END PUBLIC KEY-----'", "PINNED_PUBKEY='-----BEGIN PUBLIC KEY-----\n__DECOY_RELEASE_PUBLIC_KEY__\n-----END PUBLIC KEY-----'", text, count=1))
    assert _run(no_pem, env).returncode == 1
    r = _run(_variant(tmp_path, INSTALL_SH), env)
    assert r.returncode == 69 and re.search(r"tried: .*not pinned", r.stderr)


# ------------------------------------------------------------------ negative matrix
def _sshsig_namespace(data: Path, key: Ed25519PrivateKey, namespace: str) -> None:
    keyfile = data.parent / "other_ns.key"
    keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()))
    keyfile.chmod(0o600)
    with data.open("rb") as stdin, open(f"{data}.sshsig", "wb") as out:
        cmd = [REAL_SSH_KEYGEN, "-Y", "sign", "-f", str(keyfile), "-n", namespace]
        assert subprocess.run(cmd, stdin=stdin, stdout=out, check=False).returncode == 0


def _sshsig_framed_raw_signature(data: Path, key: Ed25519PrivateKey) -> None:
    """A valid raw `.sig`, but over the SSHSIG signed blob instead of the file bytes."""
    def s(b: bytes) -> bytes:
        return len(b).to_bytes(4, "big") + b
    blob = b"SSHSIG" + s(NAMESPACE.encode()) + s(b"") + s(b"sha512") + s(hashlib.sha512(data.read_bytes()).digest())
    Path(f"{data}.sig").write_text(base64.b64encode(key.sign(blob)).decode())


def _case(tmp_path: Path, rel, kind: str, which: str, case: str) -> Path:
    ext, idx = ("sig" if kind == "openssl" else "sshsig"), (0 if which == "vdoc" else 1)
    d = tmp_path / "files"
    d.mkdir()
    data = d / rel.files[idx].name
    data.write_bytes(rel.files[idx].read_bytes())
    sidecar = Path(f"{data}.{ext}")
    shutil.copy(f"{rel.files[idx]}.{ext}", sidecar)
    if case == "missing":
        sidecar.unlink()
    elif case == "other_key":
        stranger = write_key(tmp_path / "other.pem", Ed25519PrivateKey.generate())
        args = ("sign", str(data)) if kind == "openssl" else ("sshsig", "--in", str(data), "--out", str(sidecar))
        assert run_signer(*args, key_file=stranger).returncode == 0
    elif case == "wrong_namespace" and kind == "sshsig":
        _sshsig_namespace(data, rel.key, "other")
    elif case == "wrong_namespace":
        _sshsig_framed_raw_signature(data, rel.key)
    elif case == "other_file":
        shutil.copy(f"{rel.files[1 - idx]}.{ext}", sidecar)
    elif case == "changed_byte":
        data.write_bytes(data.read_bytes()[:-1] + b"X")
    return data


@pytest.fixture(scope="module")
def matrix_release(tmp_path_factory):
    if not (REAL_OPENSSL and REAL_SSH_KEYGEN):
        pytest.skip("the matrix needs both verifiers")
    return _signed_release(tmp_path_factory.mktemp("matrix"))


@needs_openssl_route
@needs_sshsig_route
@needs_ssh_keygen
@pytest.mark.parametrize("case", ["missing", "other_key", "wrong_namespace", "other_file", "changed_byte"])
@pytest.mark.parametrize("which", ["vdoc", "bundle"])
@pytest.mark.parametrize("kind", ["openssl", "sshsig"])
def test_at_x1_negative_matrix(tmp_path, matrix_release, kind, which, case):
    script, env, _ = _force(kind, tmp_path, matrix_release)
    data = _case(tmp_path, matrix_release, kind, which, case)
    if which == "bundle":
        env["DECOY_LOCAL_BUNDLE"] = str(_sha_sidecar(data))
    else:
        env["DECOY_VERSION_URL"] = f"file://{data}"
    r = _run(script, env)
    assert f"verifier: {kind}" in r.stderr
    assert r.returncode == 1, r.stderr
    if case == "missing":
        assert ("could not fetch version-document signature" if which == "vdoc" else "needs ") in r.stderr
    else:
        assert (INVALID_VDOC if which == "vdoc" else INVALID_BUNDLE) in r.stderr
    assert not (tmp_path / "home" / "versions").exists()


# ----------------------------------------------------------------- static choke point
def _code(text: str) -> list[str]:
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


def _bodies(text: str) -> dict[str, str]:
    return {m[1]: m[2] for m in re.finditer(r"(?ms)^(\w+)\(\) \{\n(.*?)^\}", text)}


def test_at_x2_only_verify_file_checks_a_signature():
    text = INSTALL_SH.read_text()
    bodies = _bodies(text)
    outside = [b for name, b in bodies.items() if name not in ("verify_sig", "verify_sshsig")]
    assert all("pkeyutl" not in "\n".join(_code(b)) and " -Y " not in "\n".join(_code(b)) for b in outside)
    top = "\n".join(_code(re.sub(r"(?ms)^\w+\(\) \{\n.*?^\}", "", text)))
    assert "pkeyutl" not in top and " -Y " not in top
    for low, allowed in (("verify_sig", {"verify_file", "kat_openssl"}), ("verify_sshsig", {"verify_file", "kat_sshsig"})):
        users = {n for n, b in bodies.items() if re.search(rf"(?m)^\s*(.*[;&|]\s*)?{low} ", "\n".join(_code(b))) and n != low}
        assert users == allowed, (low, users)
        assert not re.search(rf"(?m)^[^#\s]*{low} ", top)
    assert len(re.findall(rf'(?m)^\s*verify_file "\$VDOC" "[^"]+" \|\| die "{re.escape(INVALID_VDOC)}"$', top)) == 1
    assert len(re.findall(rf'(?m)^verify_file "\$TARBALL" "[^"]+" \|\| die "{re.escape(INVALID_BUNDLE)}"$', top)) == 1


# --------------------------------------------------------------- stock macOS guest
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.mark.skipif(os.environ.get("DECOY_STOCK_MAC_GUEST") != "1", reason="AT-M1 runs only on the stock macOS guest (DECOY_STOCK_MAC_GUEST=1)")
def test_at_m1_stock_mac_installs_through_the_builtin_ssh_keygen(tmp_path):
    """The unmodified injected install.sh, PATH of a stock Mac, local http server. The
    preconditions are asserted (a failure is a precondition error, never a pass or a skip)."""
    target = targets.detect_target()
    assert target, "precondition: unsupported host target"
    assert ed25519_openssl(["/usr/bin/openssl"]) is None, "precondition: /usr/bin/openssl can verify Ed25519"
    assert not _openssl_fallbacks(), "precondition: a Homebrew or MacPorts openssl exists"
    assert usable_ssh_keygen(["/usr/bin/ssh-keygen"]), "precondition: /usr/bin/ssh-keygen fails the SSHSIG known answer"

    rel, serve = _signed_release(tmp_path), tmp_path / "serve"
    serve.mkdir()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: _Quiet(*a, directory=str(serve), **k))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        def publish(version: str) -> Path:
            bundle = _fake_bundle(serve, version, target)
            _sign_both(rel, bundle)
            doc = vd.build_document(serial=1, latest=version, min_supported=version, artifacts={target: {
                "url": f"{base}/{bundle.name}", "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(), "sig": f"{base}/{bundle.name}.sig"}})
            vpath = serve / "version.json"
            vpath.write_bytes(vd.canonical_document_bytes(doc))
            _sign_both(rel, vpath)
            return bundle

        def run(name: str):
            env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(tmp_path), "DECOY_HOME": str(tmp_path / name),
                   "DECOY_BIN_DIR": str(tmp_path / name / "bin"), "DECOY_VERSION_URL": f"{base}/version.json"}
            return subprocess.run(["/bin/sh", str(rel.install_sh)], env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=180, check=False), env

        bundle = publish("0.1.0")
        r, env = run("good")
        assert r.returncode == 0, r.stderr
        assert "verifier: sshsig /usr/bin/ssh-keygen" in r.stderr
        assert "version document signature verified" in r.stderr and "bundle signature verified" in r.stderr
        out = subprocess.run([f"{env['DECOY_BIN_DIR']}/decoy", "--version"], capture_output=True, text=True, check=False)
        assert "0.1.0" in out.stdout
        shutil.copy(f"{serve / 'version.json'}.sshsig", f"{bundle}.sshsig")  # wrong file's sidecar
        r, _ = run("wrong_sidecar")
        assert r.returncode == 1 and INVALID_BUNDLE in r.stderr
        bundle = publish("0.1.0")
        (serve / "version.json").write_bytes((serve / "version.json").read_bytes() + b" ")
        r, _ = run("changed_doc")
        assert r.returncode == 1 and INVALID_VDOC in r.stderr
    finally:
        server.shutdown()
