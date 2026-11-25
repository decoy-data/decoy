"""AT-C1l flag cells, AT-C1f and the `--native` decline cells on a plain single-table run.

Parity cells compare the lazy run with the base resident run: exit, route and every file the
run places (targets and the quarantine file).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.e2e.run_stream._support import (
    PLAIN,
    install_probe,
    run_both,
    single_build,
    write_config,
)
from tests.keyed_secret import TEST_MASK_SECRET_REF, secret_env


@pytest.fixture(autouse=True)
def _secret(monkeypatch: pytest.MonkeyPatch) -> None:
    for var, value in secret_env().items():
        monkeypatch.setenv(var, value)


def _same(lazy: Any, base: Any) -> None:
    assert lazy.exit_code == base.exit_code, (lazy.output, base.output)
    assert lazy.route == base.route
    assert lazy.files == base.files


@pytest.mark.parametrize(
    "flag", ["--explain-plan", "--fidelity", "--post-validate", "--post-validate-enforce"]
)
def test_report_flag_parity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
    lazy, base, _ = run_both(
        monkeypatch, tmp_path, single_build(tmp_path, columns=PLAIN), args=(flag,)
    )
    assert lazy.exit_code == 0, lazy.output
    _same(lazy, base)


def test_quarantine_parity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cols = [{"name": "id", "strategy": "passthrough"}, {"name": "email", "strategy": "passthrough"}]
    single = single_build(tmp_path, columns=cols)

    def build(out: Path) -> tuple[Path, list[Path]]:
        # Rows whose email does not start `user1` fail the validator and go to quarantine.
        config, targets = single(out)
        import yaml

        cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
        cfg["validators"] = [
            {
                "name": "regex_match",
                "columns": {"people": ["email"]},
                "params": {"pattern": "^user1"},
            }
        ]
        cfg["quarantine"] = {
            "enabled": True,
            "output_path": str(out / "q.jsonl"),
            "triggers": ["validation_fail"],
        }
        return write_config(config, cfg), [*targets, out / "q.jsonl"]

    lazy, base, _ = run_both(monkeypatch, tmp_path, build)
    _same(lazy, base)
    assert lazy.exit_code == 0, lazy.output
    assert "q.jsonl" in lazy.files


def test_targetless_table_parity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A table with no target is consumed and counted, never written."""
    import yaml

    from tests.e2e.run_stream._support import fk_build

    inner = fk_build(tmp_path, rows=100)

    def build(out: Path) -> tuple[Path, list[Path]]:
        config, _ = inner(out)
        cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
        del cfg["targets"]["b"]
        return write_config(config, cfg), [out / "a.csv", out / "b.csv"]

    lazy, base, _ = run_both(monkeypatch, tmp_path, build)
    assert lazy.exit_code == 0, lazy.output
    _same(lazy, base)
    assert set(lazy.files) == {"a.csv"}


def _fixed_width_build(tmp: Path) -> Any:
    from tests.csv_sources import file_source

    path = tmp / "data" / "f.dat"
    path.parent.mkdir(exist_ok=True)
    path.write_text(
        "".join(f"{i:<6}{f'user{i}@example.invalid':<40}\n" for i in range(3000)), "utf-8"
    )
    layout = {
        "columns": [
            {"name": "id", "start": 0, "width": 6},
            {"name": "email", "start": 6, "width": 40},
        ]
    }

    def build(out: Path) -> tuple[Path, list[Path]]:
        cfg = {
            "version": 2,
            "global_settings": {"seed": 5, "mask_secret_ref": TEST_MASK_SECRET_REF},
            "sources": {"people": file_source(path, "fixed_width", layout=layout)},
            "tables": [{"name": "people", "columns": PLAIN}],
            "targets": {
                "people": {"type": "file", "format": "csv", "path": str(out / "people.csv")}
            },
        }
        return write_config(out / "p.yaml", cfg), [out / "people.csv"]

    return build, path


@pytest.mark.parametrize("fmt", ["parquet", "fixed_width"])
def test_file_changed_after_the_facts_pass_exits_3_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """AT-C1f and AT-C1w: the source is replaced after routing read its facts and before the
    first batch. The run fails with `runtime.lazy_source_changed` and publishes nothing."""
    from decoy_engine.profile import FixedWidthLazySource, LazySource

    install_probe(monkeypatch, chunk_rows=500)  # small chunks put the run on the streamed lane
    if fmt == "parquet":
        build = single_build(tmp_path, columns=PLAIN)
        source = tmp_path / "data" / "people.parquet"
        cls: Any = LazySource

        def replace() -> None:
            pq.write_table(pa.table({"id": [1], "email": ["x@example.invalid"]}), source)

    else:
        build, source = _fixed_width_build(tmp_path)
        cls = FixedWidthLazySource

        def replace() -> None:
            source.write_text("1     x@example.invalid" + " " * 21 + "\n", encoding="utf-8")

    out = tmp_path / "run"
    out.mkdir()
    config, targets = build(out)
    real = cls.open_batches
    swapped: list[bool] = []

    def swap_then_open(self: Any, *args: Any, **kwargs: Any) -> Any:
        if not swapped:
            swapped.append(True)
            replace()
        return real(self, *args, **kwargs)

    monkeypatch.setattr(cls, "open_batches", swap_then_open)
    result = CliRunner().invoke(app, ["run", str(config), "--json"])
    assert swapped, result.output[-700:]
    assert result.exit_code == 3, result.output
    assert '"namespace": "runtime", "code": "lazy_source_changed"' in result.output
    assert not targets[0].exists()
    assert "x@example.invalid" not in result.output


_COMPANION = importlib.util.find_spec("decoy_engine_native") is not None


@pytest.mark.skipif(not _COMPANION, reason="needs a real compiled decoy-engine-native companion")
def test_native_decline_refuses_with_no_output(tmp_path: Path) -> None:
    # No column the companion can plan: nothing compiled runs, so --native has no evidence.
    columns = [{"name": "id", "strategy": "passthrough"}, {"name": "email", "strategy": "redact"}]
    build = single_build(tmp_path, columns=columns)
    out = tmp_path / "run"
    out.mkdir()
    config, targets = build(out)
    result = CliRunner().invoke(app, ["run", str(config), "--native", "--json"])
    assert result.exit_code != 0, result.output
    assert "no output was written" in " ".join(result.output.split())
    assert not targets[0].exists()
    doc = json.loads(result.stdout) if result.stdout.strip().startswith("{") else {}
    assert doc.get("code", "native_require_no_evidence") == "native_require_no_evidence"


@pytest.mark.skipif(not _COMPANION, reason="needs a real compiled decoy-engine-native companion")
def test_native_require_accepts_faker_column_on_engine_0_28_4(tmp_path: Path) -> None:
    """Engine 0.28.4 plans `person_email` natively, so a faker column beside a passthrough one
    gives --native its evidence (0.28.3 declined it and the run was refused)."""
    columns = [
        {"name": "id", "strategy": "passthrough"},
        {"name": "email", "strategy": "faker", "provider": "person_email"},
    ]
    build = single_build(tmp_path, columns=columns)
    out = tmp_path / "run"
    out.mkdir()
    config, targets = build(out)
    result = CliRunner().invoke(app, ["run", str(config), "--native", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["native_route"]["state"] == "native"
    assert payload["native_route"]["label"] == "native (compiled kernel)"
    assert targets[0].exists()
    assert len(targets[0].read_text(encoding="utf-8").splitlines()) > 1


def test_empty_fixed_width_file_keeps_its_layout_schema_in_a_parquet_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AT-C1w: with no record the lazy source reports the layout schema, so an `int` field is
    `int64`; the resident read of the same empty file gave `null`. The layout wins (CHANGELOG)."""
    from tests.csv_sources import file_source

    path = tmp_path / "data" / "e.dat"
    path.parent.mkdir()
    path.write_text("", encoding="utf-8")
    layout = {
        "columns": [
            {"name": "i", "start": 0, "width": 4, "type": "int", "align": "right"},
            {"name": "s", "start": 4, "width": 6},
        ]
    }

    def build(out: Path) -> tuple[Path, list[Path]]:
        cfg = {
            "version": 2,
            "global_settings": {"seed": 1},
            "sources": {"t": file_source(path, "fixed_width", layout=layout)},
            "tables": [
                {
                    "name": "t",
                    "columns": [
                        {"name": "i", "strategy": "passthrough"},
                        {"name": "s", "strategy": "passthrough"},
                    ],
                }
            ],
            "targets": {"t": {"type": "file", "format": "parquet", "path": str(out / "t.parquet")}},
        }
        return write_config(out / "p.yaml", cfg), [out / "t.parquet"]

    lazy, base, _ = run_both(monkeypatch, tmp_path, build)
    assert lazy.exit_code == 0, lazy.output
    assert base.exit_code == 0, base.output

    def schema(run: Any) -> pa.Schema:
        return pq.read_schema(pa.BufferReader(run.files["t.parquet"]))

    assert schema(lazy).field("i").type == pa.int64()
    assert schema(base).field("i").type == pa.null()
    # Engine 0.28.4 (#770) writes an untouched column as the source holds it, a zero-row column
    # included. The resident read of the empty file holds every column as `null`, so `s` is
    # `null` there, as it was on 0.28.3 (engine #791 fixes that reader). The lazy source reports
    # the declared layout, so `s` is `string` on this route only.
    assert schema(lazy).field("s").type == pa.string()
    assert schema(base).field("s").type == pa.null()
