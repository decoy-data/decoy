"""G-ONE-CONFIG-LOAD: a user's pipeline config is read through `decoy._config_file` only.

Eleven readers tripped over the same file in ten ways: a different except list each, and a
non-UTF-8 file raised a codec error to the crash guard in six of them. `load_config_mapping` is
the one path: bytes once, strict UTF-8, one code per failure. Every other YAML load under
`src/decoy` is a different kind of input and is named in `ALLOWLIST` with its kind, so a new
`yaml.safe_load(path.read_text())` for a user config is a new key and fails here.

`ALLOWLIST` is read from the shrink-only baseline `baselines/config-load-allow.json`; the ratchet
rejects an added key. Each entry must match a live site (rule 10: an allowed helper is still
checked). The scan is `_yaml_load_sites.py`.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from tests.sentry._ratchet import load_allowlist
from tests.sentry.io_policy import _yaml_load_sites as sites

KINDS = frozenset(
    {
        "CI manifest",
        "source index",
        "policy file",
        "fixed-width layout file",
        "CLI-written text",
        "user-editable project marker",
    }
)


class Reader(NamedTuple):
    file: str
    function: str
    n: int
    kind: str
    reason: str


def _reader(key: str, entry: dict[str, Any]) -> Reader:
    file, function, n = key.split("::")
    kind, reason = entry["reason"].split(": ", 1)
    return Reader(file, function, int(n), kind, reason)


ALLOWLIST: tuple[Reader, ...] = tuple(
    _reader(key, e) for key, e in load_allowlist("config-load-allow").items()
)


def _allowed() -> set[str]:
    return {f"{r.file}::{r.function}::{r.n}" for r in ALLOWLIST}


def test_every_entry_names_a_known_kind() -> None:
    assert {r.kind for r in ALLOWLIST} <= KINDS


def test_the_allowlist_equals_the_source_inventory() -> None:
    live = sites.inventory()
    assert live - _allowed() == set(), "a YAML load outside the loader (use load_config_mapping)"
    assert _allowed() - live == set(), "an allowlist entry no longer matches a real site"


def test_no_function_reads_bytes_and_decodes_them_itself() -> None:
    """A user config's read-and-decode step belongs to `read_config_text`. No function is exempt."""
    assert sites.bypass_inventory() == set(), (
        "a hand-rolled read_bytes + decode (use read_config_text)"
    )


def test_a_file_with_an_allowlisted_yaml_reader_still_has_a_hand_rolled_read_reported() -> None:
    seeded = (
        "import yaml\n"
        "def _parse(t):\n    return yaml.safe_load(t)\n"
        "def load(p):\n    return p.read_bytes().decode()\n"
    )
    assert sites.sites_in_source(seeded, "ci/manifest.py") == {"ci/manifest.py::_parse::1"}
    assert sites.bypass_sites_in_source(seeded, "ci/manifest.py") == {"ci/manifest.py::load"}


def test_the_loader_exists_and_loads_yaml() -> None:
    source = (sites.SRC / sites.OWNER).read_text(encoding="utf-8")
    assert sites.sites_in_source(source, sites.OWNER), "the owner no longer loads YAML"


# --- seeded spellings: each turns the scan red --------------------------------------------

_SEEDS = {
    "safe_load": "import yaml\ndef f(p):\n    return yaml.safe_load(p.read_text())\n",
    "alias": "import yaml as _yaml\ndef f(p):\n    return _yaml.safe_load(p.read_text())\n",
    "from_import": "from yaml import safe_load as sl\ndef f(p):\n    return sl(p.read_text())\n",
    "load": "import yaml\ndef f(p):\n    return yaml.load(p.read_text(), Loader=yaml.SafeLoader)\n",
    "full_load": "import yaml\ndef f(p):\n    return yaml.full_load(p.read_text())\n",
    "compose": "import yaml\ndef f(t):\n    return yaml.compose(t, Loader=yaml.SafeLoader)\n",
    "load_all": "import yaml\ndef f(t):\n    return list(yaml.safe_load_all(t))\n",
    "ruamel": "from ruamel.yaml import YAML\ndef f(p):\n    return YAML().load(p.read_text())\n",
    "method": "import yaml\nclass C:\n    def m(self, t):\n        return yaml.safe_load(t)\n",
}


def test_each_seeded_spelling_is_seen() -> None:
    for name, source in _SEEDS.items():
        found = sites.sites_in_source(source, "x.py")
        assert len(found) == 1, name


def test_a_second_load_in_one_function_is_a_new_key() -> None:
    source = "import yaml\ndef f(a, b):\n    return yaml.safe_load(a), yaml.safe_load(b)\n"
    assert sites.sites_in_source(source, "a.py") == {"a.py::f::1", "a.py::f::2"}


def test_dumping_and_event_reads_are_not_sites() -> None:
    source = (
        "import yaml\n"
        "def f(t, d):\n"
        "    yaml.safe_dump(d)\n"
        "    list(yaml.parse(t))\n"
        "    return yaml.dump(d)\n"
    )
    assert sites.sites_in_source(source, "a.py") == set()


def test_a_hand_rolled_read_and_decode_is_seen() -> None:
    seeded = "def adapter(path):\n    data = path.read_bytes()\n    return data.decode('utf-8')\n"
    assert sites.bypass_sites_in_source(seeded, "x.py") == {"x.py::adapter"}
    method = "class C:\n    def m(self, p):\n        return p.read_bytes().decode()\n"
    assert sites.bypass_sites_in_source(method, "x.py") == {"x.py::C.m"}


def test_reading_bytes_or_decoding_alone_is_not_a_bypass() -> None:
    assert sites.bypass_sites_in_source("def f(p):\n    return p.read_bytes()\n", "x.py") == set()
    assert sites.bypass_sites_in_source("def f(b):\n    return b.decode()\n", "x.py") == set()
