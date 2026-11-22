"""The CLI's vault refusal classifier and hints track the engine's refusal registry."""

from __future__ import annotations

import pytest
from decoy_engine import reasons
from decoy_engine.vault import VAULT_REFUSAL_CODES

from decoy.cli.reports import is_vault_code, vault_hint

_HINTED = (
    reasons.runtime.VAULT_TAMPERED,
    reasons.runtime.VAULT_PROTOCOL_VERSION_MISMATCH,
    reasons.runtime.VAULT_KEY_MISMATCH,
    reasons.runtime.VAULT_FORMAT_UNSUPPORTED,
)


@pytest.mark.parametrize("code", sorted(VAULT_REFUSAL_CODES))
def test_every_registry_code_is_a_vault_code(code: str) -> None:
    assert is_vault_code(code)


@pytest.mark.parametrize("code", ["vault_not_a_real_code", "run_failed", "", None, 7])
def test_codes_outside_the_registry_are_refused(code: object) -> None:
    assert not is_vault_code(code)


def test_hints_exist_only_for_registry_codes() -> None:
    for code in _HINTED:
        assert code in VAULT_REFUSAL_CODES
        assert vault_hint(code)
    for code in sorted(VAULT_REFUSAL_CODES - set(_HINTED)):
        assert vault_hint(code) is None
    assert vault_hint("vault_not_a_real_code") is None
