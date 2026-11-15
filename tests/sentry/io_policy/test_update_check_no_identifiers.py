"""G-UPDATE-NO-ID: the startup update check reads no machine or user identifier.

REL-WEB plan section 5.2, P4 (AT-C8) and AT-C9. Read off the syntax tree of
`src/decoy/_update_check.py` and of every `decoy.distribution` module it imports:

- no import of `uuid` or `getpass`;
- no use of `getnode`, `gethostname`, `getlogin`, `getuser` or `uname`, as an attribute
  (`socket.gethostname()`) or a from-import (`from socket import gethostname`);
- no `platform.node`, in either spelling. `platform.machine` stays legal: `targets.py` needs it
  to pick a bundle, and the check never imports `targets`.

AT-C9: the module docstring no longer promises an opt-out "config setting" that does not exist.

Named limit: a name built at run time (`getattr(socket, "get" + "hostname")`) is not seen.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
CHECK = SRC / "decoy" / "_update_check.py"

BANNED_MODULES = frozenset({"uuid", "getpass"})
BANNED_NAMES = frozenset({"getnode", "gethostname", "getlogin", "getuser", "uname"})


def identifier_uses(source: str) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            hits += [a.name for a in node.names if a.name.split(".")[0] in BANNED_MODULES]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] in BANNED_MODULES:
                hits.append(module)
            for alias in node.names:
                if alias.name in BANNED_NAMES or (module == "platform" and alias.name == "node"):
                    hits.append(f"{module}.{alias.name}")
        elif isinstance(node, ast.Attribute):
            on_platform = isinstance(node.value, ast.Name) and node.value.id == "platform"
            if node.attr in BANNED_NAMES or (on_platform and node.attr == "node"):
                hits.append(node.attr)
    return hits


def distribution_imports(source: str) -> set[str]:
    """The `decoy.distribution` modules a source imports, as file stems."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module == "decoy.distribution":
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("decoy.distribution."):
            found.add(node.module.rsplit(".", 1)[1])
        elif isinstance(node, ast.Import):
            found |= {
                a.name.rsplit(".", 1)[1] for a in node.names if a.name.startswith("decoy.distribution.")
            }
    return found


def scanned_files() -> list[Path]:
    text = CHECK.read_text(encoding="utf-8")
    stems = distribution_imports(text)
    # The check imports these two today; a derivation that finds fewer is broken.
    assert {"version_document", "layout"} <= stems, sorted(stems)
    return [CHECK, *(SRC / "decoy" / "distribution" / f"{stem}.py" for stem in sorted(stems))]


def test_the_update_check_reads_no_identifier() -> None:
    for path in scanned_files():
        assert identifier_uses(path.read_text(encoding="utf-8")) == [], path


def test_the_docstring_promises_no_config_setting() -> None:
    doc = ast.get_docstring(ast.parse(CHECK.read_text(encoding="utf-8"))) or ""
    assert "User-Agent: decoy-update-check" in doc
    assert "config setting" not in doc


def test_each_identifier_spelling_is_caught() -> None:
    planted = [
        "import uuid",
        "import getpass as g",
        "from uuid import uuid4",
        "from socket import gethostname",
        "from platform import node",
        "import platform\nplatform.node()",
        "import socket\nsocket.gethostname()",
        "import os\nos.getlogin()",
        "import os\nos.uname()",
        "import getpass\ngetpass.getuser()",
    ]
    for source in planted:
        assert identifier_uses(source), source
    assert identifier_uses("import platform\nplatform.machine()") == []


def test_the_import_derivation_reads_each_spelling() -> None:
    source = (
        "from decoy.distribution import layout\n"
        "from decoy.distribution import version_document as vd\n"
        "import decoy.distribution.signing\n"
        "from decoy.distribution.targets import current\n"
    )
    assert distribution_imports(source) == {"layout", "version_document", "signing", "targets"}
