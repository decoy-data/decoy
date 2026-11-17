"""Store a `decoy run`'s evidence record in the library (plan 4.3, 4.16, 4.17; L3a evidence half).

The run builds its `cli-local-1` manifest once (`decoy.cli.evidence.build_manifest`) and hands
that same dict here, so the record payload equals the `--evidence-out` file byte for byte after
canonicalization (amendment 2026-11-12: built once, stored as built; no path is rewritten here,
export strips the declared path fields). The envelope carries the run's invocation id, the
`pipeline` label the run passes in (the YAML's project-relative POSIX path, what
`library list --pipeline` reads) and the table names. Evidence links to nothing; the run-result record (RESULT C1a/C1b) will link
to it.

Records are on by default (4.16): `--no-library` or `DECOY_LIBRARY=off` skips them. A store that
fails never fails the run (4.17): `store_evidence` returns a coded outcome for the caller to warn
with, and never raises.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from decoy.cli.library._errors import LIBRARY_WRITE_FAILED, LibraryError

__all__ = ["StoreOutcome", "store_evidence"]


@dataclass(frozen=True)
class StoreOutcome:
    """What happened to the run's records: `stored` (with the root and the evidence id),
    `skipped` (records are off) or `failed` (with a code; the run's exit code is unchanged)."""

    status: Literal["stored", "skipped", "failed"]
    root: Path | None = None
    evidence: str | None = None
    code: str | None = None

    def to_json(self) -> dict[str, str]:
        out: dict[str, str] = {"status": self.status}
        if self.root is not None:
            out["root"] = str(self.root)
        if self.evidence is not None:
            out["evidence"] = self.evidence
        if self.code is not None:
            out["code"] = self.code
        return out


def store_evidence(
    manifest: Mapping[str, Any],
    *,
    pipeline: Path,
    label: str,
    invocation_id: str,
    enabled: bool = True,
    environ: Mapping[str, str] | None = None,
) -> StoreOutcome:
    """Put the run's manifest as an `evidence` record in the library of the run's YAML,
    `pipeline`. `label` is the YAML's project-relative POSIX path. Never raises."""
    if not enabled:
        return StoreOutcome("skipped")
    import decoy_engine
    from decoy_engine import DecoyError, records

    from decoy._version import __version__
    from decoy.cli.io import LayoutError
    from decoy.cli.library._paths import check_root_budget, resolve_root
    from decoy.cli.library._store import open_library

    code: str | None = None
    root: Path | None = None
    try:
        found = resolve_root(pipeline=pipeline, environ=environ)
        if not found.records:
            return StoreOutcome("skipped")
        root = found.path  # already anchored: absolute, links resolved
        check_root_budget(root)
        envelope = records.build(
            "evidence",
            dict(manifest),
            producer={
                "name": "decoy-cli",
                "version": __version__,
                "engine_version": decoy_engine.__version__,
            },
            invocation_id=invocation_id,
            created_at=datetime.now(timezone.utc),
            labels={
                "pipeline": label,
                "tables": sorted(manifest.get("output_fingerprints") or {}),
            },
        )
        stored = open_library(root).put(envelope)
        return StoreOutcome("stored", root=root, evidence=stored.id)
    except LibraryError as exc:
        code = exc.code
    except (LayoutError, DecoyError) as exc:
        code = str(getattr(exc, "code", None) or LIBRARY_WRITE_FAILED)
    except OSError:
        code = LIBRARY_WRITE_FAILED
    return StoreOutcome("failed", root=root, code=code)
