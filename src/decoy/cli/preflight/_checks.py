"""Source, target and native-companion readiness checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from decoy.cli.io import redact_url
from decoy.cli.preflight._result import _PreflightAccumulator


def _check_source_files(raw: dict[str, Any], base_dir: Path, acc: _PreflightAccumulator) -> None:
    """Check that every declared source file exists and is readable.

    File checks only. Parser config, column layout, and format inference are
    NOT checked here (those are engine-level concerns that require a profile
    pass). This check is about the files themselves, not their contents.

    Relative source paths resolve against `base_dir` (the pipeline YAML's directory), the SAME
    way `decoy run` and `estimate_job_capacity` do. Resolving against CWD let a same-named file
    in the working directory mask a source missing where the runner looks.
    """
    sources = raw.get("sources") or {}
    if not isinstance(sources, dict):
        return

    for table_name, src in sources.items():
        if not isinstance(src, dict):
            continue

        src_type = src.get("type") or "file"
        if src_type != "file":
            # Only file sources have a local path to check.
            # Non-file sources (database, API) are not checkable here.
            acc.add_pass(
                name=f"source.{table_name}.type",
                message=f"Source {table_name!r}: non-file type {src_type!r}; skipping local file check.",
                location=f"sources.{table_name}.type",
            )
            continue

        src_path_str = src.get("path")
        if not src_path_str:
            acc.add_fail(
                name=f"source.{table_name}.path",
                message=f"Source {table_name!r}: no 'path' declared.",
                location=f"sources.{table_name}.path",
            )
            continue

        shown = redact_url(str(src_path_str))
        src_path = Path(src_path_str)
        if not src_path.is_absolute():
            src_path = base_dir / src_path
        if not src_path.exists():
            acc.add_fail(
                name=f"source.{table_name}.exists",
                message=f"Source file not found: {shown}",
                location=f"sources.{table_name}.path",
            )
            continue

        if not src_path.is_file():
            acc.add_fail(
                name=f"source.{table_name}.is_file",
                message=f"Source path is not a regular file: {shown}",
                location=f"sources.{table_name}.path",
            )
            continue

        # Readability check (open for reading, read 0 bytes).
        try:
            with src_path.open("rb") as fh:
                fh.read(0)
        except OSError as exc:
            acc.add_fail(
                name=f"source.{table_name}.readable",
                message=f"Source file not readable: {shown} ({type(exc).__name__})",
                location=f"sources.{table_name}.path",
            )
            continue

        acc.add_pass(
            name=f"source.{table_name}.exists",
            message=f"Source file exists and is readable: {shown}",
            location=f"sources.{table_name}.path",
        )


def _check_target_overwrite(raw: dict[str, Any], acc: _PreflightAccumulator, base: Path) -> None:
    """Advisory: warn when an absolute output target is invalid, exists or cannot be written.

    These are warnings, not failures: the run overwrites, and the writer creates a missing
    folder, so only an existing file or a parent no run could write is worth surfacing. A
    relative path lands in a new run folder (AT-16), so none of these can apply to it.
    """
    from decoy.cli.io import LayoutError, RunLayout, is_absolute_local, target_parent_writable

    layout = RunLayout.fixed(base)
    targets = raw.get("targets")
    for table_name, target in targets.items() if isinstance(targets, dict) else ():
        if not isinstance(target, dict) or target.get("type") not in ("file", None):
            continue
        out_path_str = target.get("path")
        if not is_absolute_local(out_path_str):
            continue
        location = f"targets.{table_name}.path"
        try:
            out_path = layout.place_target(out_path_str)
            exists = out_path.exists()
            writable = exists or target_parent_writable(out_path)
        except (ValueError, OSError, LayoutError):
            msg = f"Output target path for table {table_name} is invalid."
            acc.add_warn(f"target.{table_name}.path_invalid", msg, location)
            continue
        if exists:
            msg = f"Output target already exists and would be overwritten: {out_path_str}"
            acc.add_warn(
                name=f"target.{table_name}.would_overwrite", message=msg, location=location
            )
        elif not writable:
            msg = f"Output target directory for table {table_name} cannot be created or written."
            acc.add_warn(f"target.{table_name}.parent_unwritable", msg, location)


def _check_native(raw: dict[str, Any], acc: _PreflightAccumulator) -> None:
    """Companion health (pass/warn, never a hard fail here -- a broken
    companion is `decoy run`'s fail-closed gate's job, not a preflight
    refusal) plus a STATIC, config-shape-only native-eligibility line.

    The eligibility line is explicitly labeled a possibility, not a
    guarantee (plan approach 4, open question 5): real admission needs the
    resolved route, the source profile, the resident Arrow table, and the
    compiled physical plan, none of which a profile-free preflight has.
    """
    import decoy_engine

    from decoy import _native_gate

    status = decoy_engine.native_companion_status()
    if status.ok:
        acc.add_pass(
            name="native.companion",
            message=(
                f"native companion present and healthy "
                f"(v{_native_gate.sanitize_abi(status.version)})."
            ),
        )
    elif status.present:
        acc.add_warn(
            name="native.companion",
            message=(
                f"native companion present but not usable ({status.reason}) -- "
                f"expected ABI {status.abi_expected}, got "
                f"{_native_gate.sanitize_abi(status.abi_actual)!r}. `decoy run` "
                "fails closed on this by default; use --no-native to roll back."
            ),
            code=status.reason,
        )
    else:
        acc.add_pass(
            name="native.companion",
            message="native companion not installed; masking runs on the Python fallback.",
        )

    if _native_gate.static_native_eligibility(raw):
        acc.add_pass(
            name="native.eligibility",
            message=(
                "Native eligibility: eligible by config (single non-FK csv/parquet/fixed_width "
                "mask table, companion-dependent native strategy present) -- a "
                "STATIC possibility, not a guarantee; the actual route depends "
                "on the resolved profile and resident data at run time."
            ),
        )
    else:
        acc.add_pass(
            name="native.eligibility",
            message=(
                "Native eligibility: not eligible by config shape (needs a single "
                "non-FK mask table (declared csv, parquet or fixed_width) with at least one hash/categorical/"
                "bucket_perturb/group_key column, and no validators/quarantine/"
                "post-scan integrity/vault/transforms/when-gates)."
            ),
        )
