"""`decoy fit` -- fit a distribution snapshot from a source CSV.

Capability-gaps WS3 (2026-06-12). Wraps the engine's
`compute_distribution_snapshot` (distribution-snapshot/v2): the JSON it
writes is the fitted-model artifact that `type: statistical` generate
columns consume. The loop is:

    decoy fit source.csv --output snapshot.json
    # reference snapshot.json from generate_columns, then:
    decoy run generate.yaml

The snapshot is written through the engine's `distribution_snapshot_document`:
columns the sensitivity profile flags have their cell values withheld
(`value_policy: flagged-redacted/v2`, names in `redacted_columns`).
`--include-values` keeps them and stamps `value_policy: raw`. Unflagged
columns are floored at 10 rows (rare text labels fold into `other_count`, extremes
are top and bottom coded, true/false columns stay as they are); the labels kept
are still real source values, so statistical categorical columns require the
`allow_real_categories: true` opt-in at run time.

DPS-CLI rewire (docs/plans/2026-07-24-dps-cli-fit-rewire.md). `--epsilon`
now selects a second, disjoint mode that calls the engine's
`fit_dp_snapshot` (typed-carrier `dps-marginal/v3`), replacing the removed
`apply_dp_noise`. The two modes are kept from blurring by making every
DP-only option (`--delta`, `--dp-number`/`--dp-flag`/`--dp-text`,
`--dp-allow-omit`) a usage error when `--epsilon` is
absent -- otherwise an operator who declares carriers but forgets
`--epsilon` would silently fall through to the exact, non-DP snapshot (a
fail-open release of exact data).
"""

from __future__ import annotations

# The package re-binds every public name the old single-file `fit.py` bound, so named and
# wildcard imports from `decoy.cli.fit` behave as before. Only `fit` and `FIT_EPILOG` are
# the command's own; the rest are the old module's imports. The moved code looks each name
# up in `decoy.cli.fit._command`, so a patch must target that module, not this one.
import json as json
import math as math
from pathlib import Path as Path
from typing import Any as Any

import typer as typer

from decoy._atomic import AtomicWriteError as AtomicWriteError
from decoy._atomic import WriteMode as WriteMode
from decoy._atomic import describe as describe
from decoy._atomic import write_local_target as write_local_target
from decoy._resources import ResourceError as ResourceError
from decoy._resources import read_fit_max_rows as read_fit_max_rows
from decoy.cli.exit_codes import EXIT_RUNTIME as EXIT_RUNTIME
from decoy.cli.exit_codes import EXIT_USAGE as EXIT_USAGE
from decoy.cli.exit_codes import exit_code_for as exit_code_for
from decoy.cli.fit._command import FIT_EPILOG as FIT_EPILOG
from decoy.cli.fit._command import fit as fit
from decoy.cli.gen import FIT_SAMPLE_SEED as FIT_SAMPLE_SEED
from decoy.cli.gen import FitSourceError as FitSourceError
from decoy.cli.gen import fit_exact_snapshot as fit_exact_snapshot
from decoy.cli.gen import read_fit_csv as read_fit_csv
from decoy.cli.gen import strict_csv as strict_csv
from decoy.cli.io import side_file_default as side_file_default
from decoy.ui.output import OutputMode as OutputMode
from decoy.ui.output import emit_error as emit_error
from decoy.ui.output import emit_json as emit_json
from decoy.ui.output import setup_output as setup_output
from decoy.ui.theme import code as code
from decoy.ui.theme import hint as hint
from decoy.ui.theme import success as success
from decoy.ui.theme import warn as warn
