"""The two distribution schema tags are frozen format names (freeze S7b, `docs/release/frozen-surfaces.md`)."""

from __future__ import annotations

from pathlib import Path

from decoy.distribution import manifest as manifest_mod
from decoy.distribution import version_document as vd


def test_version_document_tag_is_the_frozen_format_name() -> None:
    doc = vd.build_document(
        latest="1.0.0",
        min_supported="1.0.0",
        artifacts={},
        serial=1,
        generated="2026-01-01T00:00:00Z",
    )
    assert doc["schema_version"] == "cli-version-document/v1"


def test_bundle_manifest_tag_is_the_frozen_format_name(tmp_path: Path) -> None:
    (tmp_path / "decoy").write_text("#!/bin/sh\n")
    man = manifest_mod.compute_manifest(tmp_path, version="0.1.0", target="t")
    assert man["schema_version"] == "cli-bundle-manifest/v1"
