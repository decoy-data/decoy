"""The output-surface registry `docs/qa/surfaces.toml` holds exactly what plan 15.2.5 lists."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

PATH = Path(__file__).resolve().parents[3] / "docs" / "qa" / "surfaces.toml"
SURFACES = {
    "output-data-files",
    "stdout",
    "stderr",
    "logs",
    "run-result-files",
    "evidence-manifests",
    "integrity-reports",
    "scan-documents",
    "vault-files",
    "notification-payloads",
    "tester-capture",
    "finding-records",
    "pass-records",
    "slack-text",
}
EXCEPTIONS = {"passthrough", "truncate-prefix", "text-redact-context", "unmask-output"}
CHECKS = {"cells", "needles", "needles-encrypted"}


def _doc() -> dict:
    return tomllib.loads(PATH.read_text(encoding="utf-8"))


def test_the_registry_lists_every_planned_surface_once() -> None:
    doc = _doc()
    assert doc["schema_version"] == 1
    ids = [s["id"] for s in doc["surface"]]
    assert len(ids) == len(set(ids))
    assert set(ids) == SURFACES


def test_every_surface_names_its_check() -> None:
    for s in _doc()["surface"]:
        assert set(s) == {"id", "name", "check"}
        assert s["check"] in CHECKS
    cells = [s["id"] for s in _doc()["surface"] if s["check"] == "cells"]
    assert cells == ["output-data-files"]


def test_the_documented_exceptions_are_registered_against_real_surfaces() -> None:
    doc = _doc()
    assert {e["id"] for e in doc["exception"]} == EXCEPTIONS
    for e in doc["exception"]:
        assert set(e["applies_to"]) <= SURFACES
        assert e["rule"]
