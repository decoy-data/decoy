"""The detectors a `decoy scan` runs: the `--detectors` and `--ner-model` options, the model
preflight, and the detector line and `--json` member.

SCAN-ML plan 4.7 (slice C2b). `--detectors regex,classifier,ner` sets the pre-scan sources and
`--ner-model NAME` the NER model, as the `pre_scan` block of a pipeline does. The engine owns
the rules (`PreScanConfig`: `regex` always on, no repeats, a model name only with `ner`); this
module maps its refusal to exit 1 with fixed text, so a typo is never echoed back.

A model that cannot run is found by `load_detectors` before the first table is read, and
refuses with exit 1, the reason code and the install hint (the engine run reuses the loaded
set from its per-process cache). Everything printed is source names, model ids and versions.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import typer

from decoy.cli.exit_codes import EXIT_USAGE
from decoy.cli.io import load_detector_set
from decoy.ui.output import OutputState, emit_error

DETECTORS_OPTION: Any = typer.Option(
    None,
    "--detectors",
    help=(
        "Detectors to run: a comma-separated list of regex, classifier and ner. regex always "
        "runs, so it must be in the list (default: regex). A model that cannot run here "
        "refuses before any row is read; see `decoy models list`."
    ),
)
NER_MODEL_OPTION: Any = typer.Option(
    None,
    "--ner-model",
    help="NER model package to use with --detectors ner (default: en_core_web_sm).",
)

_BAD_LIST = "--detectors must name regex, and may add classifier and ner, each once."
_BAD_MODEL = "--ner-model must be a plain package name."
_NEEDS_NER = "--ner-model needs ner in --detectors."


class DetectorsUsageError(Exception):
    """A bad `--detectors` or `--ner-model`, found before any file is read. Fixed text only."""


def resolve_pre_scan(detectors: str | None, ner_model: str | None) -> Any:
    """The engine `PreScanConfig` for the options, or None when they ask for regex only."""
    if detectors is None and ner_model is None:
        return None
    from decoy_engine import PreScanConfig
    from pydantic import ValidationError

    names = [n.strip() for n in (detectors or "regex").split(",")]
    kwargs: dict[str, Any] = {"detectors": tuple(names)}
    if ner_model is not None:
        kwargs["ner_model"] = ner_model
    problem: str | None = None
    config = None
    try:
        config = PreScanConfig(**kwargs)
    except ValidationError as exc:
        # `hide_input_in_errors` keeps the input out of the error; only its code is read.
        codes = " ".join(str(e.get("type", "")) for e in exc.errors())
        problem = (
            _NEEDS_NER
            if "pre_scan_ner_inactive" in codes
            else _BAD_MODEL
            if "ner_model" in codes
            else _BAD_LIST
        )
    if problem is not None:
        raise DetectorsUsageError(problem)
    return None if config.detectors == ("regex",) else config


def preflight(state: OutputState, where: Mapping[str, Any], pre_scan: Any) -> None:
    """Load the chosen models before the first table is read; exit 1 when one cannot run."""
    if pre_scan is None:
        return
    _, refused = load_detector_set(pre_scan.detectors, pre_scan.ner_model)
    if refused is None:
        return
    from decoy.cli.models import hint

    emit_error(
        state,
        "scan",
        f"the {refused.source} model {refused.model_id} cannot run here.",
        code=refused.reason,
        hint=hint(refused),
        context=where,
    )
    raise typer.Exit(code=EXIT_USAGE)


def detector_members(core: Mapping[str, Any]) -> list[dict[str, Any]]:
    """`--json` `detectors`: `[{source, model_id, model_version}]`, regex first."""
    out = []
    for run in core.get("detectors") or ():
        model = run.get("model") or {}
        out.append(
            {
                "source": run["source"],
                "model_id": model.get("id"),
                "model_version": model.get("version"),
            }
        )
    return out or [{"source": "regex", "model_id": None, "model_version": None}]


def detectors_line(members: list[dict[str, Any]]) -> str:
    """`regex; classifier lgbm-v1 0.1.0; ner en_core_web_sm 3.8.0`."""
    return "; ".join(
        " ".join(str(p) for p in (m["source"], m["model_id"], m["model_version"]) if p)
        for m in members
    )


def has_models(members: list[dict[str, Any]]) -> bool:
    return any(m["source"] != "regex" for m in members)
