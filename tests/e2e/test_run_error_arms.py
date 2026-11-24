"""CL4 (24zf): every `decoy run` error arm goes through the one error emitter.

Section 7.1 and 7.4 of docs/plans/2026-11-23-dup-freeze-cl4.md name each arm's human lines, hint
and ordered `--json` members. The orders below are literals so a rebuild of the payload cannot
agree with itself. Covers AT-3, AT-6, AT-7, AT-9, AT-10, AT-11 and the run half of AT-16.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_CAPACITY, EXIT_RUNTIME, EXIT_USAGE
from tests.csv_sources import csv_source
from tests.e2e.first_user.test_items_error_envelope import SCHEMA

runner = CliRunner()
VERBOSE_HINT = "rerun with --verbose for the full traceback."
MEMORY_HINT = "this job needs more memory than this host has; use a larger tier or reduce the job."
TAIL = ["result", "result_status"]


def _config(tmp_path: Path) -> Path:
    src = tmp_path / "in.csv"
    pd.DataFrame({"customer_id": ["1", "2"], "email": ["a@x.com", "b@x.com"]}).to_csv(
        src, index=False
    )
    cfg = {
        "version": 2,
        "global_settings": {"seed": 42},
        "sources": {"customers": csv_source(src)},
        "tables": [
            {
                "name": "customers",
                "columns": [
                    {"name": "customer_id", "strategy": "passthrough"},
                    {"name": "email", "strategy": "redact"},
                ],
            }
        ],
        "targets": {
            "customers": {"type": "file", "format": "csv", "path": str(tmp_path / "out.csv")}
        },
    }
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.dump(cfg), encoding="utf-8")
    return path


def _capacity_exc():
    from decoy_engine.execution import ExecutionError

    return ExecutionError(
        code="out_of_core_insufficient_memory", message="needs about 8 GB of memory (secret-7)."
    )


def _vault_exc():
    from decoy_engine import VaultError, reasons

    return VaultError(code=reasons.runtime.VAULT_COMMIT_FAILED, message="commit failed")


def _missing_extra_exc():
    return ModuleNotFoundError("No module named 'boto3'", name="boto3")


def _run(tmp_path: Path, exc: BaseException | None, *flags: str):
    cfg = _config(tmp_path)
    if exc is None:
        return runner.invoke(app, ["run", str(cfg), *flags])
    with mock.patch("decoy_engine.run_pipeline", side_effect=exc):
        return runner.invoke(app, ["run", str(cfg), *flags])


def _doc(result) -> dict:
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1, result.stdout
    return json.loads(lines[0])


# arm -> (exception factory, exit, ordered --json keys, human hint lines)
ARMS: dict[str, tuple] = {
    "generic": (
        lambda: RuntimeError("boom"),
        EXIT_RUNTIME,
        ["command", "status", "error", "hint", "config", "mode", *TAIL],
        [VERBOSE_HINT],
    ),
    "capacity": (
        _capacity_exc,
        EXIT_CAPACITY,
        [
            "command", "status", "error", "code", "hint", "config", "mode", "error_kind",
            *TAIL,
        ],
        [MEMORY_HINT],
    ),
    "missing extra": (
        _missing_extra_exc,
        EXIT_USAGE,
        [
            "command", "status", "error", "hint", "config", "mode", "error_kind", "extra",
            *TAIL,
        ],
        [VERBOSE_HINT],
    ),
    "vault commit": (
        _vault_exc,
        EXIT_RUNTIME,
        ["command", "status", "error", "hint", "config", "mode", *TAIL],
        None,  # the vault hint text is the module constant; checked by identity below
    ),
}  # fmt: skip


def _hint_lines(stderr: str) -> list[str]:
    return [line.split("hint: ", 1)[1] for line in stderr.splitlines() if "hint: " in line]


@pytest.mark.parametrize("arm", sorted(ARMS))
def test_arm_json_keys_are_the_literal_ordered_list(tmp_path: Path, arm: str) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    factory, code, keys, _ = ARMS[arm]
    result = _run(tmp_path, factory(), "--json")

    assert result.exit_code == code, result.output
    doc = _doc(result)
    jsonschema.validate(doc, SCHEMA)
    # `reason` rides after the context members when the engine has a record for the failure.
    assert [k for k in doc if k != "reason"] == keys


@pytest.mark.parametrize("arm", sorted(ARMS))
def test_arm_hint_lines_match_the_table(tmp_path: Path, arm: str) -> None:
    from decoy.cli.run._vault import VAULT_COMMIT_FAILED_HINT

    factory, _, _, hints = ARMS[arm]
    expected = [VAULT_COMMIT_FAILED_HINT] if arm == "vault commit" else hints
    for flags in ((), ("--quiet",)):
        result = _run(tmp_path, factory(), *flags)
        assert _hint_lines(result.stderr) == expected, (arm, flags, result.stderr)
    doc = _doc(_run(tmp_path, factory(), "--json"))
    assert doc["hint"] == expected[0]


def test_the_vault_hint_is_alone_not_followed_by_the_verbose_hint(tmp_path: Path) -> None:
    result = _run(tmp_path, _vault_exc())

    assert VERBOSE_HINT not in result.stderr


# AT-6
def test_a_generic_run_error_prints_in_quiet_with_one_hint(tmp_path: Path) -> None:
    result = _run(tmp_path, RuntimeError("boom"), "--quiet")

    assert result.exit_code == EXIT_RUNTIME
    assert result.stdout == ""
    assert "error: " in result.stderr
    assert len(_hint_lines(result.stderr)) == 1


# AT-7
def test_the_capacity_label_is_on_the_human_line_only(tmp_path: Path) -> None:
    human = _run(tmp_path, _capacity_exc())
    assert human.exit_code == EXIT_CAPACITY
    line = next(x for x in human.stderr.splitlines() if "capacity:" in x)
    assert line.startswith("error: capacity: ")
    assert "[" not in line.split("capacity:")[0]
    doc = _doc(_run(tmp_path, _capacity_exc(), "--json"))
    assert not doc["error"].startswith("capacity:")
    assert doc["code"] == "out_of_core_insufficient_memory"
    assert doc["error_kind"] == "capacity"


def test_a_capacity_error_never_shows_the_engine_text(tmp_path: Path) -> None:
    for flags in ((), ("--quiet",), ("--json",)):
        result = _run(tmp_path, _capacity_exc(), *flags)
        assert "secret-7" not in result.output
        assert "8 GB" not in result.output


# AT-3
@pytest.mark.parametrize("arm", ["generic", "capacity"])
def test_the_error_document_keeps_the_result_members(tmp_path: Path, arm: str) -> None:
    doc = _doc(_run(tmp_path, ARMS[arm][0](), "--json"))

    assert doc["result_status"]["file"] in {"not_requested", "written", "failed"}
    assert "result" in doc
    assert {"config", "mode"} <= set(doc)


def test_abandon_runs_before_the_envelope_is_written(tmp_path: Path) -> None:
    from decoy.cli.io._layout import RunLayout
    from decoy.ui import output

    events: list[str] = []
    real_abandon = RunLayout.abandon
    real_emit = output.emit_json

    def spy_abandon(self) -> None:
        events.append("abandon")
        real_abandon(self)

    def spy_emit(state, payload) -> None:
        events.append("write")
        real_emit(state, payload)

    with (
        mock.patch.object(RunLayout, "abandon", spy_abandon),
        mock.patch.object(output, "emit_json", spy_emit),
    ):
        result = _run(tmp_path, RuntimeError("x"), "--json")

    assert result.exit_code == EXIT_RUNTIME
    assert "abandon" in events and "write" in events
    assert events.index("abandon") < events.index("write")


# AT-11
def test_an_env_flag_error_in_run_exits_1(tmp_path: Path) -> None:
    errors = pytest.importorskip("decoy_engine.errors")
    cls = getattr(errors, "EnvFlagError", None)
    if cls is None:
        pytest.skip("the pinned engine has no EnvFlagError")
    exc = cls.__new__(cls)
    exc.code = "env_flag_bad"
    exc.message = "bad flag"
    result = _run(tmp_path, exc)

    assert result.exit_code == EXIT_USAGE


# AT-16 pipeline canary
@pytest.mark.parametrize("flags", [(), ("--quiet",), ("--json",)])
def test_a_generic_error_shows_the_type_not_the_text(tmp_path: Path, flags: tuple) -> None:
    result = _run(tmp_path, ValueError("ROWVALUE-CANARY-42"), *flags)

    assert result.exit_code == EXIT_RUNTIME
    assert "ROWVALUE-CANARY-42" not in result.stdout + result.stderr
    if "--json" in flags:
        assert _doc(result)["error"] == "run failed (ValueError)."
    else:
        assert "error: run failed (ValueError)." in result.stderr
        assert len(_hint_lines(result.stderr)) == 1


# AT-16 compile canary
@pytest.mark.parametrize("flags", [(), ("--quiet",), ("--json",)])
def test_a_compile_failure_shows_the_type_not_the_text(tmp_path: Path, flags: tuple) -> None:
    cfg = _config(tmp_path)
    with mock.patch("decoy_engine.plan.compile_plan", side_effect=ValueError("COMPILE-CANARY-42")):
        result = runner.invoke(app, ["run", str(cfg), *flags])

    assert result.exit_code == EXIT_USAGE, result.output
    assert "COMPILE-CANARY-42" not in result.stdout + result.stderr
    assert "compile failed (ValueError)." in result.stdout + result.stderr
    if "--json" in flags:
        doc = _doc(result)
        assert all("COMPILE-CANARY-42" not in json.dumps(m) for m in doc.get("messages", []))
