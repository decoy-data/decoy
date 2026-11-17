"""Every generate starter template validates, runs, links its foreign keys, and uses only
types the live engine catalogs know (GEN-CATALOG GC2, QA check GEN-14).

The set is read from the registry, not a fixed list, so a seventh template is covered the
day it is added. The catalog guard fails here, not at a user's run, when the engine renames
a type or a faker provider.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.templates import get_template, list_templates
from tests.generate_industry_templates import GENERATE_INDUSTRY_TEMPLATES

runner = CliRunner()

SMALL_ROWS = 30


def _generate_names() -> list[str]:
    names = []
    for t in list_templates():
        cfg = yaml.safe_load(t.body)
        tables = cfg.get("tables") or []
        if tables and all(tb.get("generate_columns") for tb in tables):
            names.append(t.name)
    return names


def test_the_six_industry_templates_are_registered():
    names = set(_generate_names())
    assert set(GENERATE_INDUSTRY_TEMPLATES) <= names


@pytest.mark.parametrize("name", _generate_names())
def test_generate_template_validates_runs_and_links_keys(name: str, tmp_path: Path):
    cfg = yaml.safe_load(get_template(name).body)
    for table in cfg["tables"]:
        table["row_count"] = SMALL_ROWS
    for target in cfg["targets"].values():
        target["path"] = str(tmp_path / Path(target["path"]).name)
    config_path = tmp_path / f"{name}.yaml"
    config_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    validate = runner.invoke(app, ["validate", "config", str(config_path)])
    assert validate.exit_code == 0, f"{name}: validate failed:\n{validate.output}"
    run = runner.invoke(app, ["run", str(config_path)])
    assert run.exit_code == 0, f"{name}: run failed:\n{run.output}"

    frames = {n: pd.read_csv(Path(t["path"]), dtype=str) for n, t in cfg["targets"].items()}
    for table in cfg["tables"]:
        assert len(frames[table["name"]]) == SMALL_ROWS
    links = 0
    for table in cfg["tables"]:
        for col in table["generate_columns"]:
            if col["type"] == "reference":
                links += 1
                child = frames[table["name"]][col["name"]].dropna()
                parent = set(frames[col["reference_table"]][col["reference_column"]])
                assert set(child) <= parent, f"{name}: {table['name']}.{col['name']} not linked"
    if name in GENERATE_INDUSTRY_TEMPLATES:
        assert links >= 1, f"{name}: an industry template must declare at least one foreign key"


@pytest.mark.parametrize("name", _generate_names())
def test_generate_template_uses_only_catalog_types(name: str):
    from decoy_engine import list_generate_faker_providers
    from decoy_engine.config import generate_option_catalog

    catalog = generate_option_catalog()
    fakers = set(list_generate_faker_providers())
    cfg = yaml.safe_load(get_template(name).body)
    for table in cfg["tables"]:
        for col in table["generate_columns"]:
            assert col["type"] in catalog, f"{name}.{col['name']}: unknown type {col['type']}"
            spec = catalog[col["type"]]
            known = {*spec.required, *spec.optional, *spec.common, "name", "type"}
            assert set(col) <= known, f"{name}.{col['name']}: unknown option {set(col) - known}"
            assert set(spec.required) <= set(col), f"{name}.{col['name']}: missing required"
            if col["type"] == "faker":
                assert col["faker_type"] in fakers, f"{name}.{col['name']}: {col['faker_type']}"


def test_generate_templates_carry_no_real_looking_seeds():
    for name in GENERATE_INDUSTRY_TEMPLATES:
        body = get_template(name).body
        assert "x-derived-from-disguise" not in body
        assert "snapshot_file" not in body
