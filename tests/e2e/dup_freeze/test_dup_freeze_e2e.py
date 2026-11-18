"""The DUP-FREEZE engine changes, proved through the CLI (roadmap row 24zf, slice CL5).

The engine changes shipped in `decoy-engine` 0.24.0 and every later pin keeps them: each
`joint_mask` group draws its own stream (E2), a profile's `generated_at` ends `+00:00` (E3),
digests write UTF-8 while the evidence manifest hash keeps its bytes (E1), and an unknown
engine flag spelling raises `EnvFlagError`. The last one needs a CLI arm: the root crash guard
must show the variable name and code, not `internal error (EnvFlagError)`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import typer
import yaml
from typer.testing import CliRunner

from decoy.__main__ import _GuardedGroup, app
from tests.csv_sources import file_source
from tests.keyed_secret import TEST_MASK_SECRET_REF

pytestmark = pytest.mark.usefixtures("mask_secret")

runner = CliRunner()

_WORKER_ENV = "DECOY_INSIDE_ISOLATED_WORKER"
_N = 40
_REF = "us_zip5_city_state"
# A distinctive spelling, so any echo of the value into output is found.
_BAD_VALUE = "maybe-CANARY-7731"


def _write_config(folder: Path, cfg: dict[str, Any], name: str = "pipeline.yaml") -> Path:
    path = folder / name
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return path


def _group(column: str) -> dict[str, Any]:
    return {
        "name": column,
        "strategy": "joint_mask",
        "provider_config": {"columns": [column], "reference": _REF, "key_by": "id", "mode": "gen"},
    }


# AT-CL5-1 (E2): two joint_mask groups on one table draw different reference rows.
def test_cl5_1_two_joint_mask_groups_draw_separate_streams(tmp_path: Path) -> None:
    from decoy_engine.transforms.joint_mask import JointMaskConfig

    src = tmp_path / "in.csv"
    pd.DataFrame(
        {
            "id": [f"P{i:04d}" for i in range(_N)],
            "zip": ["00000"] * _N,
            "city": ["placeholder"] * _N,
        }
    ).to_csv(src, index=False)
    out = tmp_path / "out.csv"
    cfg = _write_config(
        tmp_path,
        {
            "version": 2,
            "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
            "sources": {"t": file_source(src, "csv")},
            "tables": [
                {
                    "name": "t",
                    "columns": [
                        {"name": "id", "strategy": "passthrough"},
                        _group("zip"),
                        _group("city"),
                    ],
                }
            ],
            "targets": {"t": {"type": "file", "format": "csv", "path": str(out)}},
        },
    )
    result = runner.invoke(app, ["run", str(cfg)])
    assert result.exit_code == 0, result.output

    rows = pd.read_csv(out, dtype=str, keep_default_na=False)
    table = JointMaskConfig.from_dict(
        {"columns": ["zip", "city"], "reference": _REF, "key_by": "id"}
    ).table
    real = {(table.row(i)["zip"], table.row(i)["city"]) for i in range(table.row_count)}
    coupled = sum((z, c) in real for z, c in zip(rows["zip"], rows["city"], strict=True))
    # One shared stream picks one reference row for both groups, so every pair would be real.
    assert coupled < _N // 2, f"{coupled} of {_N} rows picked one shared reference row"


def _stamps(node: Any) -> list[str]:
    """Every `generated_at` string in a nested JSON document."""
    if isinstance(node, dict):
        found = [v for k, v in node.items() if k == "generated_at" and isinstance(v, str)]
        return found + [s for v in node.values() for s in _stamps(v)]
    if isinstance(node, list):
        return [s for v in node for s in _stamps(v)]
    return []


# AT-CL5-1 (E3): a profile's generated_at has one shape, +00:00. No pinned-CLI command writes a
# bare profile any more (`scan` writes `scan-set/v1`), so the check calls the engine call the CLI
# used to make; the legacy `Z` fixture still loads through `scan show` (test_scan_saved.py).
def test_cl5_1_profile_generated_at_ends_utc_offset() -> None:
    from decoy_engine import profile_columns

    frame = pd.DataFrame({"name": ["a", "b", "c"], "n": ["1", "2", "3"]})
    profile = profile_columns(frame, source_label="x.csv", sample_strategy="head")
    stamp = profile.to_dict()["generated_at"]
    assert stamp.endswith("+00:00"), stamp


# AT-CL5-1 (E1): the plan's config digest writes non-ASCII text as UTF-8, not as \uXXXX.
def test_cl5_1_plan_config_hash_writes_non_ascii_as_utf8(tmp_path: Path) -> None:
    def compiled_hash(table: str) -> str:
        cfg = _write_config(
            tmp_path,
            {
                "global_settings": {"seed": 7},
                "tables": [
                    {
                        "name": table,
                        "columns": [
                            {
                                "name": "email",
                                "strategy": "faker_email",
                                "provider": "person_email",
                                "backend_type": "faker",
                                "backend_version": "stub-0",
                                "cardinality_mode": "reuse",
                            }
                        ],
                    }
                ],
            },
            name=f"{table}.yaml",
        )
        plan = tmp_path / f"{table}.plan.json"
        result = runner.invoke(
            app,
            ["validate", "compile", str(cfg), "--output", str(plan), "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        return json.loads(plan.read_text(encoding="utf-8"))["pipeline_config_hash"]

    # Golden for table `données`: the UTF-8 canonical form. A plan compiled on an engine that
    # escaped it (`données`) carries a different hash and is refused on a pinned-plan check.
    assert compiled_hash("données") == _GOLDEN_NON_ASCII_PLAN_HASH
    assert compiled_hash("donnees") != _GOLDEN_NON_ASCII_PLAN_HASH


_GOLDEN_NON_ASCII_PLAN_HASH = "633a7cf81ef1f013810887ab98284567191dcf963414f5f4d5ac4a4c583a159b"


# AT-CL5-2: control, the CLI evidence manifest hash keeps its bytes for non-ASCII text.
def test_cl5_2_evidence_manifest_hash_keeps_its_bytes(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    pd.DataFrame({"id": ["1", "2"], "v": ["a", "b"]}).to_csv(src, index=False)
    out = tmp_path / "out.csv"
    evidence = tmp_path / "evidence.json"
    cfg = _write_config(
        tmp_path,
        {
            "version": 2,
            "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
            "sources": {"données": file_source(src, "csv")},
            "tables": [
                {
                    "name": "données",
                    "columns": [
                        {"name": "id", "strategy": "passthrough"},
                        {"name": "v", "strategy": "passthrough"},
                    ],
                }
            ],
            "targets": {"données": {"type": "file", "format": "csv", "path": str(out)}},
        },
    )
    result = runner.invoke(app, ["run", str(cfg), "--evidence-out", str(evidence)])
    assert result.exit_code == 0, result.output

    manifest = json.loads(evidence.read_text(encoding="utf-8"))
    assert "données" in evidence.read_text(encoding="utf-8").replace("\\u00e9", "é")
    stripped = {
        k: v
        for k, v in manifest.items()
        if k not in {"manifest_hash", "signature", "signature_alg", "signature_key_id"}
    }
    # The pre-change rule, written out here so the test does not take it from the code it checks:
    # sorted keys, compact separators, UTF-8 (ensure_ascii off).
    expected = json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert manifest["manifest_hash"] == "sha256:" + hashlib.sha256(expected.encode()).hexdigest()


# AT-CL5-3: an engine EnvFlagError shows the variable and code, never the value.
def _guarded(exc: BaseException) -> typer.Typer:
    guarded = typer.Typer(cls=_GuardedGroup, pretty_exceptions_enable=False)

    @guarded.callback()
    def _root() -> None:
        """Root."""

    @guarded.command()
    def boom() -> None:
        raise exc

    return guarded


def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    # tests/conftest.py sets DECOY_DEBUG=1; the guard's production default is needed here.
    monkeypatch.delenv("DECOY_DEBUG", raising=False)


def test_cl5_3_handler_shows_variable_and_code_for_an_env_flag_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from decoy_engine.errors import EnvFlagError

    _clean(monkeypatch)
    result = CliRunner().invoke(_guarded(EnvFlagError(_WORKER_ENV)), ["boom"])
    assert result.exit_code == 1
    assert _WORKER_ENV in result.output
    assert "env_flag_invalid" in result.output
    assert "internal error" not in result.output
    assert "EnvFlagError" not in result.output
    assert "Traceback" not in result.output


def test_cl5_3_handler_arm_carries_no_exception_context(monkeypatch: pytest.MonkeyPatch) -> None:
    from decoy_engine.errors import EnvFlagError

    _clean(monkeypatch)
    group = typer.main.get_command(_guarded(EnvFlagError(_WORKER_ENV)))
    with pytest.raises(typer.Exit) as caught:
        with group.make_context("decoy", ["boom"]) as ctx:
            group.invoke(ctx)
    assert caught.value.exit_code == 1
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_cl5_3_run_with_an_unknown_worker_marker_never_prints_the_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import decoy_engine
    from decoy_engine.execution._isolated_common import inside_isolated_worker

    _clean(monkeypatch)
    monkeypatch.setenv(_WORKER_ENV, _BAD_VALUE)

    def engine_run(*_args: Any, **_kwargs: Any) -> Any:
        # `decoy run` does not take the isolated route in the pinned engine (the governor is not
        # wired in), so the run reaches the marker the way `run_pipeline_isolated` does.
        inside_isolated_worker()
        raise AssertionError("the unknown marker should have raised")

    monkeypatch.setattr(decoy_engine, "run_pipeline", engine_run)
    src = tmp_path / "in.csv"
    pd.DataFrame({"id": ["1", "2"]}).to_csv(src, index=False)
    cfg = _write_config(
        tmp_path,
        {
            "version": 2,
            "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
            "sources": {"t": file_source(src, "csv")},
            "tables": [{"name": "t", "columns": [{"name": "id", "strategy": "passthrough"}]}],
            "targets": {"t": {"type": "file", "format": "csv", "path": str(tmp_path / "o.csv")}},
        },
    )
    result = runner.invoke(app, ["run", str(cfg)])
    assert result.exit_code == 1, result.output
    assert _BAD_VALUE not in result.output
    assert "internal error" not in result.output
    assert _WORKER_ENV in result.output
    assert "env_flag_invalid" in result.output
