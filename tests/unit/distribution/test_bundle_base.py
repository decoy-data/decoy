"""REL-WEB RW-C2a (plan section 5.2; AT-C6, AT-C10): the pinned-bundle location and the one
version-URL resolver. A loopback server records the request line, so the evidence is what
reached a socket."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from typer.testing import CliRunner

from decoy import _update_check
from decoy.__main__ import app
from decoy.cli import upgrade as upg
from decoy.distribution import installer, targets
from decoy.distribution import version_document as vd

REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALL_SH = REPO_ROOT / "packaging_tools" / "install" / "install.sh"
PINNED = "1.0.1"
LATEST = "1.0.2"


class _Server:
    """Serves one signed document at /doc/version.json and 404s everything else, recording
    every request line."""

    def __init__(self, files: dict[str, bytes]):
        self.files, self.paths = files, []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                outer.paths.append(self.path)
                body = outer.files.get(self.path)
                self.send_response(200 if body is not None else 404)
                self.send_header("Content-Length", str(len(body or b"")))
                self.end_headers()
                self.wfile.write(body or b"")

            def log_message(self, *args: object) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def key_pair():
    key = Ed25519PrivateKey.generate()
    pub = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return key, pub


@pytest.fixture
def served(request, key_pair):
    key, _ = key_pair
    target = targets.detect_target() or "linux-x86_64"
    doc = vd.canonical_document_bytes(
        vd.build_document(
            latest=LATEST,
            min_supported="1.0.0",
            serial=1,
            artifacts={
                target: {
                    "url": "http://127.0.0.1:9/x.tar.gz",
                    "sha256": "0" * 64,
                    "sig": "http://127.0.0.1:9/x.sig",
                }
            },
        )
    )
    sig = base64.b64encode(key.sign(doc)).decode().encode()
    server = _Server({"/doc/version.json": doc, "/doc/version.json.sig": sig})
    request.addfinalizer(server.close)
    server.target = target
    return server


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("DECOY_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DECOY_BIN_DIR", str(tmp_path / "bin"))
    for name in ("DECOY_VERSION_URL", "DECOY_BUNDLE_BASE", "CI"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("no_proxy", "*")


def test_at_c6_upgrade_pin_requests_the_release_asset_path(monkeypatch, tmp_path, key_pair, served):
    _, pub = key_pair
    monkeypatch.setattr(upg, "_managed_home", lambda: tmp_path / "home")
    monkeypatch.setattr(upg.release_key, "pinned_public_pem", lambda: pub)
    bundles = _Server({})
    monkeypatch.setenv("DECOY_BUNDLE_BASE", bundles.base)
    CliRunner().invoke(
        app,
        [
            "--no-update-check",
            "upgrade",
            "--version",
            PINNED,
            "--url",
            served.base + "/doc/version.json",
        ],
    )
    bundles.close()
    # The Python installer reads the .sha256 sidecar first, then the bundle itself.
    assert f"/v{PINNED}/decoy-{PINNED}-{served.target}.tar.gz" in bundles.paths
    assert not [p for p in served.paths if p.startswith("/v")], "bundle left the bundle base"


def test_default_bundle_base_is_the_github_release_download_root():
    assert installer.DEFAULT_BUNDLE_BASE == "https://github.com/louiskeep/decoy/releases/download"
    assert installer.resolve_bundle_base() == installer.DEFAULT_BUNDLE_BASE


def test_bundle_base_variable_and_explicit_argument(monkeypatch):
    monkeypatch.setenv("DECOY_BUNDLE_BASE", "http://h/b")
    assert installer.resolve_bundle_base() == "http://h/b"
    assert installer.resolve_bundle_base("http://x/y") == "http://x/y"


@pytest.mark.skipif(
    not (shutil.which("sh") and shutil.which("openssl") and shutil.which("curl")),
    reason="needs sh, openssl, curl",
)
def test_at_c6_install_sh_pin_requests_the_same_path(tmp_path, key_pair, served):
    _, pub = key_pair
    pub_pem = tmp_path / "pub.pem"
    pub_pem.write_text(pub)
    bundles = _Server({})
    env = dict(
        os.environ,
        DECOY_HOME=str(tmp_path / "sh_home"),
        DECOY_BIN_DIR=str(tmp_path / "sh_bin"),
        DECOY_RELEASE_PUBKEY_FILE=str(pub_pem),
        DECOY_VERSION_URL=served.base + "/doc/version.json",
        DECOY_BUNDLE_BASE=bundles.base,
    )
    subprocess.run(
        ["sh", str(INSTALL_SH), "--version", PINNED], env=env, capture_output=True, text=True
    )
    bundles.close()
    assert bundles.paths[0] == f"/v{PINNED}/decoy-{PINNED}-{served.target}.tar.gz"


def test_at_c10_upgrade_check_honors_the_version_url_variable(
    monkeypatch, tmp_path, key_pair, served
):
    _, pub = key_pair
    monkeypatch.setattr(upg, "_managed_home", lambda: tmp_path / "home")
    monkeypatch.setattr(upg.release_key, "pinned_public_pem", lambda: pub)
    monkeypatch.setenv("DECOY_VERSION_URL", served.base + "/doc/version.json")
    result = CliRunner().invoke(app, ["--no-update-check", "upgrade", "--check"])
    assert "/doc/version.json" in served.paths, result.output


def test_at_c10_url_option_beats_the_variable(monkeypatch, tmp_path, key_pair, served):
    _, pub = key_pair
    other = _Server({})
    monkeypatch.setattr(upg, "_managed_home", lambda: tmp_path / "home")
    monkeypatch.setattr(upg.release_key, "pinned_public_pem", lambda: pub)
    monkeypatch.setenv("DECOY_VERSION_URL", other.base + "/doc/version.json")
    CliRunner().invoke(
        app, ["--no-update-check", "upgrade", "--check", "--url", served.base + "/doc/version.json"]
    )
    other.close()
    assert other.paths == [] and "/doc/version.json" in served.paths


def test_default_url_is_the_owner_chosen_host_and_one_resolver_serves_both_callers(monkeypatch):
    assert vd.DEFAULT_URL == "https://trydecoy.com/cli/version.json"
    assert vd.resolve_version_url() == vd.DEFAULT_URL
    monkeypatch.setenv("DECOY_VERSION_URL", "http://h/v.json")
    assert vd.resolve_version_url() == "http://h/v.json"
    assert vd.resolve_version_url("http://o/v.json") == "http://o/v.json"
    assert not hasattr(_update_check, "_DEFAULT_VERSION_URL") and not hasattr(
        upg, "_DEFAULT_VERSION_URL"
    )


SCRIPTS = {
    name: (REPO_ROOT / "packaging_tools" / "install" / name).read_text(encoding="utf-8")
    for name in ("install.sh", "install.ps1")
}


def test_installer_scripts_carry_the_same_defaults_as_python():
    for name, text in SCRIPTS.items():
        assert installer.DEFAULT_BUNDLE_BASE in text, name
        assert vd.DEFAULT_URL in text, name
        assert "decoy.dev" not in text, name


def test_install_ps1_pinned_path_uses_the_v_prefixed_release_layout():
    assert "$baseUrl/v$ver/decoy-$ver-$target.tar.gz" in SCRIPTS["install.ps1"]
    assert "$BundleBase.TrimEnd('/')" in SCRIPTS["install.ps1"]
    assert (
        "DECOY_BUNDLE_BASE" in SCRIPTS["install.ps1"]
        and "DECOY_BUNDLE_BASE" in SCRIPTS["install.sh"]
    )
    assert "/v$VERSION/decoy-$VERSION-$TARGET.tar.gz" in SCRIPTS["install.sh"]
