"""Acyclic leaf for the install refusal shared by `installer`, `trust_state` and the key
rotation code. It imports nothing from this package, so the modules that raise it can import
each other without a cycle. `installer` re-exports `InstallError` for existing callers."""

from __future__ import annotations


class InstallError(RuntimeError):
    """A hard refusal: a failed verification or a broken bundle. The managed runtime is
    left exactly as it was (or rolled back)."""
