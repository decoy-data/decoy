"""The one registry of banned user text.

Two lists, each with its scope:

* `DEAD_STRINGS`: invocation strings of deleted commands. Scope: every line of every
  `src/decoy/**/*.py` file, comments and docstrings included (checked by
  `tests/unit/test_no_dead_command_strings.py`).
* `BANNED_USER_TEXT`: internal names a user must never read (ticket ids, private module
  paths, hidden command names). Scope: text a user can see, namely command help, usage lines,
  `explain` topics, string constants outside docstrings, and bundled templates (checked by
  `tests/sentry/cli_text/test_user_text_internal_names.py`). Comments and docstrings keep their
  ids because no user reads them.

An allowlist entry is keyed by (file, the exact full string constant, the one banned pattern it
is exempt from, the AST context it sits in) and carries the expected site count and the reason it
is not user text. A string that merely contains the
exempt text, or that also trips a different pattern, still fails.
"""

from __future__ import annotations

import re
from typing import Any

from tests.sentry._ratchet import load_allowlist
from tests.sentry.release.test_retired_name_residual import RETIRED_PATTERN

DEAD_STRINGS = (
    # S2: top-level commands removed / re-parented. The space is load-bearing:
    # it keeps `decoy validate preflight` and `decoy validate compile` (the
    # live forms) from matching `decoy preflight` / `decoy compile`.
    "decoy compile",
    "decoy plan",
    "decoy preflight",
    # S3a: `profile` and the old analyze command merged into `decoy scan`; the saved-scan
    # subcommands moved from the old group to `scan`. The old group's own invocation
    # strings are covered by the retired-name pattern in `BANNED_USER_TEXT` and the
    # residual sentry, so only `decoy profile` is listed here.
    "decoy profile",
    # S3b: the `strategies`/`providers`/`checksums`/`validators` sub-apps and the
    # `templates` sub-app folded into `decoy list KIND` / `decoy show KIND`. The
    # removed top-level invocation strings are dead. `decoy templates` catches
    # both `templates list` and `templates show`; it does NOT match the live
    # `decoy list templates` / `decoy show template` forms (no "decoy templates"
    # substring in either).
    "decoy strategies",
    "decoy providers",
    "decoy checksums",
    "decoy validators",
    "decoy templates",
    # S4a: the project/catalog/jobs persistence subsystem was deleted and the
    # CLI is now stateless. The trailing space keeps `decoy report ...` (the
    # live post-run surface) from matching; neither of these has a surviving
    # `decoy ...` form. (`decoy project` came back as the layout group in P6.)
    "decoy catalog",
    "decoy jobs",
    # S4b: the `evidence` and `vault` groups, the old scan group and `validate
    # distribution` folded into `decoy report` (verify+show / vault / integrity
    # / fidelity). The live forms are `decoy report ...`, which none of these
    # substrings match. `validate distribution` (the exact nested path) is
    # dead; `decoy evidence` / `decoy vault` catch every invocation of those
    # removed groups.
    "decoy evidence",
    "decoy vault",
    "validate distribution",
)

_SCAN_PATTERN = r"(?<!\w)_scan\b"
_GATE_PATTERN = r"(?<!\w)_gate\b"

_USER_TEXT_PATTERNS = (
    r"OSS\.\d",
    r"FC-\d",
    r"CLI\.\d",
    r"DE-\d",
    r"SP-\d",
    r"\bS\d+-[A-Z]",
    r"decoy-platform/",
    r"decoy_engine\.\w+\._",
    _SCAN_PATTERN,
    _GATE_PATTERN,
    r"\b\w+\.py:\d+",
    r"\bBF\d+\b",
    r"the platform's",
)

# The retired product name is the one object the residual sentry owns, so it is spelled once.
BANNED_USER_TEXT = (*(re.compile(p) for p in _USER_TEXT_PATTERNS), RETIRED_PATTERN)

# Where an exempt literal sits in the AST. Anything else with the same text is user text.
CTX_GROUP_ARG = "make_default_group-arg"  # first positional argument of make_default_group(...)
CTX_NAME_KWARG = "name-kwarg"  # value of a `name=` keyword argument in a call

# (path under src/decoy, exact full string constant, pattern source it is exempt from, AST
# context) -> (number of sites expected, reason it is not user text). Matching is
# `text == exact` in that context, only that one pattern is skipped, and the number of exempted
# sites must equal the expected count, so a new literal of the same text fails the sentry. The
# entries live in `baselines/banned-text-allow.json` (key `path::exact::context`, `count`, the
# name of the `pattern` constant, `reason`) so the ratchet lets them only shrink.
_PATTERNS = {"_SCAN_PATTERN": _SCAN_PATTERN, "_GATE_PATTERN": _GATE_PATTERN}


def _allow_entry(
    key: str, entry: dict[str, Any]
) -> tuple[tuple[str, str, str, str], tuple[int, str]]:
    rel, exact, ctx = key.split("::")
    return (rel, exact, _PATTERNS[entry["pattern"]], ctx), (entry["count"], entry["reason"])


ALLOWLIST: dict[tuple[str, str, str, str], tuple[int, str]] = dict(
    _allow_entry(key, e) for key, e in load_allowlist("banned-text-allow").items()
)
