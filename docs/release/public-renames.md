# Public renames before 1.0

Status: current

The engine split its prototype package into `decoy_engine.detection`, `decoy_engine.profiling` and
`decoy_engine.verification`, and renamed public symbols, config keys, schema strings, events and
reason codes with it. The old-to-new table lives in the engine repository:

- the compatibility contract, section 1, "Public renames before 1.0";
- the engine `CHANGELOG.md`, release 0.17.0, "Breaking for consumers".

There is no alias for an old name. The CLI uses only the new names, and
`tests/sentry/release/test_retired_name_residual.py` fails if a CLI source file uses an old one.
