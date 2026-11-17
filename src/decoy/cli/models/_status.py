"""What `decoy models list` and `decoy doctor` say about the two models and DP certification.

Every row comes from the engine's one status probe per model (`classifier_status`, `ner_status`);
nothing here probes on its own. Rows carry ids, versions, reason identities and fixed hints only.
"""

from __future__ import annotations

from typing import Any

from decoy_engine import ModelStatus, classifier_status, ner_status
from decoy_engine.detection.ner import DEFAULT_NER_MODEL

from decoy.cli.extras import install_line

_CLASSIFIER_HINTS = {
    "disabled": "unset DECOY_ML_DISABLED to use the classifier.",
    "import": "lightgbm or scikit-learn does not import here; on macOS run `brew install libomp`.",
}
_PACK_HINT = "the bundled classifier pack did not load; reinstall Decoy."


def install_command_text(model: str = DEFAULT_NER_MODEL) -> str:
    suffix = "" if model == DEFAULT_NER_MODEL else f" --model {model}"
    return f"{install_line('ner')}{suffix}"  # the one text, shared with the missing-extra hints


def hint(status: ModelStatus) -> str | None:
    """The one fix line for an unavailable model, read by list, doctor and the gate."""
    if status.available:
        return None
    if status.source == "classifier":
        return _CLASSIFIER_HINTS.get(status.cause or "", _PACK_HINT)
    return f"run `{install_command_text(status.model_id or DEFAULT_NER_MODEL)}`."


def row(status: ModelStatus) -> dict[str, Any]:
    return {
        "source": status.source,
        "model_id": status.model_id,
        "available": status.available,
        "version": status.version,
        "runtime_version": status.runtime_version,
        "reason": status.reason,
        "cause": status.cause,
        "hint": hint(status),
    }


def model_rows(ner_model: str = DEFAULT_NER_MODEL) -> list[dict[str, Any]]:
    return [row(classifier_status()), row(ner_status(ner_model))]


def describe(r: dict[str, Any]) -> str:
    """One line: `ner  en_core_web_sm  available  3.8.0 (runtime 3.8.18)` or the reason.

    No square brackets: `decoy doctor` prints notes through Rich markup.
    """
    head = f"{r['source']}  {r['model_id'] or '-'}  "
    if r["available"]:
        return head + f"available  {r['version']} (runtime {r['runtime_version']})"
    cause = f", cause {r['cause']}" if r["cause"] else ""
    return head + f"not available ({r['reason']}{cause})"


def dp_certified() -> tuple[bool, str | None]:
    """Whether a real DP fit may run here, and the refusal code when not."""
    from decoy_engine.quality.dp_provenance import ProvenanceError, check_fit_environment

    code: str | None = None
    try:
        check_fit_environment()
    except ProvenanceError as exc:
        code = str(exc.code)
    return code is None, code


def doctor_rows() -> list[dict[str, Any]]:
    """`decoy doctor` rows: one per model, then whether this environment is a certified DP row."""
    rows = []
    for r in model_rows():
        note = describe(r) + (f"; {r['hint']}" if r["hint"] else "")
        status = "pass" if r["available"] else "warn"
        rows.append(
            {"name": f"model:{r['source']}", "kind": "soft", "status": status, "note": note}
        )
    certified, code = dp_certified()
    where = "certified DP row" if certified else f"not a certified DP row ({code})"
    note = f"{where}; installing NER takes an environment off its certified row"
    rows.append(
        {
            "name": "dp-certified",
            "kind": "soft",
            "status": "pass" if certified else "warn",
            "note": note,
        }
    )
    return rows
