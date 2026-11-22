Status: plan

# After 1.0: what ships in 1.x and what waits for 2.0

Part of the roadmap: [ROADMAP.md](../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.
In short (owner, 2026-11-18): anything that does not break the contract is v1+; anything that breaks it is v2.
This page holds the rule. The items it used to list moved on 2026-11-18: see "Where the items are" below.
This page replaces `out-of-scope.md`. Owner direction, 2026-11-16.

## The rule

After the CLI ships 1.0.0, any change that keeps the contract the same is a 1.x release, whatever the
roadmap called it before. "V2" now means 2.0.0 only, and 2.0.0 means a change that breaks the contract.

The contract is the REL-GATE versioning freeze (roadmap row 93 and [release-gates.md](release-gates.md)):
CLI commands and flags, exit codes (including 6), the result schema, the YAML config schema, the reason
registry, versioned report tags (`name/vN`, for example `post-scan-integrity/v3`), install and signature
verification, and the engine compatibility contract (engine `docs/compatibility-contract.md`: artifact
formats, the vault, determinism, the public API, disguises).

Every item has one bucket:

| Bucket | Meaning |
|---|---|
| Before 1.0 freeze | Would be 2.0 if it shipped after 1.0, but can be done now. It is a 1.0 row in a group file. |
| 1.x minor | Adds a command, flag, option, format or feature, or turns a refusal into a success. Every existing valid config and run still gives the same result. |
| 1.x patch | A fix or an internal cleanup with no user-visible change. |
| 2.0 | Removes or renames a public name, changes a default output or the determinism of an existing config, changes the meaning of an exit code or reason, or drops an old config key or report tag. |

Four tests decide, in this order. (1) Does a name, default, output byte, exit code, reason string, schema
field or report tag change for a config or run that is valid today? Then it is 2.0, or before 1.0 freeze if
it can be done now. (2) Can it be done by adding something next to the old behavior? Then 1.x minor.
(3) Does nothing user-visible change? Then 1.x patch. (4) Could the design go either way? Then write
"1.x if <design>, else 2.0" and name the design that keeps it 1.x. A new refusal of something that works
today is a contract change. A new warning on stderr is not.

Where the source says "V2", "V2-LOG", "post-V1" or "V1+", read the bucket on this page instead.

## Where the items are

| Bucket | Home |
|---|---|
| Before 1.0 freeze | 1.0 rows: PROP-FALLBACK (24zi), PROP-SURFACE (24zj), PROP-SHIMS (24zk), FREEZE-OUTPUT in the group files; open choices in [inbox.md](inbox.md) |
| 1.x minor | "Candidates with no plan yet" under Later in each [group file](groups/); platform-only ones in [platform-parked.md](platform-parked.md) |
| 1.x patch | "Maintenance candidates" in [groups/health.md](groups/health.md) |
| 2.0, and "2.0 only if built the other way" | [2.0-holding.md](2.0-holding.md) |

## Named 1.x speed slots

Owner 2026-11-19: work from the engine speed and route record `E:docs/records/2026-11-19-engine-speed-and-route-completeness.md` (engine #715) that had no row became named slots.
Each slot is a row in the Later table of its group file, tagged with its release. The rule for every
1.x speed release: same input, same seed, same output. A slot that cannot keep the output bytes
identical is not 1.x and goes back to the owner. The release notes and the proof manifest carry the
before and after numbers.

Owner 2026-11-22 (scope cut): rows 36, 29 and 32c, F09 rotation and remap (79b), F25 quotas (58b), the GEN-TYPES distribution families (24qb) DELIV best-effort (61b), F26 `decoy cleanup` (74b) and the DECOY-LANG sidecar (LANG-SIDECAR) moved from 1.0 to the slots below. They are not speed slots, but they keep the same rule: a 1.0 config or run keeps its result.

Owner 2026-11-22: the speed slots below that were 1.0.x or 1.1 (GEN-VECTOR-STREAMS, TEXT-REDACT-RUST-SPLICE, FPE-CHECKSUM-NATIVE, PER-COLUMN-ROUTING) moved into 1.0, and FAKER-NATIVE-WIDEN, LARGE-STRING-CAST and UF-DOMAIN are firm 1.0. Engine fast-path gaps are due 2026-12-15. SEAM-REASONS stays a candidate; its first decline reason ships inside ROUTE-LABEL-TRUTH.

| Release | Slot | Group |
|---|---|---|
| 1.0.x if its plan is not small | NONFK-OOM part (b) (1.0 row) | [run](groups/run.md) |
| 1.1 | 36 L2-cli, then 29 SCAN-MULTI S3-cli | [library](groups/library.md), [scan](groups/scan.md) |
| 1.1 | LANG-SIDECAR (DECOY-LANG S7, compiled-YAML sidecar) | [config](groups/config.md) |
| 1.1 | 32c SCAN-ML-MD as an opt-in model (the small model stays the default) | [scan](groups/scan.md) |
| 1.2 | RUST-DATE-TEXT | [mask](groups/mask.md) |
| 1.2 | 79b F09 rotation and remap | [mask](groups/mask.md) |
| 1.2 | 24qb GEN-TYPES E1b distribution families | [generate](groups/generate.md) |
| 1.3 | CHUNK-PARALLEL | [run](groups/run.md) |
| 1.3 | 58b F25 quotas, opt-in with no default quota | [run](groups/run.md) |
| 1.3 | 74b F26 `decoy cleanup` and stage reclaim | [run](groups/run.md) |
| 1.3 | 61b DELIV best-effort and exit 6 (1.0 refuses `best_effort` at validate) | [run](groups/run.md) |
| 1.x | PIP-NATIVE-EXTRA | [release](groups/release.md) |
| 1.x | OOC-QUARANTINE, then OOC-DATE-BUCKET | [run](groups/run.md) |
| 1.x, on demand | FK-CHUNKED-HASH-CHILD | [run](groups/run.md) |

## Corrective backlog (vault)

The vault holds the corrective backlog in one file, `handoffs/V2-CORRECTIVE-BACKLOG.md`, merged on 2026-11-16 from two
overlapping copies (nothing was dropped: every line of both is in the merged file). Each of its 528 entries carries a
bucket tag. The tags are a first pass. These are the counts:

| Bucket | Entries |
|---|---|
| 1.x patch | 436 |
| 1.x minor | 17 |
| either (1.x if a named design, else 2.0) | 38 |
| before 1.0 freeze | 2 (now in FREEZE-OUTPUT and FREEZE-SURFACE) |
| 2.0 | 0 |
| V1 (entry says it stays V1 or was kept V1) | 16 |
| check (needs an owner answer or a fact) | 10 |
| n/a (index rows and notes) | 9 |

## Owner questions

1. Reason codes (audit B9): 68 of 69 platform codes and others are unreferenced in the engine and CLI. Record the platform
   consumer, or remove the code before the freeze?
2. Package A: A1, A3, A4 and A8 are 1.0 work (row 24zi) because each turns a run that works today into an
   error, and A8 changes the exit code of a run with no outputs from success to failure. A2, A5, A6 and A7 turn a
   fallback into an error only on a broken install or an internal bug and are kept as 1.x patch. Confirm the split.
3. F17 and F27: the companion scope marks them V1 and the old list kept them as V2. Which is right? This page treats them
   as 1.x minor.
4. Which public renames belong in "Before 1.0 freeze" for the STORM taxonomy split and the F22 names?
5. Does the platform API count as contract? The rule above lists the CLI and the engine. The backlog's platform entries are
   tagged for that reading (patch unless named otherwise).
6. The ten `check` entries in the vault file (`grep '\[check:'`) each name the owner question or the missing fact.
7. Platform V2 plan feature 1 (reversible tokenization vault, de-tokenize half) waits on an auth-model decision: who may
   de-tokenize, under what policy, with what key custody.
