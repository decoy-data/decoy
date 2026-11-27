"""Shared setup for the delivery sink cases: a project with two tables, and run helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.csv_sources import csv_source

runner = CliRunner()
RUN_ID = re.compile(r"[0-9]{8}T[0-9]{12}Z-[0-9a-f]{8}(?:[0-9a-f]{4}){0,6}")


def project(tmp_path: Path, tables: int = 2, targets: str = "relative") -> tuple[Path, Path]:
    """A project root and its pipeline YAML; `targets` is "relative" or "absolute"."""
    root = tmp_path / "proj"
    root.mkdir(parents=True)
    (root / "decoy.yaml").write_text("kind: decoy-project/v1\n", encoding="utf-8")
    cfg: dict = {
        "version": 2,
        "global_settings": {"seed": 3},
        "sources": {},
        "tables": [],
        "targets": {},
    }
    for i in range(tables):
        name = f"t{i + 1}"
        src = root / f"in{i + 1}.csv"
        pd.DataFrame({"code": ["a", "b"]}).to_csv(src, index=False)
        cfg["sources"][name] = csv_source(src)
        cfg["tables"].append({"name": name, "columns": [{"name": "code", "strategy": "redact"}]})
        path = f"{name}.csv" if targets == "relative" else str(tmp_path / "abs" / f"{name}.csv")
        cfg["targets"][name] = {"type": "file", "format": "csv", "path": path}
    yml = root / "pipelines" / "orders" / "pipeline.yaml"
    yml.parent.mkdir(parents=True)
    yml.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return root, yml


def run(yml: Path, *args: str):
    return runner.invoke(app, ["run", str(yml), "--json", *args])


def document(result) -> dict:
    """The run result document of a `--json` run, success or error."""
    try:
        # A warning line (the native-kernel notice on a host without the bundle) may precede it.
        text = (
            result.output[result.output.index("\n{") + 1 :]
            if not result.output.startswith("{")
            else result.output
        )
        return json.loads(text)["result"]
    except (ValueError, KeyError) as exc:
        raise AssertionError(f"not a JSON document: {result.output[:300]!r}") from exc


def runs(root: Path) -> list[Path]:
    folder = root / "out" / "orders"
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if RUN_ID.fullmatch(p.name))


def latest(root: Path) -> str | None:
    path = root / "out" / "orders" / "LATEST"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else None


def litter(root: Path) -> list[str]:
    """Stage siblings and attempt files the run left behind."""
    return sorted(
        p.name
        for p in (root / "out" / "orders").iterdir()
        if p.name.startswith("._decoy") or p.name.endswith(".attempt")
    )


def vaulted(yml: Path, monkeypatch) -> None:
    from tests.keyed_secret import TEST_MASK_SECRET, TEST_MASK_SECRET_ENV, TEST_MASK_SECRET_REF

    monkeypatch.setenv(TEST_MASK_SECRET_ENV, TEST_MASK_SECRET)
    cfg = yaml.safe_load(yml.read_text(encoding="utf-8"))
    cfg["global_settings"]["mask_secret_ref"] = TEST_MASK_SECRET_REF
    for table in cfg["tables"]:
        table["columns"][0] = {
            "name": "code",
            "strategy": "hash",
            "namespace": "code_ns",
            "vault": True,
        }
    yml.write_text(yaml.safe_dump(cfg), encoding="utf-8")


def post_scan(yml: Path) -> None:
    """Ask the pipeline for the integrity report, so a run has one to deliver or to keep."""
    cfg = yaml.safe_load(yml.read_text(encoding="utf-8"))
    cfg["post_scan"] = {"integrity": True}
    yml.write_text(yaml.safe_dump(cfg), encoding="utf-8")
