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
from tests.sentry.io_policy import _lang_imports as lang_imports
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


# --- the language is reached only through the loader (rule 1, tests 2 and 3) --------------------


def test_no_one_outside_the_loader_takes_a_private_name_of_it() -> None:
    """`_parse_yaml_mapping(read_config_text(p))` is the bypass this closes: the YAML parser is
    private, so a caller cannot read a pipeline file without the loader's checks."""
    private = [v for v in lang_imports.violations() if "private loader name" in v]
    assert private == []


def test_the_language_is_imported_only_by_the_exact_allowed_pairs() -> None:
    assert lang_imports.violations() == []


_PAIR_SEEDS = [
    ("decoy._config_file", "from decoy.lang import lower_text\n", "lower_text"),
    ("decoy._config_file", "def f():\n    from decoy.lang import LangError\n", "LangError"),
    ("decoy.cli.lang._fmt", "from decoy.lang import format_text, render\n", "format_text"),
    ("decoy.cli.lang", "from decoy.lang import convert_config, emit_yaml\n", "emit_yaml"),
    (
        "decoy.ci.rule_codes",
        "def validation_codes():\n    from decoy.lang import CODES\n",
        "CODES",
    ),
]


def _bad(importer: str, source: str) -> list[tuple[str, str, str]]:
    return [
        use
        for use in sorted(lang_imports.uses_in_source(source))
        if not lang_imports.is_allowed(importer, *use)
    ]


def test_each_allowed_pair_passes_its_own_seeded_check() -> None:
    for importer, source, name in _PAIR_SEEDS:
        assert {u[1] for u in lang_imports.uses_in_source(source)} >= {name}, source
        assert _bad(importer, source) == [], (importer, source)


def test_moving_the_codes_import_to_module_scope_is_red() -> None:
    assert _bad("decoy.ci.rule_codes", "from decoy.lang import CODES\n")


def test_one_more_name_for_an_allowed_importer_is_red() -> None:
    assert _bad("decoy._config_file", "from decoy.lang import lower_text, compile_text\n")


_SPELLINGS = {
    "alias": "import decoy.lang as L\nL.lower_text(t)\n",
    "from_import": "from decoy.lang import compile_text\n",
    "attribute": "import decoy\ndecoy.lang.compile_text(t)\n",
    "private_from": "from decoy.lang._lower import lower\n",
    "package_binding": "from decoy import lang\n",
    "star": "from decoy.lang import *\n",
    "dunder_import": '__import__("decoy.lang")\n',
    "import_module": 'import importlib\nimportlib.import_module("decoy.lang")\n',
    "private_import_module": 'import importlib\nimportlib.import_module("decoy.lang._lower")\n',
    "private_alias": "import decoy.lang._lower as x\n",
}


def test_each_seeded_spelling_is_red_for_a_cli_module() -> None:
    for name, source in _SPELLINGS.items():
        assert _bad("decoy.cli.validate", source), name


def test_a_private_loader_name_is_seen_in_each_spelling() -> None:
    bypass = "from decoy._config_file import _parse_yaml_mapping, read_config_text\n"
    assert lang_imports.private_loader_imports(bypass) == {"_parse_yaml_mapping"}
    assert lang_imports.private_loader_imports("from decoy._config_file import *\n") == {"*"}
    assert lang_imports.private_loader_imports(
        "from decoy import _config_file\n_config_file._parse_yaml_mapping(t)\n"
    ) == {"_parse_yaml_mapping"}
    assert (
        lang_imports.private_loader_imports("from decoy._config_file import load_pipeline\n")
        == set()
    )


# --- the one pipeline suffix table (F10) --------------------------------------------------------

_CLI = sites.SRC / "cli"


def yml_literals(source: str) -> list[int]:
    """Lines of a string literal that is exactly `.yml`. The suffix table is
    `decoy._config_file.PIPELINE_SUFFIXES`; no command module keeps a second one."""
    import ast

    return [
        n.lineno
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Constant) and n.value == ".yml"
    ]


def test_no_cli_module_spells_a_pipeline_suffix() -> None:
    found = {
        p.relative_to(sites.SRC).as_posix(): yml_literals(p.read_text(encoding="utf-8"))
        for p in sorted(_CLI.rglob("*.py"))
    }
    assert {k: v for k, v in found.items() if v} == {}


def test_a_seeded_suffix_literal_is_seen() -> None:
    assert yml_literals('SUFFIXES = (".yaml", ".yml")\n') == [1]
    assert yml_literals('name.endswith((".yml", ".yaml"))\n') == [1]
    assert yml_literals('"native-companion.yml CI"\n') == []
