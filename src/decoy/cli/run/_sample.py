"""`decoy run --sample N`: the config, the placement and the scratch folder of a sample.

A sample masks a head slice of the sources into a private scratch folder and writes nothing else
(plan 4.4). This module owns the three decisions that keep it there:

- `sample_config` renames every output to one relative file name, so nothing a pipeline declares
  (a path, a database, a bucket) is read back or reached;
- `sample_placement` and `open_sample_layout` put those names in the scratch folder, through the
  one `OutputPlacement.fixed` and `RunLayout.out_dir` that `--out-dir` uses;
- `require_project` and `open_scratch` find the project and take the scratch folder from its
  library, never from `open_run_layout`, so no claim, `out/<name>/`, `LATEST` or `current`.

Row choice stays in the engine: `subset.sample_request` is the only builder of a sample request.
Messages name flags, tables and codes, never a value.
"""

from __future__ import annotations

import contextlib
import copy
from datetime import timedelta
from pathlib import Path

from decoy.cli.io import (
    OUTPUT_PATH_ESCAPES,
    PROJECT_NOT_FOUND,
    LayoutError,
    OutputPlacement,
    RunLayout,
    explicit_project,
    find_project,
)
from decoy.cli.run._context import RunContext, UsageRefusal

SCRATCH_OWNER = "sample"  # the library scratch owner; the folder is `sample-<invocation id>`
SCRATCH_TTL = timedelta(hours=24)
QUARANTINE_FILE = "quarantine.jsonl"
_SUFFIX = {"csv": ".csv", "parquet": ".parquet", "fixed_width": ".txt"}
_SAMPLE_BASE = "the sample folder"
_NOT_READY = "--sample is not available yet. Run the pipeline without --sample."


def _one_component(name: object) -> bool:
    """True when `name` can be one file name: not empty, not `.` or `..`, no separator or NUL."""
    return (
        isinstance(name, str)
        and name not in ("", ".", "..")
        and not any(char in name for char in ("/", "\\", "\x00"))
    )


def sample_config(config_dict: dict) -> dict:
    """A copy of `config_dict` whose every output is one relative file name in the scratch folder.

    A table with a target gets `<table>.csv` for a csv file target, `<table>.parquet` for a
    parquet one, `<table>.txt` (and its layout) for fixed width, and `<table>.parquet` for every
    database and cloud target. An enabled quarantine block gets `quarantine.jsonl`. Declared
    paths are never read back. Raises `LayoutError` (`layout.output_path_escapes`) for a table
    name that is not one path component, judged before the suffix is added, since `..` plus a
    suffix would pass. Case-folded twins are the gate's collision rule, not repeated here.
    """
    config = copy.deepcopy(config_dict)
    targets = config.get("targets")
    if isinstance(targets, dict):
        for table in targets:
            if not _one_component(table):
                raise OUTPUT_PATH_ESCAPES.error(path=f"the table name {table!r}", base=_SAMPLE_BASE)
        config["targets"] = {table: _sample_target(table, spec) for table, spec in targets.items()}
    quarantine = config.get("quarantine")
    if isinstance(quarantine, dict) and quarantine.get("enabled"):
        quarantine["output_path"] = QUARANTINE_FILE
    return config


def _sample_target(table: str, spec: object) -> dict:
    """The file target that stands in for one declared target."""
    declared = spec if isinstance(spec, dict) else {}
    kind = declared.get("format") if declared.get("type", "file") == "file" else None
    suffix = _SUFFIX.get(kind, ".parquet") if isinstance(kind, str) else ".parquet"
    target: dict = {
        "type": "file",
        "format": "fixed_width" if suffix == ".txt" else suffix.lstrip("."),
        "path": f"{table}{suffix}",
    }
    if suffix == ".txt":
        target["layout"] = copy.deepcopy(declared.get("layout"))
    return target


def sample_placement(scratch: Path, typed: tuple[tuple[str, Path], ...] = ()) -> OutputPlacement:
    """The gate's placement for a sample: the scratch folder, as `--out-dir` is placed."""
    return OutputPlacement.fixed(scratch, typed)


def open_sample_layout(scratch: Path) -> RunLayout:
    """The run layout for a sample: the scratch folder stands in for the run folder."""
    return RunLayout.out_dir(scratch)


def require_project(ctx: RunContext) -> None:
    """Find the project of the pipeline, or refuse with `layout.project_not_found` (exit 1).

    A sample keeps its rows in the project's library, so a folder with no Decoy project marker
    (`Project.implicit`) has nowhere to put them. Runs before any scratch folder or engine call.
    """
    failure: LayoutError | None = None
    project = None
    try:
        project = find_project(ctx.config.resolve().parent, explicit_project(ctx.cli))
    except LayoutError as exc:
        failure = exc
    if failure is None and project is not None and project.implicit:
        failure = PROJECT_NOT_FOUND.error(where="the pipeline's folder")
    if failure is not None:
        raise UsageRefusal(failure.message, code=failure.code)
    ctx._sample_project = project


def open_scratch(ctx: RunContext, scopes: contextlib.ExitStack) -> None:
    """Take this run's scratch folder from the project library and point the layout at it.

    The folder is kept 24 hours (`decoy library clean` is the reaper until the sample record
    lands) and `discard_scratch` removes it on any failure. Raises `LibraryError`.
    """
    from decoy.cli.library import open_library, resolve_root

    root = resolve_root(project=ctx._sample_project.root).path
    library = open_library(root)
    allocation = scopes.enter_context(
        library.scratch(SCRATCH_OWNER, ctx.invocation_id, ttl=SCRATCH_TTL)
    )
    ctx._library, ctx._scratch = library, allocation.path
    ctx.layout = open_sample_layout(allocation.path)


def discard_scratch(ctx: RunContext) -> None:
    """Delete this run's scratch folder, best effort; a no-op when none was taken."""
    if ctx._library is not None and ctx._scratch is not None:
        ctx._library.delete_scratch(ctx._scratch)
        ctx._scratch = None


def begin(ctx: RunContext, scopes: contextlib.ExitStack) -> None:
    """The sample branch of `_flow`: the scratch folder, then (until SC2) a refusal.

    The run itself lands in SAMPLE SC2. Until then a sample that got this far stops here, so no
    run can write a declared target by mistake; `_flow` deletes the scratch folder.
    """
    open_scratch(ctx, scopes)
    raise UsageRefusal(_NOT_READY)
