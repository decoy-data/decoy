# Config, validation and the init wizard

Status: current

Part of the roadmap: [ROADMAP.md](../../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rows keep their number from the pre-split track. A row number or section number that is not in a group file is a closed row or old section in the [snapshot](../../archive/2026-11-18-roadmap-before-split.md).

## 1.0

Blocks the 1.0 release.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| DECOY-LANG | The Decoy language (owner 2026-11-19: V1). `.decoy` files define pipelines; the CLI stays the control surface and the wizard plus hand editing stays for basic jobs. Owner calls: O1 `decoy fmt`; O2 the run record keeps the compiled YAML beside the `.decoy` hash; O3 a folder with both `pipeline.yaml` and `pipeline.decoy` is refused; O4 `decoy init` writes `.decoy` by default, `--yaml` for YAML; O5 narrow subset-guard exemption for `lang/_subset.py`. | CLI | PARTLY BUILT. The compiler, converter, formatter and guide MERGED (CLI #333, `254fb342f`, 2026-11-20). Commands S2 to S7 are not merged (S1 MERGED as CLI #359, 2026-11-21): S1 (merged) one loader so every command reads `.decoy`, S2 source positions, S3 both-kinds route cells, S4 project layout, S5 `decoy fmt` and `decoy convert`, S6 `decoy init` writes `.decoy`, S7 run record sidecar. S8 (from SCAN-ML M3b, owner 2026-11-20): the column classifier's type guesses become suggested rules when `decoy init` or `decoy convert` writes a `.decoy` file (`starter_config`, `ColumnSuggestion`); M3b was planned onto the init wizard, which stopped on 2026-11-19. | C:`docs/plans/2026-11-19-decoy-language-commands.md` (revision 3, branch `plan/decoy-lang-commands`) | none; S1 first |
| VALIDATE-SUBSET-EDGES | `decoy validate` runs the subset edge-direction check, so a wrong-way edge fails at validate and not at run. Owner 2026-11-22 (V1 fast path) | CLI | NOT STARTED. No plan yet | none | none |

## Later (1.x)

Additive. Not scheduled until a 1.x release picks it up.

None.

### Candidates with no plan yet

Non-breaking ideas, so v1+ by rule. A candidate becomes a row in the table above when a release picks it up.

| Item | Source | Why it does not break |
|---|---|---|
| F18 config composition (includes, inheritance) | Council features | New optional keys; complete inline configs unchanged. |
| F19 semantic diff and repair | Council features | New command; no change to how a reviewed pipeline runs. |
| F41 expression evaluator preview | Council features | New command. |

## Maintenance

No user-visible change. Merges at any time and never gates a release.

None.
