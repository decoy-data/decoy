"""A throwaway TLS identity for loopback test servers.

The outbound purposes refuse plain `http:` for the update check and the upgrade, so a test
server that stands in for them speaks https. `secure` wraps the server socket with a fresh
self-signed certificate for 127.0.0.1 and points `SSL_CERT_FILE` at it, which the default
client context trusts.
"""

from __future__ import annotations

import datetime
import http.server
import ipaddress
import ssl
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def _identity(pem: Path) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    pem.write_bytes(
        cert.public_bytes(serialization.Encoding.PEM)
        + key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )


def secure(httpd: http.server.HTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Wrap `httpd` in TLS. Every server of one test shares one identity, so one trust file."""
    pem = tmp_path / "loopback.pem"
    if not pem.exists():
        _identity(pem)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(pem)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    monkeypatch.setenv("SSL_CERT_FILE", str(pem))
