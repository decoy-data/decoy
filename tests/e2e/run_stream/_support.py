"""Shared harness for the C1l acceptance cells: run the CLI lazy and resident, compare.

`run_both` runs one config twice through the CLI: as shipped (lazy candidates plus
`resident_fallback=True`) and with the candidate builder turned off (the base resident run).
Each run records the engine route, the exit code and every target file's bytes. A `Probe`
wraps the engine seams the plan names (AT-C1l): the two `materialize_source` bindings, and the
batch yields of a lazy Parquet read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml
from decoy_engine.profile import LazySource
from decoy_engine.profile._readers import OpenedLazyBatches
from typer.testing import CliRunner

from decoy.__main__ import app

runner = CliRunner()


@dataclass
class Outcome:
    exit_code: int
    output: str
    route: str | None
    files: dict[str, bytes]
    sources: dict[str, Any] = field(default_factory=dict)
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Probe:
    """What the engine seams saw during one run."""

    prepass_reads: list[type] = field(default_factory=list)
    route_reads: list[type] = field(default_factory=list)
    batches: int = 0

    @property
    def lazy_materialized(self) -> bool:
        return any(issubclass(t, LazySource) for t in self.route_reads)


def install_probe(monkeypatch: pytest.MonkeyPatch, *, chunk_rows: int | None = None) -> Probe:
    """Count whole-source reads at both engine bindings and batch yields of a lazy read.

    `chunk_rows` forces a small chunk and a zero auto-chunk threshold on the `run_pipeline`
    call so a small file spans several batches.
    """
    probe = Probe()
    import decoy_engine
    from decoy_engine.execution import _pipeline_sources
    from decoy_engine.execution.pipeline import _lazy_input

    real_pre = _lazy_input.materialize_source
    real_route = _pipeline_sources.materialize_source

    def pre(value: Any) -> Any:
        probe.prepass_reads.append(type(value))
        return real_pre(value)

    def route(value: Any) -> Any:
        probe.route_reads.append(type(value))
        return real_route(value)

    monkeypatch.setattr(_lazy_input, "materialize_source", pre)
    monkeypatch.setattr(_pipeline_sources, "materialize_source", route)

    real_iter = OpenedLazyBatches._read

    def counted(self: Any, *args: Any, **kwargs: Any) -> Any:
        for batch in real_iter(self, *args, **kwargs):
            probe.batches += 1
            yield batch

    monkeypatch.setattr(OpenedLazyBatches, "_read", counted)

    if chunk_rows is not None:
        real_run = decoy_engine.run_pipeline

        def small(config: Any, sources: Any, **kwargs: Any) -> Any:
            kwargs.update(chunk_size_rows=chunk_rows, auto_chunk_threshold_rows=1)
            return real_run(config, sources, **kwargs)

        monkeypatch.setattr(decoy_engine, "run_pipeline", small)
    return probe


def run_both(
    monkeypatch: pytest.MonkeyPatch,
    tmp: Path,
    build: Any,
    *,
    args: tuple[str, ...] = (),
    probe: Probe | None = None,
) -> tuple[Outcome, Outcome, Probe | None]:
    """Run `build(out_dir)` (returns config path and target paths) lazy, then resident.

    A `{out}` in `args` becomes that run's output folder. The probe, when given, is snapshotted after the lazy run and reset for the resident one.
    """
    import decoy_engine
    from decoy_engine import route_summary

    seen: dict[str, Any] = {}
    real = decoy_engine.run_pipeline

    def spy(cfg: Any, sources: Any, **kwargs: Any) -> Any:
        seen["sources"] = dict(sources)
        seen["kwargs"] = kwargs
        result = real(cfg, sources, **kwargs)
        seen["route"] = route_summary(result.quality_metrics).route
        return result

    monkeypatch.setattr(decoy_engine, "run_pipeline", spy)
    outcomes: list[Outcome] = []
    snapshot: Probe | None = None
    for label in ("lazy", "base"):
        seen.clear()
        out = tmp / label
        out.mkdir()
        config, targets = build(out)
        if label == "base":
            monkeypatch.setattr("decoy.cli.run._execute.lazy_sources", lambda c, b: {})
            if probe is not None:
                snapshot = Probe(list(probe.prepass_reads), list(probe.route_reads), probe.batches)
        run_args = [a.replace("{out}", str(out)) for a in args]
        result = runner.invoke(app, ["run", str(config), *run_args])
        outcomes.append(
            Outcome(
                result.exit_code,
                result.output,
                seen.get("route"),
                {t.name: t.read_bytes() for t in targets if t.exists()},
                dict(seen.get("sources", {})),
                dict(seen.get("kwargs", {})),
            )
        )
    return outcomes[0], outcomes[1], snapshot


def write_config(path: Path, cfg: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path
