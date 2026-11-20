# Public renames before 1.0

Status: current

The engine split its prototype package into `decoy_engine.detection`, `decoy_engine.profiling` and
`decoy_engine.verification` and renamed six symbols (one of them private). There is no alias for an old name. If your code
imports one, use the new name in the second column. The CLI uses only the new names.

The product label and the wire names (the config field, schema string, event name and routes)
kept their spelling.

`tests/sentry/release/test_public_renames.py` checks that this table lists every pair of the engine
rename and that each old name is in the retired-name residual list. This file is the only tracked
file outside dated records that may spell the old names, and only in the table rows.

| Old name | New name | Kind |
|---|---|---|
| `run_storm` | `profile_columns` | function |
| `StormProfile` | `ColumnProfile` | class |
| `run_storm_post_mask` | `run_post_mask` | function |
| `StormPostMaskReport` | `PostMaskReport` | class |
| `storm_profiles_to_snapshot` | `profiles_to_snapshot` | function |
| `_run_storm_inner` | `_profile_columns_inner` | private function |
| `decoy_engine.storm` | `decoy_engine.detection, decoy_engine.profiling, decoy_engine.verification` | package |
