"""How the CLI words an engine vault refusal: one table from the reason code to the hint.

`decoy unmask` and `decoy report vault` both open vaults and both refuse the same ways, so the
hints live here once. The text is the engine's own message, which names no path, key or value.
"""

from __future__ import annotations

_SECRET_HINT = (
    "use the mask secret (--mask-secret or global_settings.mask_secret_ref) "
    "of the `decoy run --vault` call that wrote this vault."
)


def is_vault_code(code: object) -> bool:
    """True for an engine vault reason code (`vault_tampered`, `vault_key_mismatch`, ...)."""
    return isinstance(code, str) and code.startswith("vault_")


def vault_hint(code: str) -> str | None:
    """The remedy for a vault refusal, or None when the engine message says enough."""
    from decoy_engine import reasons

    runtime = reasons.runtime
    if code == runtime.VAULT_TAMPERED:
        return "the vault was changed or damaged after it was written; do not use it."
    if code == runtime.VAULT_PROTOCOL_VERSION_MISMATCH:
        return (
            "the vault was written under a different engine protocol version; "
            "re-mask under the current engine, or use the engine version that wrote the vault."
        )
    if code == runtime.VAULT_KEY_MISMATCH:
        return _SECRET_HINT
    if code == runtime.VAULT_FORMAT_UNSUPPORTED:
        return "re-mask with `decoy run --vault` to write a vault this engine reads."
    return None
