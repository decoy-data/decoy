"""The records a `decoy run` stores in its project library (plan 4.16, 4.17; LIB L3a).

`store_evidence` is the one entry point for the evidence half: the run builds its manifest once
(`cli/run/_evidence.py`, its only caller) and hands it here unchanged. The library root is the
pipeline's (plan 4.1: `DECOY_LIBRARY`, else the project that holds the YAML); `DECOY_LIBRARY=off`
or the run's `--no-library` stores nothing.

Path fields the evidence kind declares (`records.kind_spec("evidence").path_fields`) are stored
relative to the project, the library root's parent (plan LL8). Under a `decoy.yaml` project the
manifest already records them that way (`path_base: "project"`), so the payload is stored as
built; elsewhere an absolute path inside the project is made relative and one outside it stays
absolute.

A store never fails the run (plan 4.17: warn, keep the exit code): every failure comes back as a
`StoreReport` with `status="failed"` and a code, for the run card and `--json`.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Literal

__all__ = ["StoreReport", "store_evidence"]

Status = Literal["stored", "off", "failed"]


@dataclass(frozen=True)
class StoreReport:
    """What happened to a run's records: `root` is the library root (None when off or when no
    root could be found), `evidence` the stored record's id, `code` the failure's code."""

    status: Status
    root: str | None = None
    evidence: str | None = None
    code: str | None = None

    def as_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"status": self.status}
        if self.status == "failed":
            out["code"] = self.code
        if self.root is not None:
            out["root"] = self.root
        if self.evidence is not None:
            out["evidence"] = self.evidence
        return out


def _relative(value: object, project: Path) -> object:
    if not isinstance(value, str) or not value:
        return value
    path = Path(value)
    if not path.is_absolute():
        return value
    absolute = Path(os.path.abspath(path))
    base = Path(os.path.abspath(project))
    if absolute == base or base in absolute.parents:
        return absolute.relative_to(base).as_posix()
    return PurePosixPath(absolute.as_posix()).as_posix()


def relativize(payload: dict[str, Any], pointers: tuple[str, ...], project: Path) -> dict[str, Any]:
    """`payload` with each path field (`/payload/a/*/b` pointers, as the kind spec gives them)
    relative to `project` where it is an absolute path inside it."""
    out = copy.deepcopy(payload)
    for pointer in pointers:
        parts = pointer.strip("/").split("/")
        if parts and parts[0] == "payload":
            parts = parts[1:]
        _apply(out, parts, project)
    return out


def _apply(node: Any, parts: list[str], project: Path) -> None:
    if not parts or node is None:
        return
    head, rest = parts[0], parts[1:]
    if head == "*":
        items = node.values() if isinstance(node, dict) else node if isinstance(node, list) else ()
        for item in items:
            _apply(item, rest, project)
        return
    if not isinstance(node, dict) or head not in node:
        return
    if rest:
        _apply(node[head], rest, project)
    else:
        node[head] = _relative(node[head], project)


def store_evidence(
    manifest: dict[str, Any],
    *,
    pipeline: Path,
    invocation_id: str,
    enabled: bool,
    producer: dict[str, str],
    now: datetime | None = None,
) -> StoreReport:
    """Store the run's evidence manifest as an `evidence` record; never raises."""
    from decoy_engine import records

    from decoy.cli.io import LayoutError, find_project, project_relative_posix
    from decoy.cli.library._errors import LibraryError
    from decoy.cli.library._paths import resolve_root
    from decoy.cli.library._store import open_library

    if not enabled:
        return StoreReport("off")
    code: str | None = None
    root_text: str | None = None
    try:
        root = resolve_root(pipeline=pipeline)
        if not root.records:
            return StoreReport("off")
        root_text = str(root.path)
        project = root.path.parent
        owner = find_project(Path(os.path.abspath(pipeline)).parent, None).root
        spec = records.kind_spec("evidence")
        paths = spec.path_fields if spec is not None else ()
        payload = relativize(manifest, paths, project)
        envelope = records.build(
            "evidence",
            payload,
            producer=producer,
            invocation_id=invocation_id,
            created_at=now or datetime.now(timezone.utc),
            labels={"pipeline": project_relative_posix(owner, pipeline)},
        )
        stored = open_library(root.path).put(envelope)
        return StoreReport("stored", root_text, stored.id)
    except (LayoutError, LibraryError, records.RecordError) as exc:
        code = getattr(exc, "code", None) or type(exc).__name__
    return StoreReport("failed", root_text, code=code)
