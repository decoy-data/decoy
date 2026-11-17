"""The models section of `decoy setup`: offer the NER install. It stores nothing in settings.json.

It runs the same install as `decoy models install ner` (`install_ner`), so the two cannot drift.
The engine loads inside `run`, never at import (see `decoy.cli.models`).
"""

from __future__ import annotations

from typing import Any

from decoy.cli.models import DP_NOTE, plan_lines
from decoy.cli.setup._step import Prompter, SetupAnswers


class ModelsSection:
    name = "models"
    title = "Models"

    def status(self) -> list[dict[str, Any]]:
        from decoy.cli.models import model_rows

        return model_rows()

    def run(self, prompter: Prompter, answers: SetupAnswers) -> dict[str, Any]:
        if answers.ner == "skip":
            return {"ner": "skipped"}
        asked = False
        if answers.ner != "install":
            if answers.yes:
                return {"ner": "skipped"}  # `--yes` never installs packages unasked
            ner = self.status()[1]
            if ner["available"]:
                prompter.say(f"NER: {ner['model_id']} {ner['version']} is installed.")
                return {"ner": "already_installed", "model": _ref(ner["model_id"], ner["version"])}
            prompter.say(f"NER is not installed. {DP_NOTE}")
            if not prompter.confirm("Install spaCy and the NER model now?"):
                return {"ner": "skipped"}
            asked = True

        from decoy_engine.detection.ner import DEFAULT_NER_MODEL

        from decoy.cli.models import install_ner

        def confirm(plan: Any) -> bool:
            for line in plan_lines(plan):
                prompter.say(line)
            return answers.yes or asked or prompter.confirm("Install these packages?")

        result = install_ner(
            model=DEFAULT_NER_MODEL, source=answers.ner_from, confirm=confirm, progress=prompter.say
        )
        return {
            "ner": "already_installed" if result.already_installed else "installed",
            "model": _ref(result.model, result.version),
            "installed": list(result.installed),
        }


def _ref(model_id: str, version: str | None) -> dict[str, Any]:
    return {"id": model_id, "version": version}
