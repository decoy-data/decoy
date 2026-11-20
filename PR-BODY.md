## Summary

Removes the hidden `decoy demo --ref` and `--rows` flags (FREEZE-SURFACE S2, audit C16). Both only printed that the 3-table demo was deferred and exited 1. They now exit 2 as unknown options. Also deleted: `_generate_ref_datasets`, `_run_ref_demo`, the FK name and value tables only they used, their rows in the io_policy sink table and the one-error-emitter baseline. `docs/release/frozen-surfaces.md` does not list these flags, so no row to remove. CHANGELOG has a "Breaking" entry.

## Tests

- AT-S2a (`tests/e2e/test_demo_command.py`): `--ref`, `--rows 50` and both exit 2 with "no such option" and write nothing; the helpers are gone. Red on base, green now.
- `tests/e2e/test_demo_command.py` + `tests/sentry` + `tests/sentry/io_policy`: 370 passed in the final io_policy plus demo run; the earlier full demo + sentry run was 1519 passed, 1 failed (the sink census, since fixed to 60 sinks, public 20).
- ruff check and format clean on touched files.

## Mutation

Re-adding `--ref` as a hidden option makes `test_demo_ref_and_rows_are_unknown_options[flag_args0]` fail (killed). Reverted.

## Deviations

- S2 is split. This PR is S2a only. AT-S2b (tiered hidden-name sentry) waits for X1 (CLI tier registry) and moves to S2b.
- The sink census test and sentry baselines changed because the removed code held 3 file sinks and 2 error sites.

cam

https://claude.ai/code/session_01SLKsADUhYs38T4cUjNstft
