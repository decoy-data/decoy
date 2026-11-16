"""The fixed `models.*` codes and texts of `decoy models`, and the one error that carries them.

Messages are fixed text plus names, versions and integer exit codes. Nothing an installer printed,
no index URL and no user path goes in one: configured index URLs can hold credentials.
"""

from __future__ import annotations

from typing import Any

from decoy.cli.exit_codes import EXIT_RUNTIME, EXIT_USAGE

INSTALL_FAILED = "models.install_failed"
MODEL_UNPINNED = "models.model_unpinned"
SOURCE_INVALID = "models.source_invalid"
ENV_CHANGED = "models.env_changed"
MANAGED_RUNTIME = "models.managed_runtime"
PIP_MISSING = "models.pip_missing"

DP_NOTE = (
    "Installing NER adds packages to this environment, so DP fits here refuse as uncertified "
    "(dp_stack_uncertified); keep NER in a separate environment if you need both."
)

CODES = (INSTALL_FAILED, MODEL_UNPINNED, SOURCE_INVALID, ENV_CHANGED, MANAGED_RUNTIME, PIP_MISSING)
_RUNTIME = frozenset({INSTALL_FAILED, ENV_CHANGED})


class ModelsError(Exception):
    """A refused or failed model install. Always raised outside any `except` block."""

    def __init__(
        self,
        code: str | None,
        message: str,
        *,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.context = context or {}
        self.exit_code = EXIT_RUNTIME if code in _RUNTIME else EXIT_USAGE
