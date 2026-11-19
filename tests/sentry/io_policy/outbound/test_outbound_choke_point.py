"""AT-S6d (G-ONE-OUTBOUND): no first-party function outside an exact allowlist owns a network call.

Freeze batch plan 10.7. An AST pass over `src/` resolves import aliases and module-level string
constants through the shared scanner `tests/sentry/io_policy/_calls.py`. A reference that
resolves under `urllib.request`, `http.client`, `requests`, `urllib3`, `httpx`, `socket` or
`smtplib` is a network call site, and so is `importlib.import_module` or `__import__` of one of
those names. Allowlist entries are exact `(path, enclosing function)` pairs.

Named limit: a dynamic import with a computed, non-constant name is not seen (V2-LOG).
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.sentry._ratchet import load_allowlist
from tests.sentry.io_policy._calls import sites

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
BANNED = (
    "urllib.request",
    "ftplib",
    "xmlrpc.client",
    "asyncio.open_connection",
    "http.client",
    "requests",
    "urllib3",
    "httpx",
    "socket",
    "smtplib",
)
# The exact (path, function) owners are the baseline `outbound-network-owners`; it may shrink
# and never grow.
OWNERS = frozenset(
    (key.split("::")[0], key.split("::")[1]) for key in load_allowlist("outbound-network-owners")
)


# Private names of `decoy._outbound`; only that module may name them.
OUTBOUND_PRIVATE = frozenset(
    {"_open", "_scheme_of", "redirect_handler", "RefuseRedirects", "_PurposeRedirects"}
)


def _is_banned(name: str | None) -> bool:
    """A banned module at any segment, so `decoy._outbound.urllib.request.urlopen` is caught."""
    if name is None:
        return False
    parts = name.split(".")
    tails = (".".join(parts[i:]) for i in range(len(parts)))
    return any(t == b or t.startswith(b + ".") for t in tails for b in BANNED)


def _is_private_outbound(name: str | None) -> bool:
    prefix = "decoy._outbound."
    return (
        bool(name)
        and name.startswith(prefix)
        and name[len(prefix) :].split(".")[0] in OUTBOUND_PRIVATE
    )  # type: ignore[union-attr]


def _constants(tree: ast.Module) -> dict[str, str]:
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                found |= {t.id: node.value.value for t in node.targets if isinstance(t, ast.Name)}
    return found


def network_sites(source: str, rel: str = "src/decoy/x.py") -> set[str]:
    """The enclosing scope of every network reference in `source` (a file at `rel`)."""
    tree = ast.parse(source)
    consts = _constants(tree)
    hits: set[str] = set()
    for site in sites(tree):
        named = isinstance(site.node, (ast.Name, ast.Attribute))
        if named and _is_banned(site.name):
            hits.add(site.scope)
        if named and rel != "src/decoy/_outbound.py" and _is_private_outbound(site.name):
            hits.add(site.scope)
        if not isinstance(site.node, ast.Call) or not site.node.args:
            continue
        func = site.node.func
        dynamic = site.name == "importlib.import_module" or (
            isinstance(func, ast.Name) and func.id == "__import__"
        )
        arg = site.node.args[0]
        if isinstance(arg, ast.Name):
            text = consts.get(arg.id)
        else:
            text = arg.value if isinstance(arg, ast.Constant) else None
        if dynamic and isinstance(text, str) and _is_banned(text):
            hits.add(site.scope)
    return hits


def scan() -> tuple[set[tuple[str, str]], int]:
    found: set[tuple[str, str]] = set()
    files = sorted(SRC.rglob("*.py"))
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        found |= {(rel, scope) for scope in network_sites(path.read_text(encoding="utf-8"), rel)}
    return found, len(files)


def test_the_walk_sees_the_known_owners() -> None:
    found, count = scan()
    assert count > 100
    assert ("src/decoy/notify.py", "send_email") in found
    assert ("src/decoy/_outbound.py", "open_url") in found


def test_only_the_allowlist_owns_a_network_call() -> None:
    found, _ = scan()
    assert found - OWNERS == set()
    assert OWNERS - found == set(), "a stale allowlist entry"


def test_the_update_check_is_a_caller_not_an_owner() -> None:
    text = (SRC / "decoy" / "_update_check.py").read_text(encoding="utf-8")
    assert "HTTPRedirectHandler" not in text and 'purpose="update_check"' in text


def _body(path: str, func: str) -> str:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func:
            return ast.unparse(node)
    raise AssertionError(f"{path}::{func} is missing")


def test_the_allowlisted_owners_apply_their_rule() -> None:
    assert "_scheme_of" in _body("src/decoy/_outbound.py", "check_scheme")
    assert "check_scheme" in _body("src/decoy/_outbound.py", "open_url")
    assert "otel_endpoint_problem" in _body("src/decoy/telemetry.py", "validate_endpoint")
    assert "validate_endpoint" in _body("src/decoy/telemetry.py", "configure")
    assert "purpose='notify_webhook'" in _body("src/decoy/notify.py", "send_webhook")
    assert "purpose='notify_slack'" in _body("src/decoy/notify.py", "send_slack")
    assert "check_scheme" in _body("src/decoy/notify.py", "parse_notify_spec")


def test_each_import_spelling_is_caught() -> None:
    planted = [
        "import ftplib\nftplib.FTP('h')",
        "import xmlrpc.client\nxmlrpc.client.ServerProxy('h')",
        "import asyncio\nasyncio.open_connection('h', 1)",
        "from asyncio import open_connection as oc\noc('h', 1)",
        # Dennis r1 M1: the two survivors, reaching urllib through `_outbound` itself.
        "from decoy import _outbound\n_outbound.urllib.request.urlopen('u')",
        "from decoy import _outbound\n_outbound._open(_outbound.urllib.request.build_opener(),"
        " _outbound.urllib.request.Request('u'), None)",
        "from decoy import _outbound\n_outbound._scheme_of('u')",
        "from decoy._outbound import RefuseRedirects\nRefuseRedirects()",
        "import urllib\nurllib.request.urlopen('x')",
        "import urllib.request\nurllib.request.urlopen('x')",
        "import urllib.request as r\nr.urlopen('x')",
        "from urllib import request as r\nr.urlopen('x')",
        "from urllib.request import urlopen as u\nu('x')",
        "import http.client\nhttp.client.HTTPSConnection('h')",
        "from http import client\nclient.HTTPConnection('h')",
        "import requests\nrequests.get('x')",
        "import urllib3\nurllib3.PoolManager()",
        "import httpx\nhttpx.get('x')",
        "import socket\nsocket.create_connection(('h', 1))",
        "import smtplib\nsmtplib.SMTP('h')",
        "import importlib\nimportlib.import_module('socket')",
        "import importlib\nMOD = 'urllib.request'\nimportlib.import_module(MOD)",
        "from importlib import import_module as im\nim('smtplib')",
        "__import__('http.client')",
        "def f():\n    import urllib.request as r\n    return r.urlopen('x')",
    ]
    for source in planted:
        assert network_sites(source), source


def test_the_outbound_public_surface_is_not_flagged() -> None:
    source = (
        "from decoy import _outbound\n"
        "_outbound.open_url('u', 'notify_slack')\n_outbound.check_scheme('u', 'notify_slack')\n"
        "_outbound.allowed_schemes('notify_slack')\n_outbound.OutboundRefused"
    )
    assert network_sites(source) == set()
    assert (
        network_sites("from decoy import _outbound\n_outbound._open", "src/decoy/_outbound.py")
        == set()
    )


def _scopes_naming(name: str) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        for site in sites(ast.parse(path.read_text(encoding="utf-8"))):
            node = site.node
            ident = node.id if isinstance(node, ast.Name) else getattr(node, "attr", None)
            if ident == name:
                found.setdefault(rel, set()).add(site.scope)
    return found


def test_the_span_exporter_is_built_only_by_configure() -> None:
    telemetry = "src/decoy/telemetry.py"
    exporter = _scopes_naming("_DecoySpanExporter")
    assert set(exporter) == {telemetry}
    assert {s for s in exporter[telemetry] if not s.startswith("_DecoySpanExporter")} == {
        "build_provider"
    }
    provider = _scopes_naming("build_provider")
    assert set(provider) == {telemetry}
    assert provider[telemetry] == {"configure"}


def test_non_network_spellings_are_not_flagged() -> None:
    clean = [
        "import urllib.parse\nurllib.parse.urlsplit('x')",
        "from urllib.parse import quote\nquote('x')",
        "import urllib.error\nurllib.error.URLError",
        "import importlib\nimportlib.import_module('json')",
    ]
    for source in clean:
        assert network_sites(source) == set(), source
