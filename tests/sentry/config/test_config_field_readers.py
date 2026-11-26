"""G-CONFIG-READER: every pipeline config field the engine accepts has a recorded reader.

A pipeline config accepts a field that no run reads, and the run reports success: that is how
`pre_scan` was accepted and ignored. This sentry walks the pinned engine's live
`PipelineConfig` (every top-level field and the fields of every top-level field whose annotation
is a pydantic model, through `Optional` and unions) and demands exactly one manifest entry per
path in `tests/sentry/baselines/config-field-readers.json`. The list of paths comes from the
live model, never from the manifest.

It does not walk `tables`, `columns`, `sources`, `targets` or per-column strategy fields. Those
are list or dict items read by the compiler and covered by the engine's own plan tests; walking
them would turn the manifest into a copy of the schema.

Entry kinds: `engine` (a public engine symbol whose source names the key), `cli` (a function on
the CLI run path, with exact call chains), `other_command` (read only by another command) and
`unread` (accepted and read by no run; a shrink-only ratchet through the registered baseline).

Named limits: a read through `getattr` with a computed name, `model_dump()` walked generically,
and a symbol that mentions the key without reading it. The sentry proves a reader is wired to the
key's name; the engine plan tests prove what it does with it. Ported idea: dbt's unused
configuration warning, applied at build time.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from decoy_engine.config import PipelineConfig
from pydantic import BaseModel
from tests.sentry._ratchet import load_allowlist
from tests.sentry.config import _readers as r

ROOT = Path(__file__).resolve().parents[3]
# The unread rows at the C0 merge. C1 (PRE-SCAN-RUN) removes `pre_scan`. A shrink-only pin: the
# registered baseline ratchet blocks growth on main, this blocks it inside the slice.
UNREAD_AT_C0 = frozenset(
    {"pre_scan", "scan_baseline.on_drift", "delivery", "protected_quarantine.access_policy"}
)


UNREAD: dict[str, Any] = load_allowlist("config-field-readers")


def _real() -> dict[str, Any]:
    return r.load_manifest(UNREAD)


def _text(found: list[str]) -> str:
    return "\n".join(found)


def test_t1_every_walked_path_has_exactly_one_entry() -> None:
    assert r.findings(PipelineConfig, _real(), ROOT) == []


def test_t1_a_missing_entry_is_a_finding() -> None:
    manifest = copy.deepcopy(_real())
    del manifest["readers"]["global_settings.seed"]
    assert "global_settings.seed" in _text(r.findings(PipelineConfig, manifest, ROOT))


def test_t1_a_path_with_two_entries_or_a_stale_entry_is_a_finding() -> None:
    manifest = copy.deepcopy(_real())
    manifest["unread"]["global_settings.seed"] = {"reason": "twice listed on purpose", "row": "X"}
    manifest["readers"]["no_such.field"] = {"other_command": "x", "row": "X"}
    text = _text(r.findings(PipelineConfig, manifest, ROOT))
    assert "global_settings.seed" in text and "no_such.field" in text


def test_t2_every_engine_entry_names_its_key() -> None:
    for path, entry in _real()["readers"].items():
        if "engine" in entry:
            assert r.engine_findings(path, entry) == [], path


def test_t2_an_engine_entry_that_does_not_name_its_key_fails() -> None:
    entry = {"engine": "decoy_engine.plan:compile_plan"}
    found = r.engine_findings("global_settings.no_such_setting_here", entry)
    assert found and "does not" in found[0]


def test_t2_a_model_class_does_not_count_as_a_reader() -> None:
    entry = {"engine": "decoy_engine.config:PreScanConfig"}
    assert r.engine_findings("pre_scan.on_findings", entry)


def test_t3_a_complete_chain_passes(tmp_path: Path) -> None:
    root = _chain_tree(tmp_path)
    assert r.cli_findings("pre_scan", _chain_entry(), root) == []


@pytest.mark.parametrize(
    ("file", "drop", "link"),
    [
        ("src/decoy/cli/run/_prepare.py", "run_pre_scan(", "prepare -> run_pre_scan"),
        ("src/decoy/api.py", "_mask_pre_scan(", "mask -> _mask_pre_scan"),
    ],
)
def test_t3_a_dropped_link_fails_even_when_the_next_hop_still_calls_on(
    tmp_path: Path, file: str, drop: str, link: str
) -> None:
    root = _chain_tree(tmp_path)
    target = root / file
    target.write_text(target.read_text().replace(drop, "unrelated("), encoding="utf-8")
    found = _text(r.cli_findings("pre_scan", _chain_entry(), root))
    assert link.split(" -> ")[0] in found and link.split(" -> ")[1] in found


def test_t3_a_call_inside_a_nested_function_is_not_a_direct_call(tmp_path: Path) -> None:
    root = _chain_tree(tmp_path)
    prep = root / "src/decoy/cli/run/_prepare.py"
    prep.write_text(
        "def prepare(cfg):\n    def never_called():\n        run_pre_scan(cfg)\n", encoding="utf-8"
    )
    assert r.cli_findings("pre_scan", _chain_entry(), root)


def test_t3_a_missing_file_or_function_fails(tmp_path: Path) -> None:
    root = _chain_tree(tmp_path)
    entry = _chain_entry()
    entry["cli"] = "src/decoy/cli/run/_prepare.py::no_such_function"
    assert r.cli_findings("pre_scan", entry, root)
    entry["cli"] = "src/decoy/cli/run/missing.py::prepare"
    assert r.cli_findings("pre_scan", entry, root)


def test_t4_the_unread_rows_never_grow() -> None:
    assert set(_real()["unread"]) <= UNREAD_AT_C0


def test_t4_each_unread_row_names_a_roadmap_row() -> None:
    for path, entry in _real()["unread"].items():
        assert entry.get("row"), path


class _Extra(BaseModel):
    thing: int = 0


class _Extended(PipelineConfig):
    extra_block: _Extra | None = None


def test_t5_a_new_nested_block_the_walker_was_never_told_about_fails() -> None:
    assert "extra_block.thing" in r.walk(_Extended)
    text = _text(r.findings(_Extended, _real(), ROOT))
    assert "extra_block.thing" in text and "extra_block:" in text


def test_t5_the_walk_does_not_enter_list_or_dict_items() -> None:
    paths = r.walk(PipelineConfig)
    assert "tables" in paths and not any(p.startswith("tables.") for p in paths)
    assert "pre_scan.detectors" in paths and "global_settings.seed" in paths


@pytest.mark.parametrize(
    ("spec", "rule"),
    [
        ("decoy_engine.plan._compile:compile_plan", "private"),
        ("decoy_engine.plan:_checks", "private"),
        ("decoy_engine.plan._compile:_hash_config", "private"),
        ("decoy_engine.plan:validate", "__all__"),
    ],
)
def test_t6_a_private_or_unlisted_engine_symbol_fails(spec: str, rule: str) -> None:
    found = r.engine_findings("global_settings.on_pool_exhaustion", {"engine": spec})
    assert found and rule in found[0]


def test_t6_a_public_listed_symbol_passes_the_visibility_rule() -> None:
    found = r.engine_findings(
        "global_settings.on_pool_exhaustion", {"engine": "decoy_engine.plan:compile_plan"}
    )
    assert found == []


@pytest.mark.parametrize(
    "path", ["scan_baseline.path", "quarantine.enabled", "delivery.mode", "global_settings.seed"]
)
def test_t7_a_short_or_common_key_with_no_via_fails(path: str) -> None:
    found = r.engine_findings(path, {"engine": "decoy_engine.plan:compile_plan"})
    assert found and "via" in found[0]


def test_t7_a_via_helper_the_symbol_does_not_call_fails() -> None:
    entry = {
        "engine": "decoy_engine.plan:compile_plan",
        "via": "decoy_engine.execution:run_pipeline",
    }
    found = r.engine_findings("quarantine.enabled", entry)
    assert found and "call" in found[0]


def _chain_entry() -> dict[str, Any]:
    prep = "src/decoy/cli/run/_prepare.py::prepare"
    scan = "src/decoy/cli/run/_pre_scan.py::run_pre_scan"
    core = "src/decoy/cli/run/_pre_scan.py::check_pre_scan"
    return {
        "cli": prep,
        "via": "pre_scan_requested",
        "chains": {
            "run": [prep, scan, core],
            "api.mask": ["src/decoy/api.py::mask", "src/decoy/api.py::_mask_pre_scan", core],
        },
    }


def _chain_tree(base: Path) -> Path:
    files = {
        "src/decoy/cli/run/_prepare.py": "def prepare(cfg):\n    if pre_scan_requested(cfg):\n        run_pre_scan(cfg)\n",
        "src/decoy/cli/run/_pre_scan.py": "def run_pre_scan(cfg):\n    check_pre_scan(cfg)\n\ndef check_pre_scan(cfg):\n    return cfg\n",
        "src/decoy/api.py": "def mask(cfg):\n    _mask_pre_scan(cfg)\n\ndef _mask_pre_scan(cfg):\n    check_pre_scan(cfg)\n",
    }
    for rel, text in files.items():
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text(text, encoding="utf-8")
    return base
