"""`decoy validate preflight` -- local file, source, and schema readiness checks (SP-17).

`preflight` helps catch common problems BEFORE running a pipeline. It performs
local checks that do not require the engine to execute the full pipeline.

What preflight checks (honest framing)
--------------------------------------
1. YAML syntax, schema and profile-free config logic.
2. Project-layout output paths (the same refusals as `decoy validate`).
3. Source file existence and readability.
4. Existing output targets (advisory).
5. Out-of-core-FK capacity and generated-output floor (hard refusals exit EXIT_CAPACITY).
6. Native companion health and static config-shape eligibility.

What preflight does NOT check
------------------------------
* Platform preflight conditions such as secrets, RBAC, schedules, and network targets.
* Engine run-time constraints beyond the out-of-core-FK capacity check above
  (provider capacity, null-bearing integer distributions) -- these require a
  profile pass during the run.
* Vault or secret access, network connectivity, or successful engine execution.

OOM checker v1 (docs/plans/2026-07-24-oom-checker-cli-v1.md): the capacity
check is an "OOC-FK engine-gate capacity checker", NOT a whole-job OOM
guarantee. `decoy run` fully loads every source into memory BEFORE it calls
the engine, so an ingestion `MemoryError` or OS OOM-kill happens before this
gate ever runs -- this check does not cover that. A "capacity: OK" here means
only that no hard impossibility was found. The build-floor estimate is
ADVISORY: when the predicted relation-build floor exceeds its cap, the check
reports a WARNING with a recommended size and the job still proceeds
(`--fail-on-warning` turns that warning into a nonzero exit). Two hard
capacity refusals exit EXIT_CAPACITY: a fan-in impossibility (more co-live
DuckDB joiners than the budget can seat), and generate tables whose resident
output cannot fit the machine's memory (`generation_budget_exceeded`, GEN-STRICT
row 24k). A config with a non-file source skips the estimate, so a generate floor
refusal exits 5 only at `decoy run`. A missing or unreadable source file
fails first (exit 1), so the exit 5 needs readable sources.

Do NOT describe the output of this command as "platform parity." Preflight
here is a local file/source/schema readiness gate. The spec (cli-first-
capability-guide.md lines 99-100) is explicit: frame this as FILE / SOURCE /
SCHEMA checks. Platform preflight is a different product.

The same engine primitives (PipelineConfig.model_validate,
run_config_only_checks) are used for steps 1-3; this keeps both commands
in sync on what "structurally valid" means without literally reusing the
validate command's code path.
"""

from __future__ import annotations

from decoy.cli.preflight._command import PREFLIGHT_EPILOG, preflight
from decoy.cli.preflight._result import CAPACITY_CHECK, PLAN_UNCOMPILABLE_CHECK

__all__ = ["CAPACITY_CHECK", "PLAN_UNCOMPILABLE_CHECK", "PREFLIGHT_EPILOG", "preflight"]
