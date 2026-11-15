"""REL-GATE RG-F2: `decoy.mask` and `decoy.scan` are public API, so their signatures are frozen."""

from __future__ import annotations

import inspect

import decoy


def _signature(fn) -> list[tuple[str, str, object]]:
    return [(p.name, p.kind.name, p.default) for p in inspect.signature(fn).parameters.values()]


def test_mask_signature_is_frozen() -> None:
    assert _signature(decoy.mask) == [
        ("data", "POSITIONAL_OR_KEYWORD", None),
        ("config", "POSITIONAL_OR_KEYWORD", None),
        ("mask_secret", "KEYWORD_ONLY", None),
        ("master_key", "KEYWORD_ONLY", None),
        ("key_label", "KEYWORD_ONLY", None),
        ("out", "KEYWORD_ONLY", None),
        ("native", "KEYWORD_ONLY", None),
    ]


def test_scan_signature_is_frozen() -> None:
    empty = inspect.Parameter.empty
    assert _signature(decoy.scan) == [
        ("data", "POSITIONAL_OR_KEYWORD", empty),
        ("source_label", "KEYWORD_ONLY", None),
        ("rows", "KEYWORD_ONLY", None),
        ("strategy", "KEYWORD_ONLY", "head"),
        ("format", "KEYWORD_ONLY", None),
        ("layout", "KEYWORD_ONLY", None),
    ]
