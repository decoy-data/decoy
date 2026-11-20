# Public renames before 1.0

Status: current

The engine split its prototype package into `decoy_engine.detection`, `decoy_engine.profiling` and
`decoy_engine.verification`, and renamed public symbols, config keys, schema strings, events and
reason codes with it. The old-to-new table lives in the engine compatibility contract, section 1,
"Public renames", from the engine release that carries engine PR #730. Until then, see the engine
`CHANGELOG.md`, releases 0.11.0 and 0.17.0.

There is no alias for an old name. The CLI uses only the new names, and
`tests/sentry/release/test_retired_name_residual.py` fails if a CLI source file uses an old one.
