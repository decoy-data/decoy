# Versioning policy

`decoy-cli` follows [Semantic Versioning 2.0.0](https://semver.org/).

`decoy-cli` and `decoy-engine` each carry their own version number; they bump independently. The CLI pins one engine release exactly (`decoy-engine==X.Y.Z`), and that pin documents the engine surface it was tested against. Users get the CLI as a signed per-platform bundle that contains the matched engine.

## Bump rules

A release at version `MAJOR.MINOR.PATCH` follows these rules:

| Bump | Trigger |
|---|---|
| MAJOR | Backwards-incompatible change to the public CLI surface: a removed command, a removed flag, a renamed flag, an exit-code re-classification, a YAML schema field rename, a `decoy.cli.exit_codes` constant renamed or removed. Pre-1.0 the MAJOR slot stays at 0; pre-1.0 breaking changes bump the MINOR. |
| MINOR | Backwards-compatible additive change: a new command, a new flag (with a safe default), a new template, a new exit-code constant added (existing values unchanged), a new YAML schema field that defaults to a safe value. |
| PATCH | Bug fix or doc-only change with no surface change: a help-text fix, a typed-error message improvement, a workflow file update that does not change the smoke contract, a CHANGELOG-only commit. |

## Public surface (the contract MAJOR protects)

These are stable across MAJOR boundaries:

1. The set of `decoy <verb>` commands and their flags.
2. Exit-code integer values (the named constants in `decoy.cli.exit_codes` may evolve; the integers may not).
3. The V2 `PipelineConfig` YAML schema (engine-owned; the CLI propagates the engine's contract).
4. The `--json` envelope shape per command (the JSON output that scripts pipe into).
5. The set of bundled templates surfaced by `decoy list templates`.

These are NOT stable and may change across MINOR boundaries:

1. Help-text wording.
2. Spinner text and `--verbose` log line shape.
3. `decoy explain <topic>` body text.
4. Internal modules under `decoy.cli._*`, `decoy.ui.*`, `decoy.templates.*`.
5. The default Faker / Mimesis adoption matrix.

## Pre-1.0

Pre-1.0 (currently `0.X.Y`) the surface is settling. We try to follow MAJOR-equivalent rules using the MINOR slot, but reserve the right to make breaking changes in any 0.X.0 minor bump. The CHANGELOG entry calls out the break explicitly.

The first `1.0.0` release is gated on:

- The licensor confirmed by counsel (license FSL-1.1-ALv2).
- Publication of the signed bundles to the download host.
- A recorded canonical smoke install on each supported platform.
- The completed release readiness instance.

## Release process

A release is a bundle release, built and signed as described in the [packaging spec](../plans/2026-10-22-cli-distribution-and-packaging-spec.md). Nothing goes to a public package index.

1. Run `decoy --version` and confirm the value matches `pyproject.toml`'s `version`.
2. Append a new section to `CHANGELOG.md` under `## [X.Y.Z] - YYYY-MM-DD`.
3. Tag the release on `main` with `git tag vX.Y.Z` and push the tag.
4. Trigger the `release-smoke.yml` workflow on the tag. The smoke gate must be green before any bundle is published.
5. Build and sign the bundle for each platform, then publish the bundles, `SHA256SUMS` and the version document to the download host.

## Engine compatibility

`decoy-cli` X.Y.Z pins one engine release exactly (`decoy-engine==A.B.C`), and the bundle ships that release. There is no range to resolve. Moving to another engine release is a CLI release that changes the pin; the CHANGELOG entry names the engine version. Crossing an engine MAJOR boundary requires a CLI MINOR (additive) or MAJOR (breaking) bump.
