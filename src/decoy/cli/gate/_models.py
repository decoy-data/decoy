"""The gate's model availability preflight: a `post_scan` model that cannot run here is an error.

Plan 4.1 matrix: `decoy validate` and `decoy ci check` check the `post_scan` models only (a
`pre_scan` model is the scan's to refuse). The status comes from the engine's one probe per
model (`classifier_status`, `ner_status`), never a load, so validating reads no source row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from decoy.cli.gate._layers import GateFinding

if TYPE_CHECKING:
    from decoy_engine import ModelStatus

_LOCATION = "post_scan.detectors"


def post_scan_model_findings(config: dict[str, Any]) -> list[GateFinding]:
    """One preflight error per `post_scan` model that is not available, with its fix."""
    from decoy_engine import classifier_status, ner_status
    from decoy_engine.detection.ner import DEFAULT_NER_MODEL

    post = config.get("post_scan") or {}
    detectors = post.get("detectors") or ()
    statuses = []
    if "classifier" in detectors:
        statuses.append(classifier_status())
    if "ner" in detectors:
        statuses.append(ner_status(post.get("ner_model") or DEFAULT_NER_MODEL))
    return [model_finding(status) for status in statuses if not status.available]


def model_finding(status: ModelStatus) -> GateFinding:
    """The preflight error for one `post_scan` model that cannot run, with its fix. `decoy run`
    builds the same finding when `load_detectors` refuses a model the probe passed."""
    from decoy.cli.models import hint

    reason = status.reason or ""
    cause = f", cause: {status.cause}" if status.cause else ""
    message = (
        f"post_scan asks for the {status.source} model {status.model_id or '(invalid name)'}, "
        f"which cannot run here ({reason}{cause}); {hint(status)}"
    )
    return GateFinding(
        "preflight",
        "error",
        reason.rpartition(".")[2],
        message,
        _LOCATION,
        logical_path=_LOCATION,
        extra="ner" if status.source == "ner" else None,
    )
