"""The local record library: one store of value-free records per project (LIB plan, L1b, L1c).

Commands import this facade, never a `_` module (G-LIB-WRITER outside the package, and
`tests/unit/library/test_facade.py` for the command modules in it). What exists so far: the root
rule (`resolve_root`), the store (`open_library`, `Library.put`, `get`, `resolve`, `rows`,
`latest`), refs (`Library.set_ref`, `read_ref`, under the library lock), the index and degraded
mode, the retention policy model (`load_policy`), the error type, and the `library` command group
(`library_app`: `path`, `fsck`). Scratch and logs arrive in later slices. See docs/library.md.

Only `library_app` is imported eagerly; every other name loads on first use (PEP 562), so
registering the group keeps the record engine out of `decoy --help` and `--version`.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from decoy.cli.library._commands import library_app

if TYPE_CHECKING:
    from decoy.cli.library._diff import diff_payloads
    from decoy.cli.library._errors import USAGE_CODES, LibraryError
    from decoy.cli.library._exporting import check_destination, export_lines
    from decoy.cli.library._exporting import select as export_select
    from decoy.cli.library._fs import write_user_file
    from decoy.cli.library._fsck import check as fsck_check
    from decoy.cli.library._fsck import repair as fsck_repair
    from decoy.cli.library._fsck_codes import NEEDS_NEWER
    from decoy.cli.library._paths import LibraryRoot, check_root_budget, resolve_root
    from decoy.cli.library._policy import LibraryPolicy, load_policy
    from decoy.cli.library._prune import Rule as PruneRule
    from decoy.cli.library._prune import policy_rules, prune_apply, prune_preview
    from decoy.cli.library._resolve import TargetError, resolve_target
    from decoy.cli.library._scratch import clean_all, clean_preview
    from decoy.cli.library._store import Library, PutResult, open_library

__all__ = [
    "NEEDS_NEWER",
    "USAGE_CODES",
    "Library",
    "LibraryError",
    "LibraryPolicy",
    "LibraryRoot",
    "PruneRule",
    "PutResult",
    "TargetError",
    "check_destination",
    "check_root_budget",
    "clean_all",
    "clean_preview",
    "diff_payloads",
    "export_lines",
    "export_select",
    "fsck_check",
    "fsck_repair",
    "library_app",
    "load_policy",
    "open_library",
    "policy_rules",
    "prune_apply",
    "prune_preview",
    "resolve_root",
    "resolve_target",
    "write_user_file",
]

# Public name -> (module, attribute).
_LAZY = {
    "PruneRule": ("_prune", "Rule"),
    "check_destination": ("_exporting", "check_destination"),
    "clean_all": ("_scratch", "clean_all"),
    "clean_preview": ("_scratch", "clean_preview"),
    "export_lines": ("_exporting", "export_lines"),
    "export_select": ("_exporting", "select"),
    "policy_rules": ("_prune", "policy_rules"),
    "prune_apply": ("_prune", "prune_apply"),
    "prune_preview": ("_prune", "prune_preview"),
    "write_user_file": ("_fs", "write_user_file"),
    "NEEDS_NEWER": ("_fsck_codes", "NEEDS_NEWER"),
    "USAGE_CODES": ("_errors", "USAGE_CODES"),
    "TargetError": ("_resolve", "TargetError"),
    "diff_payloads": ("_diff", "diff_payloads"),
    "resolve_target": ("_resolve", "resolve_target"),
    "Library": ("_store", "Library"),
    "LibraryError": ("_errors", "LibraryError"),
    "LibraryPolicy": ("_policy", "LibraryPolicy"),
    "LibraryRoot": ("_paths", "LibraryRoot"),
    "PutResult": ("_store", "PutResult"),
    "check_root_budget": ("_paths", "check_root_budget"),
    "fsck_check": ("_fsck", "check"),
    "fsck_repair": ("_fsck", "repair"),
    "load_policy": ("_policy", "load_policy"),
    "open_library": ("_store", "open_library"),
    "resolve_root": ("_paths", "resolve_root"),
}


def __getattr__(name: str) -> Any:
    found = _LAZY.get(name)
    if found is None:
        raise AttributeError(name)
    module, attribute = found
    return getattr(importlib.import_module(f"decoy.cli.library.{module}"), attribute)
