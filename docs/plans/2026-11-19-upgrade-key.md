Status: plan

# UPGRADE-KEY: update-channel key rotation (roadmap row UPGRADE-KEY)

Owner: Cam. Author: Opus planner. Date: 2026-11-19. Revision 3 (answers Dennis round 2,
GO-WITH-FIXES with 0 BLOCKER, 3 HIGH, 6 MEDIUM, 5 LOW).

Rules consulted: `dev-rules/README.md`, `00-universal.md`, `risk-and-exceptions.md`,
`development-loop.md`, `profiles/local-operations.md`, `workspace-and-vcs.md`, `reuse-first.md`,
`exploration.md`, `scope-discipline.md`, `proportionality.md`, `verification.md`, `code-review.md`,
`feature-dev.md`, `api-and-compatibility.md`, `security.md`, `release-and-rollback.md`,
`observability-and-resilience.md`, `config-secrets-and-supply-chain.md`, `testing.md`,
`cross-cutting-concerns.md`, `architecture.md`, `documentation.md`, and
`catalogs/recurring-defects.md`; owner memory
rules: V1 bar, PLAN defines acceptance tests, sentry over prose, root cause not patch, commit message
standard, test depth T0 to T4, one test runner per box, no em-dashes.

Bases: CLI `origin/main` at `ccc5540a`, read with `git show` from `wt-plan-upgrade-key`;
`origin/plan/cli-rel` at `d46cb9c7`; and the `origin/plan/release-chain` and
`origin/plan/win-feas` refs fetched on 2026-11-19. Notation: `C:` is CLI `src/decoy/`, `PT:` is CLI
`packaging_tools/`, `CT:` is CLI `tests/`.

Plans this one builds on: `plan/cli-rel` (row 94, `release.yml`, S0 with its `publish`, `resign` and
`rollback` modes), `plan/release-chain` (row 88, 88-O offline upgrade, 47-B), `plan/mac-ed25519`
(SSHSIG sidecar), `plan/rel-gate` revision 3 (G0 to G8, frozen surfaces), `plan/win-feas`
revision 3 (CW1 locks, CW3 prune). Roadmap: `docs/roadmap/groups/release.md` rows 88, UPGRADE-KEY,
93 (REL-GATE) and 94 (CLI-REL); `docs/roadmap/decisions.md:10-11`.

Owner decision (2026-11-18, option B), word for word: "the CLI pins a main release key plus an
offline backup key; a document signed by the backup can name a new main key and revoke the old one;
an unknown version-document format gives a coded 'download the latest installer' message. The owner
must create the backup key and keep it offline."

Risk: R2 overall (the install and upgrade trust path, a signing key, a frozen contract that a 1.0
install reads forever). Review: Dennis, then Codex. One owner task (create the backup key). No spend.

## Revision 3 changes

Every Dennis round 2 finding is adopted. The section column names the authoritative plan text and
the acceptance row that prevents regression.

| Finding | Bar | Resolved in | Revision 3 change |
|---|---|---|---|
| R2-H1 | V1 | D5, D8, class 3, AT-UK1-28 (M41), slices | An epoch rise without a version document writes serial 0; the offline test now proves a later normal-serial K2 network document is accepted |
| R2-H2 | V1 | 4.9, AT-XR-2 (M42), AT-XR-3 (M43), X5, X6, done-when | CLI-REL resolves a K1-signed live document across the K2 commit, gives resign and rollback their own output assertions, rotates the engine secret and re-signs or re-cuts the native companion |
| R2-H3 | V1 | D1, D10, section 8 preamble, AT-UK1-31 (M44), UK1a, Q3 | One fixture patches both module pin paths and the committed-statement path; environment seams remain dev-only; the fixture and custody commands land before the owner task |
| R2-M1 | V1 | D4, D7, Placement, UK1a, AT-UK1-32 (M45) | `InstallError` moves to acyclic leaf `distribution/errors.py` and remains re-exported from `installer` for existing callers |
| R2-M2 | V1 | D2, UK1a | `fingerprint` moves beside `raw_public_bytes` in `signing.py`, so the UK1a state reader does not import UK1b |
| R2-M3 | V1 | D11 step 2, AT-UK1-26 (M46) | The shell fingerprint path decodes and validates the 44-byte Ed25519 SPKI directly, hashes its last 32 bytes, validates the digest and searches only the `revoked_keys` array |
| R2-M4 | V1 | AT-UK1-26 (M47) | The revoked installer cell asserts zero fetches and the exact out-of-date text |
| R2-M5 | V1 | D10, AT-UK1-31, UK1a, UK2, OWNER-1, Q3 | `keygen --encrypt` and `backup-check` move to UK1a before the 2026-11-28 owner task |
| R2-M6 | V2-LOG | AT-UK1-30 (M36), X1, X5 | The builder test now asserts that `build_document(**fields)` with `key_rotation` raises `TypeError`; signed-output protection stays at the CLI-REL modes |
| R2-L1 | V1 | D7, AT-UK1-33 (M48) | `build_document` refuses canonical output over 32 KiB |
| R2-L2 | V1 | D11 step 3, AT-UK1-21 (M49) | The shell fast serial check is skipped when the canonical document carries `"key_rotation":"` |
| R2-L3 | V1 | D5, AT-UK1-18 (M50) | The trust-state writer asserts that the first `"serial":` in its output is the top-level serial |
| R2-L4 | V2-LOG | Later L6 | The optional verification bypass in `verify_extracted.py:35` is logged as a follow-up outside this plan |
| R2-L5 | V1 | D11, 4.8, F14, F15, AT-UK1-26 (M51, M52) | Replace without an existing home is a coded refusal pointing at normal install; corrupt trust state is reset only after the replacement verifies, while settings remain unchanged |
| Additional exact-key check | V1 | AT-UK2-8 (M53) | The single-validator sentry matches exact string constants `epoch` and `revokes`, never substrings |
| Self-review | DESIGN | D13, AT-UK1-16 (M54) | The seven new runtime reason codes now live in one closed registry in the acyclic error leaf, guarded against copies |
| Self-review size | V2-LOG | Section 12 | The plan is 900 lines, within the 800 to 900 V2 cleanup band and not a merge blocker; implementation source caps remain below 800 |

## Revision 2 changes

Revision 2 adopted every Dennis round 1 finding. Its ids remain attached to the authoritative
design and AT rows: R1-B1 to R1-B3, R1-H1 to R1-H2, R1-M1 to R1-M11 and R1-L1 to R1-L10.
Mutations M1 to M40 retain those meanings. Revision 3 supersedes only the rows explicitly changed
in the table above: R1-M9 custody commands now ship in UK1a, and the CLI-REL coverage expands from
AT-XR-1 to AT-XR-3.

## 0. Summary for the owner

Today every installed CLI trusts exactly one key: the main release key in
`C:distribution/release_key.pub.pem`. If that key leaks or is lost, there is no signed way to tell
installed CLIs to trust a new one. Users would see "signature INVALID" on every upgrade and would
have to find out for themselves that they must reinstall.

This plan adds what the owner chose and nothing more:

1. The CLI pins a second public key, the backup key. Its private half stays offline with the owner.
2. The version document may carry one extra field, `key_rotation`: a small statement signed by the
   backup key that says "the main key is now K2; K1 is revoked". The CLI checks that statement
   against the pinned backup key, then checks the version document against K2. It records the new
   key, the revocation and the new epoch in `trust_state.json`, so a document signed by K1 is
   refused from then on.
3. A version document in a format this CLI does not know gives a coded refusal
   (`upgrade_format_unknown`) that tells the user to download the latest installer and run it with
   `--replace`, which installs over the old runtime and keeps the user's settings.

Six slices: UK1a to UK1d (CLI trust core, R2), UK2 (signing tools and the rotation drill, R2), UK3
(runbook and contract docs, R1). About 3,230 lines with tests and docs. One owner task: create the
backup key offline before the first signed 1.0 candidate (Q2, Q3).

## 1. FRAME

### 1.1 Problem

- `C:cli/upgrade.py:84` reads one key, `release_key.pinned_public_pem()`, and uses it for the version
  document (`:112`), the bundle signature (through `installer.install_version`, `:164-172`) and the
  local rollback (`:99`). There is no second key and no way to change the key without a new install.
- The signer docstring describes a rotation that does not exist: "keep the old public key in a
  documented trust set for one deprecation window" (`PT:sign_release.py:15-17`). No code reads a
  trust set.
- An unknown `schema_version` raises `ValueError` in `C:distribution/version_document.py:118-119`,
  which `C:cli/upgrade.py:122` prints as "version document rejected: ValueError." The user is not
  told what to do, and the installer they would download refuses an existing runtime
  (`PT:install/install.sh:196-215`) and points back at `decoy upgrade`.
- 1.0 is the last chance: a 1.0 install can only ever trust what 1.0 pins (row UPGRADE-KEY).

### 1.2 Guarantee (what 1.0 promises)

- G1 Rotation. A 1.0 managed install that pins main key K1 and backup key B accepts a version
  document signed by K2 when the document carries a rotation statement, signed by B, that names K2
  as the main key and revokes K1. It then installs bundles signed by K2.
- G2 Revocation sticks. After G1, the install refuses any version document, bundle or local runtime
  whose trust rests on a revoked key, on every later run, including from a retained older runtime
  that pins K1.
- G3 Nothing else can rotate. A rotation statement that is not signed by the pinned backup key, that
  names the backup key or a revoked key as the main key, that revokes nothing, whose epoch is lower
  than one already accepted, or whose epoch equals the stored one but names a different main key, is
  refused and changes nothing.
- G4 Unknown format. A version document or rotation statement whose `schema_version` this CLI does
  not know gives exit 3 with code `upgrade_format_unknown` and the fixed text of D6. The text carries
  no value from the document.
- G5 No regression. A document signed by the pinned main key, with or without a rotation statement
  that names that same key, behaves exactly as today.
- G6 Release builds carry the backup key. Whenever the main pin is a real key, `check-keys` fails
  unless the backup pin is a real Ed25519 key, differs from the main key and is not revoked by the
  committed statement. CLI-REL's `verify_release_set` applies the same check to every candidate.
- G7 A leaked old key cannot block the new one. A serial accepted under epoch N never refuses a
  document of a verified epoch above N.
- G8 The advertised remedy works. The installer named in the D6 text, run with `--replace` on an
  existing home, installs the new runtime and keeps `settings.json` and valid `trust_state.json`.
  Corrupt trust state is replaced only after all replacement verification succeeds.

Non-goals (1.0): TUF roles, thresholds or multiple signatures; rotating the backup key itself (Q6);
rotation in a cached older `install.sh` or in `install.ps1` (a fresh installer always pins the
current key; the Windows target is gated off, `PT:install/install.ps1:47-58`); any change to the
startup update notice (it is unsigned and advisory, `C:_update_check.py:117-119`); re-signing
bundles already published (Q1); hardware tokens (Q2).

### 1.3 Failure modes this plan designs against

| # | Failure | Design answer |
|---|---|---|
| F1 | Main key leaks; attacker signs a document with K1 | Rotation revokes K1; G2 keeps it revoked in `trust_state.json` |
| F2 | Attacker strips the rotation statement and serves an old K1-signed document | The new main key and the revoked set are kept in local state, not only in the document (D5); serial and expiry refuse a replay within an epoch |
| F3 | Attacker forges a rotation statement under their own key | `signing.verify_envelope` requires the embedded key to equal the pinned backup key (`C:distribution/signing.py:79-101`) |
| F4 | A replayed older rotation (epoch 2 after epoch 3), or two different statements for one epoch | Monotonic `key_epoch` in state; a lower epoch is refused; an equal epoch must name the stored key |
| F5 | A release path drops or copies a stale `key_rotation` | The single builder `vd.build_document` sets the field from the committed statement and has no parameter to drop it (D7); CLI-REL output routes and release-set verification check it (AT-XR-1 to AT-XR-3) |
| F6 | A hostile or huge document is parsed before its signature is checked | Pre-verify parse only under a 64 KiB cap and only to pull out the rotation envelope; nothing from it is trusted until `verify_envelope` passes |
| F7 | Two upgrades race; one records a rotation while the other acts on an older decision | The trust decision is taken again inside `installer._exclusive` |
| F8 | Backup pin is the placeholder in a release build | `check-keys` fails whenever the main pin is real; at runtime a rotation in a placeholder build is refused, never silently skipped |
| F9 | A future v2 document reaches a 1.0 install | Coded `upgrade_format_unknown` with the download page and `--replace` |
| F10 | Backup key lost | Rotation becomes impossible; the runbook says so; Q2 asks for two encrypted copies and a restore test |
| F11 | Attacker with leaked K1 serves a document with serial 2^53 before the rotation | The serial floor belongs to an epoch; the verified epoch-2 statement resets it (D5) |
| F12 | `install.sh` reads a nested field instead of the top-level one | `key_rotation` is one opaque base64 string; `install.sh` sees no nested JSON (D3) |
| F13 | The recovery the message advertises cannot run on an existing install | `install.sh --replace` (D11) |
| F14 | `--replace` is run against a home with no installed runtime | Coded pre-fetch refusal points at the normal install form (D11) |
| F15 | Existing `trust_state.json` is corrupt during recovery | Replacement verification finishes before an atomic trust-state reset; settings and failed attempts remain unchanged (D11) |

## 2. Established solutions (survey)

Searches run on 2026-11-19: TUF section 5.3; OpenBSD signify rotation; Debian archive rotation and
`debian-archive-keyring`; minisign; Sigstore root signing; Android APK Signature Scheme v3. The
codebase search covered the distribution modules, both installers, signer and document builder,
plus the related plans.

- **TUF root rotation** (https://theupdateframework.github.io/specification/latest/#update-root)
  supplies the core pattern: an offline key vouches for an online key, versions are monotonic,
  accepted trust roots persist, key ids are hashes, and a key change resets the old metadata floor.
  This plan omits thresholds, roles, chain files and root expiry. Unlike TUF, backup B alone signs
  the statement because K1 may be compromised; cumulative revocations allow skipped epochs; an
  equal epoch must name the stored key. The repo already uses TUF serial and expiry checks.
- **signify** (https://flak.tedunangst.com/post/signify) and **Debian archive keys**
  (https://ftp-master.debian.org/keys.html) introduce the next key through existing trust. This plan
  does not use per-release keys, a keyring package or double signatures. **minisign** has no rotation
  protocol, matching the CLI's current limitation.
- **Sigstore root signing** (https://github.com/sigstore/root-signing) supplies the offline recorded
  ceremony. Hardware keyholders are later work. **Android v3**
  (https://source.android.com/docs/security/features/apksigning/v3) uses old-key lineage, rejected
  here because a compromised K1 cannot vouch for K2.

Result: TUF's root-key pattern is reduced to one offline backup, one cumulative statement, one epoch
and serial floor, one stored main key and one revoked set. Existing `signing.py` performs all crypto.

## 3. Design notes

D1. **One offline backup key, pinned.** `C:distribution/release_backup_key.pub.pem` sits beside
`release_key.pub.pem`. It holds the placeholder `__DECOY_RELEASE_BACKUP_PUBLIC_KEY__` until the owner
creates the key (Q2); then the real public half is committed (it is public, so no injection step is
needed). `release_key.pinned_backup_pem()` follows the rules of `pinned_public_pem()`
(`C:distribution/release_key.py:37-63`) with one stricter rule (R1-L3): the dev override
`DECOY_RELEASE_BACKUP_PUBKEY_FILE` is honored only while both the backup pin and the main pin are
the placeholder, with the same warning. Otherwise the override is ignored with a warning, so no
environment variable can add a backup key to a build that pins a real main key. A build whose backup
pin is the placeholder raises `NoPinnedKeyError`, which matters only when a rotation needs the
backup key. The environment seams are for placeholder dev builds only. Tests do not depend on them:
one shared fixture in existing `CT:conftest.py` monkeypatches `release_key._KEY_FILE`, the new
module-level backup-key path and the module-level path read by
`key_rotation.committed_statement()`. The fixture definition lands in UK1a before its UK1b
`key_rotation` consumer, as an explicitly paired later-slice consumer. It is used by every
rotation acceptance row and remains valid after the real main and backup pins are committed
(R2-H3).

D2. **The rotation statement.** A signed envelope in the format `signing.verify_envelope` already
checks (`{alg, payload, signature, public_key}`, `C:distribution/signing.py:79`). Payload:

```json
{
  "schema_version": "cli-key-rotation/v1",
  "epoch": 2,
  "main_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n",
  "revokes": ["<sha256 hex of the raw 32-byte Ed25519 key>"],
  "issued": "2027-03-01T00:00:00Z"
}
```

`epoch` 1 is the pinned key; a statement has `epoch >= 2`. `revokes` is cumulative: the statement for
epoch 3 lists K1 and K2, so a client that missed epoch 2 still revokes both. `issued` is for people;
nothing checks it. There is no expiry: a client that was offline for a year must still accept the
statement. The fingerprint is `sha256(raw key bytes)` in lower-case hex, computed by
`signing.fingerprint(pem)` beside `signing.raw_public_bytes`. Both ship in UK1a because the
trust-state reader needs the function before UK1b exists (R2-M2). R1-L2 still applies: the private
`_raw_public_bytes_from_pem` is renamed, its one outside caller `PT:sign_release.py:261` is updated,
and no alias is kept.

D3. **Where the statement travels (R1-B1).** Inside the version document, as the optional top-level
field `key_rotation`, whose value is one string: standard base64 of
`signing.canonical_bytes(envelope)`. The roadmap row says "a version document signed by the backup
key can name a new main key"; a backup-signed statement inside a main-signed document gives that,
with one fetch and no new URL. The opaque string is required because `install.sh` reads fields with
`grep` over the sorted canonical bytes (`PT:install/install.sh:134-142`): `key_rotation` sorts before
`schema_version`, and a nested payload with its own `schema_version` would be read first, so
`install.sh` would refuse every document after a rotation. Base64 has no `"`, `{` or `}`, so the
existing `json_top_string`, `json_top_number` and `json_artifact_field` patterns cannot match inside
it. Only `key_rotation.py` decodes it. The v1 contract already says unknown top-level fields are
ignored (`docs/distribution/version-endpoint-contract.md:91`), so `schema_version` stays
`cli-version-document/v1`.

D4. **Resolution order (one function, `key_rotation.resolve_main_key`).** `InstallError` moves from
`installer.py` to the leaf `C:distribution/errors.py`, and `installer` re-exports it for existing
callers. `key_rotation.TrustRefusal` subclasses `errors.InstallError`, so the import graph is
`installer -> version_document -> key_rotation -> errors`, never back into `installer` (R2-M1).
Inputs: the document bytes, the detached signature, the pinned main key `Mp` and backup key `B`, and the trust state `S`
(`key_epoch` `Es`, stored `main_key` `Ks` when `Es > 1`, `revoked_keys` `Rs`, `serial`). It returns a
`TrustDecision(main_pem, epoch, revoked, serial_floor)` or raises `key_rotation.TrustRefusal`, which
carries one fixed `code` (R1-M4).

1. Pre-verify extract. If the bytes are at most 64 KiB, parse them as JSON. If the result is an
   object whose `key_rotation` is a string, decode it with `base64.b64decode(validate=True)`, parse
   the result as JSON, and keep it as the envelope if it is an object. Any failure (a parse error,
   `RecursionError`, a non-object, a non-string field, invalid base64, or a size over the cap) means
   "no statement". Step 1 also notes the top-level `schema_version` if it is a string. Nothing read
   here is trusted yet.
2. With a statement: if the backup pin is the placeholder, refuse `upgrade_rotation_unavailable`. If
   the payload `schema_version` is a string other than `cli-key-rotation/v1`, refuse
   `upgrade_format_unknown`. Check the envelope with `signing.verify_envelope(...,
   expected_public_pem=B, schema_version="cli-key-rotation/v1")`; failure refuses
   `upgrade_rotation_invalid`. Then `key_rotation.validate_statement` checks: `epoch` is an int (not
   bool) >= 2; `revokes` is a non-empty list of strings that `re.fullmatch("[0-9a-f]{64}")` accepts;
   `main_key` loads as Ed25519; its fingerprint differs from B's and is not in `revokes`. Any failure
   refuses `upgrade_rotation_invalid`. Against state: `epoch < Es` refuses
   `upgrade_rotation_replayed`; `epoch == Es` with a `main_key` other than `Ks` refuses
   `upgrade_rotation_invalid` (R1-M1); a `main_key` whose fingerprint is in `Rs` refuses
   `upgrade_key_revoked`. The candidate main key is `main_key`, the epoch is the statement's, and the
   revoked set is `Rs` plus `revokes`.
3. Without a statement: the candidate main key is `Ks` when `Es > 1`, else `Mp` (R1-M1); the epoch
   is `Es`; the revoked set is `Rs`.
4. If the candidate's fingerprint is in the revoked set, refuse `upgrade_key_revoked` (a defensive
   check; the state reader already refuses a stored main key that is revoked).
5. Verify the detached signature over the exact bytes with the candidate key through
   `signing.verify_detached` (the function `vd.verify_document` wraps; `key_rotation` does not import
   `version_document`, so there is no import cycle with D7). On failure, classify, in this order:
   (a) the step 1 `schema_version` is a string that starts with `cli-version-document/` and is not
   v1: `upgrade_format_unknown` (Q5); (b) `Mp` is in the revoked set and the signature verifies under
   `Mp`: `upgrade_key_revoked` (the pinned-key diagnosis, R1-M6); (c) otherwise
   `upgrade_signature_invalid` with today's text. The classification never accepts a document; it
   only picks the message.
6. After verification: the strict `vd.parse_document` runs (D6). If the parsed document carries
   `key_rotation` but step 1 found no statement, refuse `upgrade_rotation_invalid` (R1-L9): a signed
   document with a broken statement is a release-tool fault and fails closed.
7. `serial_floor` is the stored `serial` when the decision's epoch equals `Es`, and 0 when it is
   higher (R1-B2).

No second verifier: steps 2 and 5 call the two existing functions in `signing.py`.

D4a. **Recording (R1-M2).** `installer.check_document_freshness(doc, home, decision, record=...)`
checks expiry and `serial >= decision.serial_floor`, and on a recording run writes the state (D5).
A recording run is any run that holds the install lock and is not `--check`: `install_version`, the
new `installer.record_trust(doc_bytes, sig, home)` that `decoy upgrade` calls on the up-to-date path
when the pre-lock decision's epoch is above the stored one, and `first_install` (D11).
`record_trust` takes `_exclusive`, resolves again from the bytes, and writes only when the epoch
rose; with no rotation the up-to-date path writes nothing, as today. `--check` never writes.

D5. **Trust state and writer API.** `trust_state.json` gains `key_epoch` (int, default 1), `main_key` (the PEM of the current epoch's main key, present only when `key_epoch > 1`) and `revoked_keys` (sorted list of
fingerprints, default empty). `serial` stays a top-level integer, because `install.sh` reads it with
`json_top_number` (`PT:install/install.sh:134`, `:289`), and now means "the highest serial accepted
in the current epoch". The reader and writer move from `C:distribution/installer.py:182-212` into a
new `C:distribution/trust_state.py`, the one module that reads or writes the file. The reader
refuses, as unreadable state: a `key_epoch` that is not an int >= 1 or is a bool; a non-empty
`revoked_keys` with `key_epoch` 1; `key_epoch > 1` without a `main_key` that loads as Ed25519 and is
not revoked; a `revoked_keys` entry that is not 64 lower-case hex. The writer takes the union of the
stored and new revoked sets (grow-only) and the larger epoch. Its writer API takes the decision plus
`document_serial: int | None`. When the epoch rises with a version document, `serial` is set to that
document's serial. When the epoch rises without a document, as on the 88-O sidecar route, `serial`
is set to 0. It never carries the old epoch's floor into a new epoch. `main_key`, epoch, revocations
and reset serial are written in the same atomic write (R1-B2, R2-H1, TUF 5.3.11); within one epoch
`serial` only rises and a no-document write cannot lower it. Unknown top-level fields are kept as they were read
(R1-M8): a 1.0 runtime rolled back under a 1.x home must not drop what 1.x wrote. The contract
(D12) forbids any later field from nesting a key named `serial`, because `install.sh` reads the
first match. Before writing, the writer asserts that the first exact `"serial":` token in its
generated output is the top-level serial it is about to persist. It refuses rather than emit output
where an unknown retained field would put a nested `serial` first (R2-L3). The state is written once,
atomically, after every check. The file stays local state,
not a secret, as today (`C:distribution/installer.py:46-48`).

D6. **Unknown format (R1-L8).** `vd.parse_document` raises a new subclass
`UnknownFormat(ValueError)` when `schema_version` is a string other than `cli-version-document/v1`.
Its message is fixed and value-free: "version document format is not supported by this decoy". The
same class, with the fixed message "rotation statement format is not supported by this decoy", is
raised for an unknown statement schema. The old message at `C:distribution/version_document.py:119`,
which quoted the document's value, is gone. `_refuse` gains a keyword-only `hint` (fixed text only).
`DOWNLOAD_PAGE_URL` is a constant beside `DEFAULT_URL` in `version_document.py` (Q4). The exact
human output is:

```
error: [upgrade_format_unknown] the update channel uses a format this decoy cannot read: UnknownFormat.
  hint: download the latest installer from https://trydecoy.com/download and run it with --replace; it keeps your settings.
```

and the `--json` object is `{"command": "upgrade", "status": "error", "error": "the update channel
uses a format this decoy cannot read: UnknownFormat.", "code": "upgrade_format_unknown", "hint":
"download the latest installer from https://trydecoy.com/download and run it with --replace; it
keeps your settings."}` in the `decoy-error-v1` shape. Every path to this code raises
`UnknownFormat`, so the suffix is always `UnknownFormat`. No value from the document reaches the
output.

D7. **Every document carries the statement, from one builder (R1-B3).** The acyclic error leaf in
D4 lets `version_document` import `key_rotation` without closing the former
`installer -> version_document -> key_rotation -> installer` cycle (R2-M1). A committed file
`C:distribution/key_rotation.json` (absent until the first rotation) holds the canonical envelope
bytes of the current statement. It sits in the runtime package, not in `PT:`, because the single
builder `vd.build_document` lives there and must not import build-host tools. One helper,
`key_rotation.committed_statement()`, reads the file, checks it with `validate_statement` against
the pinned backup key, and returns the base64 string (or `None` when the file is absent).
`vd.build_document` calls it on every build and sets `key_rotation` from it; it has no parameter to
pass or drop the field, so a caller that copies a live document's fields (CLI-REL `resign`) still
gets the committed statement. A committed statement that fails the check makes `build_document`
raise, so no document is built. After canonical encoding, `build_document` refuses output larger
than 32 KiB, leaving headroom below the 64 KiB pre-verify statement-extraction cap (R2-L1).
`make_version_document.py` and CLI-REL `sign-set`, `resign` and `rollback` all build through `build_document`; CLI-REL also runs `verify_release_set`, which must
require the statement, canonical-equal to the committed one, whenever one is committed (cross-plan
lines X1 and X5, AT-XR-1 to AT-XR-3). This is the cumulative-statement replacement for TUF's chain walk: a 1.0.0
install that never upgraded still finds the statement in whatever document is live. The file ships
in the wheel (harmless: it is public and signed); no runtime path reads it.

D8. **One choke point for key use.** Every place that picks a key to verify with goes through
`key_rotation`: `resolve_main_key` for the network paths and `local_key(home)` for local activation
and the 88-O offline bundle path. `local_key` returns `Ks` when `Es > 1`, else `Mp`, and on a failed
verification applies the D4 step 5 classification ((b) then D9). The 88-O path also reads an
optional sidecar `PATH.key_rotation` (the same base64 string as the document field) and resolves it
through D4 step 2 against the stored state, then records the decision under the lock when the
bundle installs (R1-M5). Because that route has no version document, it passes
`document_serial=None` to the D5 writer. An epoch rise therefore records serial 0, and a later K2
network document uses its own epoch-2 serial instead of the K1 floor (R2-H1). `install_version` and `activate_local_version` lose their
`expected_public_pem` parameters (R1-M4): each resolves its key inside `_exclusive`, so no caller can
pass a stale or `None` key, and the `None`-skips-verification branch at
`C:distribution/installer.py:412` is deleted. `install_version` uses the decision for the document,
the bundle signature (`C:distribution/installer.py:543`) and the manifest (`:555`). `decoy upgrade`
catches `TrustRefusal` before `InstallError` and emits `exc.code`, so an under-lock rotation
refusal is not reported as `upgrade_install_failed` (`C:cli/upgrade.py:173`).

A guard test walks the syntax tree of every module under `C:` (R1-L4). It fails when a module other
than `key_rotation.py` and `release_key.py` references `pinned_public_pem` or `pinned_backup_pem` in
any form (a call, a bare attribute or name reference, an assignment to a local, `import ... as`,
`from release_key import name`, `from ... import name as alias`), or holds a string constant that
contains `release_key.pub.pem`, `release_backup_key.pub.pem` or `key_rotation.json`. One exception,
scoped to the function and recorded with its reason: `C:__main__.py:226` `_key_unresolved`, which only
asks whether a key is pinned.

D9. **Rollback across a rotation (Q1).** A retained runtime whose manifest was signed by a revoked
key cannot be verified with the current key. `activate_local_version` verifies with
`local_key(home)`. On failure: D4 step 5 (b) gives `upgrade_key_revoked` when the running runtime's
own pin is revoked and verifies the slot; else, when `key_epoch > 1`, the refusal is
`upgrade_rollback_key_rotated`, whose hint says to install that version again with
`decoy upgrade --force --version <v>` if it was re-published under the new key. `current` is not
changed.

D10. **Signer side (R1-H1, R1-M7, R1-M9).** All statement checks on the build host call
`key_rotation.validate_statement` and `key_rotation.check_release_pins`; `PT:` holds no second copy.
The custody prerequisites ship early: UK1a owns `keygen --encrypt` and `backup-check` so OWNER-1 can
run by 2026-11-28. UK2 owns `rotation`, the expanded `check-keys` and the release drill.

- `sign_release.py keygen` gains `--encrypt`: it asks for a passphrase twice through `getpass` and
  writes `BestAvailableEncryption` PKCS8. Without `--encrypt` it behaves as today (CI and tests).
- `sign_release.py rotation` reads the backup private key only from `--backup-key-file`, never from
  `DECOY_RELEASE_KEY_PEM` or `DECOY_RELEASE_KEY_FILE`, so the CI secret path cannot reach it. It
  refuses a file that is not encrypted PKCS8 (`-----BEGIN ENCRYPTED PRIVATE KEY-----`). It takes
  `--new-main-pub`, `--epoch` and `--revoke-pub` (repeatable), refuses an epoch not above the
  committed statement's and a revoke list that drops an entry of the committed one, builds the
  statement, runs `validate_statement` on it, and writes `C:distribution/key_rotation.json`
  atomically.
- `sign_release.py backup-check --backup-key-file` decrypts the file and confirms its public half
  equals the committed backup pin. It prints `signing.fingerprint` only. This is the restore test of
  Q2.
- `check-keys` (no new flag) adds, whenever `release_key.pub.pem` holds a real key:
  `check_release_pins` requires the backup pin to be a real Ed25519 key, different from the main
  key and not in the committed statement's `revokes`; when `key_rotation.json` exists, it must pass
  `validate_statement` and its `main_key` must equal `release_key.pub.pem`. With a placeholder main
  pin (a dev checkout), these checks are skipped and `check-keys` behaves as today.

No new dependency: `cryptography` already reads and writes encrypted PKCS8.

D11. **Installer replace mode and first install (R1-H2, R1-M3).** `install.sh --replace` installs
over an existing home without deleting anything:

1. Without `--replace`, the existing-runtime refusal (`PT:install/install.sh:196-215`) remains and
   its text names `--replace`. With `--replace`, an existing runtime is required. If neither
   `current` nor a version directory exists, the script refuses before fetch with the fixed coded
   line `replace_no_existing_install: no existing Decoy install; run this installer without
   --replace for a normal install`.
2. Before any download, if `trust_state.json` exists, the script derives its pinned key fingerprint
   without `openssl pkey` and without a status-hiding pipeline. It extracts the PEM body to a temp
   file, runs `openssl base64 -d -A` into another temp file, requires exactly 44 bytes, requires the
   first 12 bytes to equal the Ed25519 SPKI prefix `302a300506032b6570032100`, writes the last 32
   bytes to a temp file and hashes that file with the existing `sha256_of`. It requires the result
   to match `^[0-9a-f]{64}$` or dies. It extracts only the `"revoked_keys":[...]` array from
   `trust_state.json` and searches that array for the fingerprint. A match refuses with the exact
   fixed line `decoy install: this installer is out of date; download the latest installer`, with
   zero fetch calls. Every command's status is checked directly, so `set -eu` cannot mistake a
   successful last pipeline command for a failed earlier one. The shell bootstrap cannot import
   Python, so AT-UK1-26 guards this unavoidable cross-language copy by comparing its result with
   `signing.fingerprint` for the same PEM (R2-M3, R2-M4).
3. The shell fast serial refusal (`:285-293`) is skipped in replace mode. It is also skipped in
   normal mode when the canonical document contains the exact token `"key_rotation":"`, because
   the stored serial may belong to the previous epoch. The authoritative epoch-aware check runs in
   `first_install` (R2-L2).
4. `install.sh` passes the document and its signature file to `first_install`, plus `--replace`.

`first_install` (`C:distribution/first_install.py`), under the install lock, runs
`key_rotation.resolve_main_key` on the document bytes and signature, then `check_document_freshness`
with the decision, and records `serial`, `latest`, `key_epoch`, `main_key` and `revoked_keys`. A
fresh install of an installer that pins K2 with a statement for epoch 2 therefore starts with K1
revoked. A corrupt `trust_state.json` remains a refusal in normal mode. In replace mode only, it is
treated as state to recover after the shell has verified the document, bundle, manifest, identity
and native self-check under the replacement installer's pin. `first_install` keeps the corrupt
state bytes unchanged until those checks have passed, derives fresh state from the verified
document and atomically replaces only `trust_state.json`. `settings.json` is never touched. A
verification failure leaves both files byte-identical (R2-L5).

In replace mode it places the bundle at `versions/<v>`, or at a fresh
`versions/<v>+<build>` slot (`installer._fresh_same_version_slot`) when `versions/<v>` exists,
flips `current` and rewrites the launcher. It never removes any retained version. A trust refusal
exits 5 with one fixed line that names the code (`first_install: refused
(upgrade_key_revoked)`); the D6 rule applies, so no exception text from a document is printed. The
offline `DECOY_LOCAL_BUNDLE` install has no document and records nothing, as today. `install.sh` and
`first_install` ship in the same release, so the new argument form is internal to one release.

D12. **Contract rules for later versions (R1-M10).** The contract doc reserves: a later statement
version (`cli-key-rotation/v2`) rides in a new top-level field (for example `key_rotation_v2`), and
documents keep the v1 `key_rotation` field for as long as the v1 backup key is good, so 1.0 installs
keep rotating. A v2 payload placed in `key_rotation` is still refused `upgrade_format_unknown`. A
later `trust_state.json` field never changes the meaning of an existing field and never nests a key
named `serial`.

D13. **One runtime reason-code registry.** `C:distribution/errors.py` owns a closed `TrustCode`
enum for the seven new `upgrade_*` codes in 6.1. `TrustRefusal`, `UnknownFormat` mapping, local
rollback and CLI output consume that enum; no caller repeats the string literals. The AT-UK1-16
AST guard walks `C:` and fails if any exact new code literal appears outside the registry, with the
registry definition as the one named exception. This is the choke point for the cross-cutting
reason-code rule; M54 adds a copied literal in `cli/upgrade.py` and must turn the guard red.

Design principles (architecture.md): one place per fact (rotation schema and checks in
`key_rotation.py`, used by runtime and build host; the state file in `trust_state.py`; fingerprints
in `signing.py`; the error base and reason-code registry in the acyclic `errors.py` leaf; the
document field set in one builder); single-purpose functions; a typed
`TrustDecision` and a typed `TrustRefusal`; no flag argument switches behavior (record versus check
stays the existing `record` keyword, and replace is a separate installer mode). The trust-state move
answers a real change pain: `installer.py` is at 731 lines of an 800 cap, and the state file gains
three fields. Established pattern: TUF root rotation, cut to one key (section 2).

## 4. Behavior

### 4.1 Normal upgrade, no rotation ever

Unchanged. `resolve_main_key` returns the pinned key, epoch 1, an empty revoked set and the stored
serial as the floor. The state file gains `key_epoch: 1` and `revoked_keys: []` on the next
recording write.

### 4.2 First upgrade after a rotation (client pins K1, document signed by K2 with statement)

`decoy upgrade` verifies the statement with B, verifies the document with K2, checks freshness
against a reset floor, downloads the bundle, verifies it with K2, verifies the manifest with K2,
swaps, and records `key_epoch: 2`, `main_key: K2`, `revoked_keys: [fp(K1)]` and the new serial. The
new runtime pins K2. Output is today's "upgraded" line.

### 4.3 Up to date when the rotation arrives

`decoy upgrade` finds no newer version, calls `installer.record_trust` under the lock, records epoch
2, K2 and the revocation, and prints today's "up to date" line. `decoy upgrade --check` makes the
same checks, reports, and writes nothing.

### 4.4 Attack: K1-signed document after the rotation was recorded

The candidate key is the stored K2, so the K1 signature fails. If the running runtime still pins K1,
the refusal is `upgrade_key_revoked`, else `upgrade_signature_invalid`. Exit 3, nothing written.

### 4.5 Attack: leaked K1 pushed the serial to 2^53 before the rotation

The epoch-2 document's statement verifies, the floor resets, the document is accepted, and the state
records epoch 2 with the new, normal serial. If epoch 2 first arrives through the 88-O offline
sidecar, the state records serial 0; the next normal-serial K2 network document is then accepted.

### 4.6 Rollback to a retained runtime signed by K1

Refused `upgrade_rollback_key_rotated` (Q1), or `upgrade_key_revoked` when run from the K1-pinned
runtime itself. Exit 3, `current` unchanged.

### 4.7 1.0 install meets a v2 document

`upgrade_format_unknown`, exit 3, the D6 text. The user runs the latest installer with `--replace`
(4.8).

### 4.8 Recovery with `install.sh --replace`

The installer from the download page pins the current key, verifies the document and the bundle,
and hands both to `first_install`, which checks them against the existing `trust_state.json`, places
the new runtime beside the old ones, flips `current`, and keeps `settings.json`, `trust_state.json`
and every retained version. An installer whose pinned key is revoked in the home refuses before any
download. `--replace` with no existing runtime refuses with `replace_no_existing_install` and points
at the normal install form. If the existing trust state is corrupt, the verified replacement resets
only that file after all replacement verification succeeds; `settings.json` stays byte-identical,
and a failed verification changes neither file.

### 4.9 Owner rotation ceremony (UK3 runbook)

1. On the offline machine: create K2 with `sign_release.py keygen --out K2.key --pub K2.pub`, run
   `sign_release.py backup-check --backup-key-file <B>`, then run
   `sign_release.py rotation --backup-key-file <B> --new-main-pub K2.pub --epoch 2 --revoke-pub K1.pub`.
2. Carry `key_rotation.json` and `K2.pub` (public files only) back. Replace K1 with K2 in the
   `native-release` Environment secret in both the CLI and engine repositories (X6).
3. Commit `C:distribution/key_rotation.json` and the new `release_key.pub.pem`; `check-keys` passes.
4. Cut a release. The version document carries the statement from now on.
5. Re-publish the supported older bundles and their tag-run `version.json` under K2 if they must
   stay installable by `--version` or reachable by CLI-REL `rollback` (Q1, X2); otherwise raise
   `min_supported` to the first K2 release. Re-sign the pinned native companion release's
   `SHA256SUMS.sig` under K2, or re-cut and pin the native companion release under K2, before
   CLI-REL publishes the first post-rotation CLI release (X6).

## 5. Later (1.x or 2.0)

- L1 Threshold signing (two of three keys) for rotation, as `cli-key-rotation/v2` in its own field
  (D12).
- L2 Rotating the backup key itself (Q6), by the same D12 rule.
- L3 The startup notice says when the channel format is unknown.
- L4 `install.sh` and `install.ps1` honor a rotation for a user who runs an old cached script.
- L5 `install.ps1 -Replace`, when WIN-FEAS lifts the Windows target gate.
- L6 V2-LOG follow-up, outside UPGRADE-KEY: `C:distribution/verify_extracted.py:35` accepts
  `expected_public_pem=None` and skips manifest signature verification. Track its callers and close
  it in the later verification-hardening row; this plan removes the `None` route only from
  `installer.py`, not from the helper's public contract.

## 6. Enumerations

### 6.1 Exit paths

All new refusals exit `EXIT_RUNTIME` 3 through `_refuse` (`C:cli/upgrade.py:180-186`), which prints
fixed text plus the exception type and drops the chain. Under-lock refusals arrive as `TrustRefusal`
and keep their own code:

- `upgrade_signature_invalid`: today's text at `C:cli/upgrade.py:113-118`, now with a code.
- `upgrade_key_revoked`: a statement names a revoked key, or the signature verifies only under the
  running runtime's revoked pin (D4 steps 2, 4, 5b; D9).
- `upgrade_rotation_invalid`: the statement fails `verify_envelope` or a D4 step 2 check, names
  another key at the stored epoch, or is present but undecodable in a verified document (D4 step 6).
- `upgrade_rotation_replayed`: statement epoch below the stored `key_epoch`.
- `upgrade_rotation_unavailable`: a statement arrived but this build's backup pin is the placeholder.
- `upgrade_format_unknown`: D6; replaces `upgrade_document_rejected` (`C:cli/upgrade.py:122`) only
  for an unknown `schema_version`.
- `upgrade_rollback_key_rotated`: D9, on the local activation path at `C:cli/upgrade.py:97-103`.
- Unchanged: `upgrade_no_key` exit 1 (`C:cli/upgrade.py:86`), `upgrade_document_stale`,
  `upgrade_endpoint_unreachable`, `upgrade_install_failed` (now only for non-trust install errors).
- `first_install`: trust refusals exit 5 with `first_install: refused (<code>)` (D11).
- `install.sh --replace`: a revoked pinned key exits 1 with the exact D11 out-of-date text and no
  fetch; no existing runtime exits 1 with `replace_no_existing_install`; corrupt trust state is
  reset only by verified `first_install` recovery.
- Signer: `sign_release.py rotation`, `backup-check` and `check-keys` exit 1 with one line per
  problem and print no key material.

### 6.2 Routes

- Network latest upgrade and `--force` reinstall: `resolve_main_key` before the lock for the early
  checks, again inside `install_version` under `_exclusive` (`C:distribution/installer.py:478-488`).
- Pinned `--version` download (`C:distribution/installer.py:518-523`): same key as the latest route.
- Up to date, no install: `installer.record_trust` under the lock records a higher epoch (D4a).
- `--check` (`C:cli/upgrade.py:124-142`): resolve, check freshness with `record=False`, write nothing.
- Local activation (`C:cli/upgrade.py:97-103`, `C:distribution/installer.py:398-441`):
  `key_rotation.local_key(home)` inside `_exclusive`, then D9.
- 88-O offline bundle (`plan/release-chain`, not on main): `local_key(home)` plus the optional
  `PATH.key_rotation` sidecar (D8); whichever of 88-O and UK1c merges second wires it and AT-UK1-28.
- Fresh install by `install.sh` (`PT:install/install.sh:264-270`): unchanged in the shell;
  `first_install` now resolves and records the full decision (D11).
- `install.sh --replace`: D11, including the no-home refusal and verified corrupt-state recovery.
- `install.ps1`: unchanged; the Windows target is gated off and the script neither calls
  `first_install` nor reads trust state. It parses the document with `ConvertFrom-Json`
  (`PT:install/install.ps1:119`), so the extra string field is ignored.
- Startup notice (`C:_update_check.py:117`) and `_key_unresolved` (`C:__main__.py:226`): unchanged.
- Release smoke (`PT:smoke_install.py:481`): verifies with the pinned key; a document with a
  statement naming that key still verifies. Unchanged.

### 6.3 Fields

- Version document v1: optional top-level `key_rotation`, a base64 string of the canonical envelope
  bytes `{alg, payload, signature, public_key}`; `schema_version` unchanged
  (`C:distribution/version_document.py:52`).
- Rotation payload `cli-key-rotation/v1`: `schema_version`, `epoch`, `main_key`, `revokes`, `issued`
  (D2). A missing or unknown schema tag is refused (recurring-defects class 4); extra payload fields
  are ignored.
- `trust_state.json`: adds `key_epoch` (int >= 1, bool refused), `main_key` (PEM, only when
  `key_epoch > 1`) and `revoked_keys` (sorted list of 64-hex strings); `serial` is the current
  epoch's floor and keeps its top-level integer form; an offline epoch rise writes 0; the writer
  asserts its first exact `"serial":` token is that top-level value; `latest` unchanged; unknown
  fields kept unless they would violate that first-serial invariant.
- New pinned file `C:distribution/release_backup_key.pub.pem`; new committed file
  `C:distribution/key_rotation.json` (absent until a rotation); offline sidecar `PATH.key_rotation`.
- `.gitattributes`: `src/decoy/distribution/*.pem -text` and
  `src/decoy/distribution/key_rotation.json -text`, so a Windows checkout cannot rewrite the bytes
  (R1-M11).
- `--json` error object: unchanged shape (`decoy-error-v1`); new `code` values and a `hint` on
  `upgrade_format_unknown`.

### 6.4 FK shapes

N/A: this row changes the update channel and never reads, resolves or masks foreign keys or any
customer data.

### 6.5 Output surfaces

- Human error lines and `--json` error objects of `decoy upgrade` (codes in 6.1, D6 text).
- `first_install` stderr lines and `install.sh --replace` messages, including the exact D11 codes
  and fixed text.
- `trust_state.json` in `DECOY_HOME` (local, not a secret).
- The published `version.json` gains `key_rotation` after the first rotation.
- `sign_release.py` stdout and stderr: file paths and fingerprints only, never a private key.
- Docs: `docs/distribution/key-rotation.md` (new runbook), `docs/distribution/version-endpoint-contract.md`,
  `docs/install.md` (replace mode), and `docs/release/frozen-surfaces.md:23` (the "Version document
  and installer contract" row).

## 7. Class table

| # | Class | Closing structure | Sentry or property test | Mutation that must turn it red |
|---|---|---|---|---|
| 1 | value leak | every new refusal goes through `_refuse` or the fixed `first_install` line with a code and the exception type only; `UnknownFormat` messages are fixed | AT-UK1-16, AT-UK1-9, AT-UK1-24 | M16 put `str(exc)` back in the message; M9 echo the document's `schema_version` |
| 2 | cleanup | a refusal writes nothing: state is written once, after all checks; a refused rotation leaves the state bytes identical; replace mode deletes nothing | AT-UK1-3, AT-UK1-10, AT-UK1-26 | M10 record state on `--check` |
| 3 | state | `trust_state.py` is the one reader and writer; `revoked_keys` grow-only, `key_epoch` max-only, the serial floor per epoch, a no-document epoch rise resets it to 0, unknown fields kept when the first-serial invariant holds | AT-UK1-12, AT-UK1-18, AT-UK1-20, AT-UK1-28, AT-UK1-29 | M12 write the document's revoked list in place of the union; M26 keep the floor across a document epoch change; M41 keep it across an offline epoch change; M50 omit the first-serial assertion |
| 4 | route | every key choice goes through `key_rotation` (D8); network, pinned, force, up to date, check, local, offline, first install and replace routes enumerated in 6.2 | AT-UK1-14, AT-UK1-13, AT-UK1-23, AT-UK1-28 | M14 the guard scans only `distribution/`; M13 local activation without the revocation diagnosis |
| 5 | referential | a statement names keys by fingerprint; the new main key must differ from the backup key and must not be revoked; `revokes` is cumulative; an equal epoch names the stored key | AT-UK1-5, AT-UK1-22, AT-UK2-5 | M5 drop the main-differs-from-backup check; M28 accept another key at the stored epoch |
| 6 | untrusted input | the pre-verify parse is capped at 64 KiB and only extracts the envelope; nothing is trusted until `verify_envelope` passes against the pinned backup key | AT-UK1-4, AT-UK1-15, AT-UK1-27 | M4 verify against the envelope's embedded key; M15 drop the size cap |
| 7 | TOCTOU (check-then-use) | `install_version`, `record_trust`, `activate_local_version` and `first_install` resolve the trust decision inside the lock, after re-reading the state; no key parameter exists to pass a stale one | AT-UK1-11, AT-UK1-25 | M11 pass the pre-lock decision into `install_version` |
| 8 | weak test | rotation tests use real Ed25519 keys, real signatures and the real `decoy upgrade` command; no verifier is mocked; the drill asserts the revoked set exactly | AT-UK2-5 | M23 make `revokes` hold only the last key |
| 9 | refactor | the trust-state move out of `installer.py` keeps behavior: corrupt state refused, absent state is a first run, `install.sh` still reads `serial` | AT-UK1-18 | M18 nest `serial` so `install.sh`'s top-level read misses it |
| 10 | frozen surface | version document stays `cli-version-document/v1` with one optional opaque string; `cli-key-rotation/v1` is new and closed; later versions use new fields (D12); all enter the frozen-surface map before REL-GATE G3 | AT-UK1-19, AT-UK1-21, AT-UK3-1 | M19 bump `schema_version` when `key_rotation` is present; M27 emit the statement as a nested object |

## 8. Acceptance tests (red first)

Each test is written first and fails on the base head for the reason given ("guard" means it passes
on base and pins behavior the slice must keep). The first UK1a test support is one fixture that
creates ephemeral Ed25519 keys K1, K2, K3 and backup B, then monkeypatches the module-level
`release_key._KEY_FILE`, the new backup-key path and the path read by
`key_rotation.committed_statement()`. Every rotation AT and the drill use that fixture. The
`DECOY_RELEASE_PUBKEY_FILE` and `DECOY_RELEASE_BACKUP_PUBKEY_FILE` seams remain covered for
placeholder dev builds only; no release-path test depends on them, so committing real pins cannot
turn the suite red (R2-H3). A builder may add tests, never weaken these. Every mutation runs on the
final head and the record names that head (recurring-defects class 9). 45 acceptance rows: 33 in UK1
(AT-UK1-28 owned by whichever of UK1c and 88-O merges second), 8 in UK2, 3 in CLI-REL and 1 docs;
mutations M1 to M40 are retained and new mutations continue M41 to M54.

Windows (R1-M11): AT-UK1-11 depends on a real install lock, which Windows lacks until WIN-FEAS CW1
(`C:distribution/lock.py:50-52` yields with no lock); on Windows it is skipped with that reason until
CW1 merges. AT-UK1-18, AT-UK1-19, AT-UK1-21, AT-UK1-24 and AT-UK1-26 run `install.sh` and are
POSIX-only (`install.ps1` has no trust state, no `first_install` call and a gated target). All other
rows run on both.

### 8.1 UK1 (CLI trust core)

| ID | Slice | Test | Red on base because | Mutation |
|---|---|---|---|---|
| AT-UK1-1 | UK1c | Guard: a K1-signed document with no statement upgrades as today; a K2-pinned build accepts a K2-signed document whose statement names K2 | guard | M1 require the signer to differ from the pinned key whenever a statement is present |
| AT-UK1-2 | UK1c | Client pins K1; a K2-signed document carries a B-signed statement (epoch 2, main K2, revokes K1); a K2-signed bundle installs; state holds `key_epoch: 2`, `main_key` K2, `revoked_keys: [fp(K1)]` and the serial | signature invalid today | M2 verify the bundle with the pinned key instead of the resolved key |
| AT-UK1-3 | UK1c | After AT-UK1-2, the client still pinning K1 (in-process) gets a fresh-serial K1-signed document with no statement: refused `upgrade_key_revoked`; state and `current` byte-identical | K1 is still trusted | M3 read revocations from the document only, not from state |
| AT-UK1-4 | UK1b | A statement signed by K1, by K2 or by an unrelated key, or with B's public key embedded but a forged signature, is refused `upgrade_rotation_invalid`; nothing written | no rotation code | M4 verify against the envelope's embedded key |
| AT-UK1-5 | UK1b | A statement whose `main_key` is B, whose `main_key` is in `revokes`, with empty `revokes`, with `epoch` 1 or `true`, or with a fingerprint plus `"\n"` or in upper case, is refused `upgrade_rotation_invalid` | no rotation code | M5 drop the main-differs-from-backup check |
| AT-UK1-6 | UK1b | With stored `key_epoch: 3`, a valid epoch-2 statement is refused `upgrade_rotation_replayed`; an epoch-3 statement naming the stored key is accepted | no epoch | M6 skip the epoch comparison |
| AT-UK1-7 | UK1c | A K1-signed document carrying a valid statement that revokes K1, read by a K1-pinned client, is refused `upgrade_key_revoked` | K1 signature passes today | M7 verify with the pinned key first and accept on success |
| AT-UK1-8 | UK1c | Backup pin is the placeholder: a document with a statement is refused `upgrade_rotation_unavailable`; one without a statement upgrades | no backup pin | M8 skip the statement and use the pinned key when the backup is the placeholder |
| AT-UK1-9 | UK1c | A trusted-key-signed document with `schema_version` `cli-version-document/v2`, a bad-signature document with that schema, and a statement with `cli-key-rotation/v2` each exit 3 with `upgrade_format_unknown` and exactly the D6 human and `--json` text; a document with no `schema_version` still gives `upgrade_document_rejected` | prints "version document rejected: ValueError" | M9 echo the document's `schema_version` in the message (the test plants a marker string there) |
| AT-UK1-10 | UK1c | `decoy upgrade --check` across a rotation reports and leaves `trust_state.json` absent or byte-identical | no rotation | M10 record state on `--check` |
| AT-UK1-11 | UK1c | Process A records epoch 3 (revokes K1 and K2) between process B's pre-lock resolve (epoch 2, main K2) and B's `install_version`; B refuses `upgrade_key_revoked`. The test wraps `installer.install_version` with monkeypatch so the wrapper runs A to completion, then calls through; no production hook (R1-L5). Skipped on Windows until CW1 | no rotation | M11 pass the pre-lock decision into `install_version` |
| AT-UK1-12 | UK1a | `key_epoch` non-int, bool, 0 or negative; `revoked_keys` non-list or non-hex; revoked keys at epoch 1; epoch 2 without a loadable `main_key` or with a revoked one: each refused as unreadable state. Absent fields read as epoch 1 and an empty set; a write after an epoch-2 decision over a state with an extra revoked fingerprint keeps both | fields do not exist | M12 write the document's revoked list in place of the union |
| AT-UK1-13 | UK1c | Retained slot signed by K1, runtime pins K2, state epoch 2: `decoy upgrade --version <old>` refuses `upgrade_rollback_key_rotated`, `current` unchanged; with a runtime pinning K1 and K1 revoked in state, local activation of the same slot refuses `upgrade_key_revoked` | generic activation failure | M13 activate with the stored key without the revocation diagnosis |
| AT-UK1-14 | UK1c | Guard `CT:sentry/release/test_key_choke_point.py` fails on seeded code in a scratch copy: `release_key.pinned_public_pem()` in `cli/upgrade.py`; `import decoy.distribution.release_key as rk; rk.pinned_backup_pem()` in `distribution/installer.py`; `from decoy.distribution.release_key import pinned_backup_pem as p`; `f = release_key.pinned_public_pem` with no call; a string `"release_backup_key.pub.pem"` in `distribution/layout.py`. Passes on the tree with only `__main__._key_unresolved` excepted | guard does not exist | M14 the guard scans only `distribution/` |
| AT-UK1-15 | UK1b | A 64 KiB plus 1 byte document and a 10,000-deep nested document reach the signature check with no statement and refuse `upgrade_signature_invalid`; a spy shows `json.loads` was not called on the oversize bytes | no pre-verify parse | M15 drop the size cap |
| AT-UK1-16 | UK1c | Every new code, human and `--json`: output matches `decoy-error-v1`, contains the code, and contains no PEM line, no fingerprint, no URL other than `DOWNLOAD_PAGE_URL`, and no exception message; each raised error has `__cause__` and `__context__` None. An AST guard finds every exact new code literal only in `errors.TrustCode` and fails on a copy elsewhere | codes do not exist | M16 put `str(exc)` back in the message; M54 copy a new code literal into `cli/upgrade.py` |
| AT-UK1-17 | UK1a | `DECOY_RELEASE_BACKUP_PUBKEY_FILE` is honored with a warning while both pins are the placeholder; ignored with a warning when a real backup key is committed; ignored with a warning when the backup is the placeholder but the main pin is real (the test copies the module with real pems) | override does not exist | M17 honor the override whenever the backup pin is the placeholder |
| AT-UK1-18 | UK1a | Guard after the move: corrupt state refused, absent state a first run, serial replay refused; `install.sh` under `sh` reads `serial` from a state file written by the new writer (with `main_key` and `revoked_keys` present) and refuses a lower serial; the writer refuses output whose first exact `"serial":` token would be nested instead of its top-level value | guard (the refactor) | M18 nest `serial` under an object; M50 omit the first-serial assertion |
| AT-UK1-19 | UK1d | A v1 document with `key_rotation` installs through `install.sh` (pinned K2) unchanged, and the built wheel lists `decoy/distribution/release_backup_key.pub.pem` | backup pem absent | M19 bump `schema_version` when `key_rotation` is present |
| AT-UK1-20 | UK1c | R1-B2: client pins K1; a K1-signed document with serial 2^53 is accepted and recorded; then a K2-signed epoch-2 document with serial 1,000 is accepted; state holds `key_epoch: 2` and `serial: 1000`; a later epoch-2 document with serial 999 is refused `upgrade_document_stale` | the global floor refuses serial 1,000 | M26 keep the floor across the epoch change |
| AT-UK1-21 | UK1d | R1-B1, R2-L2: the real `install.sh` under `sh`, pinning K2, installs from a document whose `key_rotation` carries an epoch-2 statement as built by `vd.build_document`; the test asserts `install.sh` read `schema_version`, `serial`, `expires` and `latest` from the top level and skipped the non-replace shell serial fast check because the exact canonical `"key_rotation":"` token was present | field does not exist | M27 emit the statement as a nested object (`install.sh` then refuses the schema); M49 run the old serial fast check despite the statement |
| AT-UK1-22 | UK1c | R1-M1: after epoch 2 is recorded, a K1-pinned client accepts a K2-signed document with no statement; an epoch-2 statement naming K3 is refused `upgrade_rotation_invalid` and changes nothing | main key not stored | M28 accept another key at the stored epoch |
| AT-UK1-23 | UK1c | R1-M2: a client on the latest version runs `decoy upgrade` across a rotation; state records epoch 2, K2 and the revocation under the lock; the same run with `--check` writes nothing | `record=False` on that path | M29 keep `record=False` on the up-to-date path |
| AT-UK1-24 | UK1d | R1-M3: `first_install` given a document with an epoch-2 statement and its signature records `serial`, `latest`, `key_epoch: 2`, `main_key` and `revoked_keys`; a revoked or stale document exits 5 with `first_install: refused (<code>)` and no document value on stderr | records only `latest` and `serial` | M30 `first_install` parses and records without the resolver |
| AT-UK1-25 | UK1c | R1-M4: a `TrustRefusal` raised under the lock in `install_version` is emitted with its own code, not `upgrade_install_failed`; `inspect.signature` of `install_version` and `activate_local_version` has no `expected_public_pem` | parameters exist; all errors map to `install_failed` | M31 map `TrustRefusal` to `upgrade_install_failed` |
| AT-UK1-26 | UK1d | R1-H2, R2-M3, R2-M4, R2-L5, end to end on an existing home (`settings.json`, epoch-2 `trust_state.json`, `current`): the D6 output names `--replace`; `sh install.sh --replace` from an installer pinning K2 installs the new runtime, flips `current`, and leaves settings byte-identical and the revoked set intact. On stock macOS LibreSSL and Linux, an installer pinning revoked K1 derives the fingerprint by the D11 44-byte SPKI path, equal to `signing.fingerprint` for the same PEM, makes zero fetch calls, changes nothing and emits exactly `decoy install: this installer is out of date; download the latest installer`; a same fingerprint planted outside `revoked_keys` does not match. Without `--replace` the refusal text names it. `--replace` with no existing runtime makes zero fetches and emits the exact `replace_no_existing_install` line. With corrupt trust state, a verification fault leaves state and settings byte-identical; a verified replacement atomically resets only state and keeps settings byte-identical | replace mode does not exist | M32 skip the revoked-pin check; M46 accept a wrong SPKI length or prefix; M47 fetch before the revoked check or change its text; M51 allow replace on no home; M52 reset corrupt state before verification |
| AT-UK1-27 | UK1b | R1-L9: a document signed by the trusted key whose `key_rotation` is a number, a list, invalid base64, or base64 of a non-object, is refused `upgrade_rotation_invalid` after verification; nothing written | field ignored | M33 treat a present but undecodable field as absent |
| AT-UK1-28 | UK1c or 88-O | R1-M5, R2-H1: a K1-pinned client first records a K1 document at serial 2^53, then `decoy upgrade --bundle PATH` with a K2-signed bundle and `PATH.key_rotation` records epoch 2 with serial 0. A later normal-serial K2 network document is accepted and records its serial. Without the sidecar the offline install refuses `upgrade_signature_invalid`; a sidecar signed by K1 refuses `upgrade_rotation_invalid` | no offline route on main | M34 the offline route ignores the sidecar; M41 keep the K1 serial floor on the offline epoch rise |
| AT-UK1-29 | UK1a | R1-M8: a state file with an extra top-level field `future_field` keeps it byte-equal after a recording write | writer rebuilds the object | M35 drop unknown fields on write |
| AT-UK1-30 | UK1b | R1-B3, R1-L6, R2-M6: with a committed statement, `vd.build_document` sets `key_rotation` to the base64 of the committed bytes, equal as a string; a committed statement that fails against the backup pin makes the builder raise; with no committed file the field is absent; `build_document(**fields)` where `fields` contains `key_rotation` raises `TypeError` | builder has no field | M36 add a `key_rotation` keyword escape hatch or embed without verifying |
| AT-UK1-31 | UK1a | R2-H3, R2-M5: after the real-pin monkeypatch fixture lands, `keygen --encrypt` writes `ENCRYPTED PRIVATE KEY` PKCS8 that loads only with the passphrase, and `backup-check` prints only the fingerprint when the file's public half equals the patched committed backup pin and exits 1 otherwise | commands do not exist | M44 make the fixture patch only environment seams or make `backup-check` use the unpatched installed pin |
| AT-UK1-32 | UK1a | R2-M1: importing `installer`, `version_document` and `key_rotation` in both fresh-process orders succeeds; `key_rotation.TrustRefusal` is an `errors.InstallError`; `installer.InstallError is errors.InstallError`; an import-graph assertion shows `errors.py` imports no distribution module | cycle appears when the planned imports are added without the leaf | M45 make `key_rotation` import `InstallError` from `installer` |
| AT-UK1-33 | UK1b | R2-L1: `build_document` accepts canonical output of exactly 32 KiB and refuses 32 KiB plus 1 before signing or writing | no builder cap | M48 omit the 32 KiB bound |

### 8.2 UK2 (signer tools and drill)

| ID | Test | Red on base because | Mutation |
|---|---|---|---|
| AT-UK2-1 | `sign_release.py rotation --backup-key-file B.enc --new-main-pub K2.pub --epoch 2 --revoke-pub K1.pub` (passphrase through a patched `getpass`) writes `key_rotation.json` that `key_rotation.validate_statement` accepts against B's public key | subcommand does not exist | M20 load the key through `load_private_key()` (the CI environment path) |
| AT-UK2-2 | `rotation` refuses: the key given only by `DECOY_RELEASE_KEY_PEM`, a new main key equal to B, an empty revoke list, an epoch not above the committed statement's, a revoke list missing an entry of the committed statement; stderr carries no key text | not built | M21 accept a new main key equal to the backup |
| AT-UK2-3 | `make_version_document.py` output carries the committed statement through `build_document` (string-equal, R1-L6) and omits the field when none is committed | not built | M22 `make_version_document.py` strips `key_rotation` before writing |
| AT-UK2-4 | `check-keys` fails on a committed statement whose `main_key` differs from `release_key.pub.pem` and on one that fails `validate_statement`; passes on a consistent set | checks `install.sh` only | M24 skip the statement cross-check |
| AT-UK2-5 | Drill with real keys and the real `decoy upgrade` command over a file-backed fetch: client 1 (pins K1) goes epoch 1 to 2 to 3; client 2 (pins K1, never saw epoch 2) goes straight to epoch 3. Both then refuse a K1-signed and a K2-signed document. Client 2's `revoked_keys` equals exactly `{fp(K1), fp(K2)}`; client 2's retained K1-pinned runtime, asked to activate its K1-signed slot, refuses with `upgrade_key_revoked` (R1-M6) | not built | M23 make `revokes` hold only the last key |
| AT-UK2-6 | R1-H1: with a real main pin and no flag, `check-keys` fails on a placeholder backup pin, a backup that is not Ed25519, a backup equal to the main key, and a backup listed in the committed `revokes`; with a placeholder main pin it behaves as today | no backup check | M37 run the backup checks only behind a flag |
| AT-UK2-7 | R1-M9, Q2: `rotation` refuses an unencrypted backup file created by plain `keygen`; the encrypted generation and restore checks already shipped in AT-UK1-31 | not built | M38 accept an unencrypted backup file |
| AT-UK2-8 | R1-M7: AST sentry: the exact string constants equal to `cli-key-rotation/v1`, `revokes` and `epoch` are read only in `C:distribution/key_rotation.py`; matching uses constant equality, never substring containment, so unrelated strings containing those words do not count. `sign_release.py` and `make_version_document.py` import `validate_statement` and `check_release_pins` from it | second copy exists | M39 add an exact `epoch` check in `sign_release.py`; M53 change the sentry to substring matching and seed an unrelated containing string |

### 8.3 Cross-plan (CLI-REL S0)

| ID | Test | Red on base because | Mutation |
|---|---|---|---|
| AT-XR-1 | R1-B3, R1-H1: `candidate.verify_release_set` refuses a set whose `version.json` lacks `key_rotation` while one is committed, carries one that is not string-equal to `committed_statement()`, or carries one when none is committed; and refuses a set whose wheel pins fail `check_release_pins`. Built in CLI-REL S0 | function is on the CLI-REL branch only | M40 skip the statement comparison in `verify_release_set` |
| AT-XR-2 | R2-H2, resign route: after K2 and its statement are committed, `sign-doc resign` reads a K1-signed live document at serial N through the X5 previous-epoch trust input, emits serial greater than N, carries `key_rotation` string-equal to `committed_statement()` and signs the output with K2. The assertion is on `sign-doc` output before `verify_release_set` | CLI-REL verifies the live document only with the committed K2 and has no rotation statement | M42 verify the live document only with K2 or copy its missing or stale statement into the output |
| AT-XR-3 | R2-H2, rollback route: after K2 and its statement are committed, `sign-doc rollback --latest X` reads the K1-signed live serial and the permitted previous-epoch tag document through X5, emits a higher-serial K2-signed output whose `key_rotation` is string-equal to `committed_statement()` and whose rollback fields are correct. The assertion is on `sign-doc` output before `verify_release_set` | CLI-REL verifies both source documents only with the committed K2 and has no rotation statement | M43 verify a source only with K2 or omit the committed statement from rollback output |

### 8.4 UK3 (docs)

| ID | Test | Red on base because | Mutation |
|---|---|---|---|
| AT-UK3-1 | Docs check: `docs/distribution/key-rotation.md` exists with `Status: current` and the five ceremony steps of 4.9; `version-endpoint-contract.md` names `key_rotation` as an opaque base64 string, `cli-key-rotation/v1`, the unknown-format rule and the D12 rules; `docs/install.md` documents `--replace`; the frozen-surface row lists the field, the statement schema and the `trust_state.json` fields | docs do not exist | M25 drop `key_rotation` from the contract doc |

## 9. Reuse inventory

- Verification: `signing.verify_envelope` (statement) and `signing.verify_detached` (document,
  bundle). No new verifier, no new crypto library.
- Key bytes and identity: `signing.raw_public_bytes` (renamed from
  `_raw_public_bytes_from_pem`) and `signing.fingerprint` beside it.
- Key pin rules and dev override: the pattern of `release_key.pinned_public_pem`.
- Freshness and replay: `installer.check_document_freshness`, `vd.check_fresh`, the `serial` rule.
- Atomic state write: `C:_atomic.py` `write_atomic` (already used for the state file).
- Lock: `installer._exclusive` and `C:distribution/lock.py`.
- Repair slot: `installer._fresh_same_version_slot` for replace mode.
- Error output: `_refuse` and `emit_error` (`decoy-error-v1`, its existing `hint`).
- Signer: `sign_release.py` `keygen`, `sign_bytes`, `_write_atomic`, `check-keys`;
  `make_version_document.py`; the single builder `vd.build_document`.
- Test seams: the UK1a real-pin fixture in existing `CT:conftest.py` patches the two module-level pin paths and the
  `committed_statement()` path; the environment overrides remain dev-build coverage only. Also
  reuse the injected downloader in `install_version` and the existing upgrade e2e harness
  (`CT:e2e/test_upgrade_error_text.py`). About 38 test call sites in
  `CT:unit/test_distribution.py`, `CT:unit/test_distribution_acceptance.py` and
  `CT:unit/distribution/test_bundle_base.py` move from `expected_public_pem=` to the module-path
  fixture.

## 10. Frozen contracts touched

- `cli-version-document/v1`: one optional field, `key_rotation`, an opaque base64 string. Additive;
  v1 readers already ignore unknown fields, and the string form keeps `install.sh`'s grep readers
  correct. Writers refuse canonical documents over 32 KiB; readers retain their 64 KiB cap. Must
  merge before REL-GATE G3 freezes the "Version document and installer contract" row
  (`docs/release/frozen-surfaces.md:23`).
- New `cli-key-rotation/v1`: frozen from 1.0. A later version rides in a new field (D12); a v2 payload
  in `key_rotation` gets `upgrade_format_unknown` from 1.0 installs.
- `trust_state.json`: three additive fields; `serial` keeps its top-level integer form for
  `install.sh` and becomes the per-epoch floor; an offline epoch rise writes 0; unknown fields are
  kept only when the first exact `"serial":` remains top-level; no later field may nest `serial`.
- `install.sh`: one new option, `--replace`, with the D11 no-home refusal and corrupt-state recovery
  semantics. The `first_install` argument form is internal to one release.
- Exit codes: none added or changed. Error codes: seven new `code` values; the `--json` error shape
  is unchanged.
- Engine contract: not touched. Nothing in this row reaches the engine, so there is no 2.0 item.

## 11. Placement (checked against CLI CODEMAP "Where Things Go")

| New file | Directory | Basis | Neighbor |
|---|---|---|---|
| `key_rotation.py` | `C:distribution/` | CODEMAP row "Shipped install and update" (`CODEMAP.md:64`); 14 direct Python modules today, 17 after the three new modules, under the fan-out limit of 25; 15 total entries today and 20 after the two data files | `release_key.py` |
| `trust_state.py` | `C:distribution/` | same row; takes code out of `installer.py` (731 lines, cap 800) | `installer.py` |
| `errors.py` | `C:distribution/` | same row; acyclic leaf for the install refusal and closed runtime reason-code registry shared by `installer`, `version_document`, `key_rotation` and the CLI | `installer.py` |
| `release_backup_key.pub.pem` | `C:distribution/` | same row; shipped in the wheel like `release_key.pub.pem` | `release_key.pub.pem` |
| `key_rotation.json` (after the first rotation only) | `C:distribution/` | same row; read by `vd.build_document`, which cannot import `PT:` | `release_backup_key.pub.pem` |
| `.gitattributes` (new) | repo root | git attributes for byte-exact key files | none |
| `test_key_rotation.py`, `test_trust_state.py`, `test_upgrade_rotation.py`, `test_sign_release_rotation.py`, `test_first_install_trust.py` | `CT:unit/distribution/` | CODEMAP: "new tests go in `tests/unit/distribution/`" | `test_sign_release_sshsig.py` |
| `test_key_choke_point.py`, `test_rotation_single_validator.py`, `test_rotation_reason_codes.py` | `CT:sentry/release/` | CODEMAP sentry row: release-gate and release-path fitness functions live here | `test_frozen_surface_map.py` |
| `test_rotation_drill.py`, `test_install_replace.py` | `CT:e2e/` | end-to-end command tests | `test_upgrade_error_text.py` |
| `key-rotation.md` | `docs/distribution/` | distribution docs | `version-endpoint-contract.md` |

## 12. Slices

Sizes are production and test lines. Every slice is under 800 lines and 10 production files (R1-L1).
Commits: Conventional Commits subject at most 72 characters, short or no body, final line `cam`,
author `ckeep <decoy@trydecoy.com>`, no other trailers. Test depth: T0 per edit, T1 per commit, T2 at
the gate on the exact head with the slice's mutations. UK1a moves code and touches the state
contract, UK1c removes public parameters used by many tests, UK1d changes `install.sh`: each
escalates to the full suite at the slice (testing.md triggers). UK1b and UK2 run T1 plus T2.

| Slice | Repo | Content | Prod / test | Risk | Depends on |
|---|---|---|---|---|---|
| UK1a | CLI | H3 fixture first; `errors.py` leaf and installer re-export; `trust_state.py` (moved reader and writer, three fields, no-document epoch reset, first-serial assertion, unknown fields kept when safe); `release_key.pinned_backup_pem` and placeholder pem; `signing.raw_public_bytes` rename plus `fingerprint`; `sign_release.py keygen --encrypt` and `backup-check`; `.gitattributes`. AT-UK1-12, 17, 18, 29, 31, 32 | 225 / 390 | R2 | none (main). Rebase onto 47-B if it merges first |
| UK1b | CLI | `key_rotation.py` (decode, `validate_statement`, `check_release_pins`, `resolve_main_key`, `local_key`, `committed_statement`, `TrustDecision`, `TrustRefusal`); `vd.UnknownFormat`, `DOWNLOAD_PAGE_URL`, `build_document` embed and 32 KiB cap. AT-UK1-4, 5, 6, 15, 27, 30, 33 | 235 / 380 | R2 | UK1a |
| UK1c | CLI | `install_version`, `activate_local_version`, new `record_trust` resolve under the lock and lose `expected_public_pem`; `cli/upgrade.py` codes, `_refuse` hint, up-to-date recording; the choke-point guard; test call-site migration. AT-UK1-1 to 3, 7 to 11, 13, 14, 16, 20, 22, 23, 25 (and expanded AT-UK1-28 if 88-O is merged) | 155 / 560 | R2 | UK1b. If 88-O merges first, UK1c wires its key and AT-UK1-28; else 88-O does |
| UK1d | CLI | `install.sh --replace`, portable SPKI fingerprint, exact revoked-array check, epoch-aware shell serial skip, no-home refusal; `first_install` resolver, recording, corrupt-state recovery and replace placement. AT-UK1-19, 21, 24, 26 | 155 / 390 | R2 | UK1c |
| UK2 | CLI | `sign_release.py rotation`; `check-keys` pin checks; `make_version_document.py` through the builder; the exact-constant single-validator sentry; the rotation drill. AT-UK2-1 to AT-UK2-8 | 120 / 330 | R2 (handles the backup private key) | UK1d |
| UK3 | CLI | `docs/distribution/key-rotation.md` runbook including X6; contract doc with D12; frozen-surface row; `docs/install.md` replace modes and the unknown-format message; readiness item "backup key pinned" pointing at `check-keys`; roadmap row and shipped log. AT-UK3-1 | docs about 240 / 50 | R1 | UK2 |
| OWNER-1 | owner | Create the backup key offline with UK1a's `keygen --encrypt` (Q2), keep two copies, run UK1a's `backup-check` on each, hand over the public PEM; commit it (a one-file change, R1) | 3 | owner | UK1a and its H3 fixture; before 2026-11-28 and the first signed 1.0 candidate (CLI-REL S0) |

Totals: about 890 production lines, 2,100 test and docs-check lines and 240 doc lines; about 3,230
lines. Largest slice UK1c at 715. Every implementation slice remains below 800 lines.

Dated targets: UK1a merged by 2026-11-23, UK1b by 2026-11-25, UK1c by 2026-11-27, UK1d by
2026-11-29, UK2 by 2026-12-01, UK3 by 2026-12-02, all before REL-GATE G3 freezes the
version-document contract. OWNER-1 by 2026-11-28 (Q3).

Cross-plan lines (each needs a line in the other plan when that slice is built):

- X1 CLI-REL S0 (required, R1-B3, R1-H1): `sign-set`, `resign` and `rollback` build every document
  through `vd.build_document` (never by copying a live dict to the wire), and
  `candidate.verify_release_set` adds the D7 statement check and `check_release_pins` on the
  wheel's pins. AT-XR-1 (M40) is the test. S0 also runs `check-keys`.
- X2 CLI-REL rollback (R1-L10): `rollback --latest X` verifies `vX`'s tag-run `version.json` with the
  committed key (`origin/plan/cli-rel` plan line 317). After a rotation, a pre-rotation `vX`
  document was signed by a revoked key and fails. The CLI-REL plan must state that rollback across a
  rotation needs `vX`'s document re-signed under the new key (runbook step 5) or is refused.
- X3 WIN-FEAS (R1-M11): CW3 depends on CW1, since the TOCTOU guarantees of this row and of CW3 need a
  Windows lock (`C:distribution/lock.py:50-52`). WIN-FEAS runs the non-POSIX-only rows of section 8
  on Windows (AT-CW3-4) after UK1c and CW1.
- X4 release-chain 88-O (R1-M5): AT-UK1-28 and the sidecar wiring belong to whichever of 88-O and
  UK1c merges second.
- X5 CLI-REL `sign-doc` and `publish` (required, R2-H2, R2-M6): across a rotation, every mode reads
  the live document's serial through `key_rotation.resolve_main_key` with the committed pins and a
  previous-epoch trust state, or through an explicit previous-main-key input that the rotation
  runbook supplies and the mode validates. It must not verify the K1-signed live document only with
  newly committed K2. `resign` and `rollback` build through `vd.build_document`; AT-XR-2 (M42) and
  AT-XR-3 (M43) assert each mode's signed output directly, while AT-XR-1 remains the release-set
  verifier guard.
- X6 CLI-REL and engine native release (required, R2-H2): rotation runbook step 2 replaces the
  `native-release` signing secret in both repositories with K2. Step 5 re-signs the pinned native
  companion release's `SHA256SUMS.sig` under K2, or re-cuts and pins the native companion release
  under K2, before the first post-rotation CLI publish. CLI-REL's companion verification
  then uses the K2 committed pin it already shares with the engine repository.

## 13. Owner questions

Recommended answer first in each. Dennis round 1 recommended (a) on all six.

- **Q1 Rollback across a rotation.** (a) Recommended: refuse with `upgrade_key_revoked` from a runtime whose pin is revoked, else `upgrade_rollback_key_rotated`; re-publish supported old bundles and tag documents under K2. (b) Keep K1 valid for local activation, which needs another trust class and weakens revocation.
- **Q2 Backup key custody.** (a) Recommended: create passphrase-encrypted PKCS8 with `keygen --encrypt` offline, keep two USB copies and a separate passphrase, run `backup-check` at creation and yearly, commit only the public half, never use B in CI. (b) Hardware token: stronger but needs cost and PKCS#11 work. (c) Paper: restore risk.
- **Q3 Deadline for the backup key.** (a) Recommended: 2026-11-28, after R2-M5 lands the H3 fixture then UK1a `keygen --encrypt` and `backup-check`, before the first signed 1.0 candidate. A real main pin with a placeholder backup fails `check-keys`, with no G0 exception. (b) Any date after UK1a and before CLI-REL S0.
- **Q4 Download page.** (a) Recommended: `https://trydecoy.com/download`, the `DOWNLOAD_PAGE_URL` constant, with the `--replace` command. RW-C2b changes it if REL-WEB Q1 changes the domain. (b) Install docs.
- **Q5 Unknown format with an unverifiable signature.** (a) Recommended: fixed `upgrade_format_unknown` text for any non-v1 `cli-version-document/` schema because it adds no capability beyond channel denial. (b) Always show signature invalid.
- **Q6 Backup-key rotation.** (a) Recommended: later statement version in a new field per D12, while v1 remains until B is bad; loss or leak means website reinstall with `--replace`. (b) Add `backup_key` to v1 now, increasing frozen scope.

## 14. Pre-mortem

- **Backup key absent or leaked.** Missing B fails every candidate through `check-keys`; Q3 and OWNER-1 schedule it. A leaked B plus channel control needs offline encrypted custody and website reinstall (Q2, Q6).
- **Client never sees rotation.** Leaked K1 can serve a fresh K1 document until the client receives the statement, the same limit as TUF; D5 prevents a high serial from extending that block afterward.
- **Statement omitted.** D7's builder plus AT-UK1-30, AT-UK2-3 and AT-XR-1 to AT-XR-3 catch missing or stale statements.
- **CLI-REL source documents still use K1.** X2 handles old rollback documents; X5 resolves the K1 live serial after K2 commit and directly tests resign and rollback output.
- **Native companion still uses K1.** X6 rotates the engine secret and re-signs or re-cuts the pinned companion before K2 publish.
- **Pre-verify parse abused.** The cap and extract-only behavior are covered by AT-UK1-15 and AT-UK1-27.
- **Replace misused.** Existing-home, verification-before-reset and pre-fetch revoked-pin rules are covered by AT-UK1-26.
- **Size or rebase drift.** Trust-state extraction keeps `installer.py` under 800; UK1c rebases if 47-B restructures it first.
- **First real ceremony surprises.** AT-UK2-5 drills real keys through the real command first.

## 15. Done when

- [ ] UK1a to UK1d, UK2 and UK3 are merged with their acceptance tests and mutations recorded on the
      exact merge heads.
- [ ] The frozen-surface map lists `key_rotation`, `cli-key-rotation/v1`, the D12 rules and the
      state fields before REL-GATE G3.
- [ ] CLI-REL and the engine runbook carry cross-plan lines X1, X2, X5 and X6, with AT-XR-1,
      AT-XR-2 and AT-XR-3. Release-chain and WIN-FEAS carry X3 and X4 at their owning slices.
- [ ] OWNER-1 is done: the real backup public key is committed and `check-keys` passes on the 1.0
      candidate.
- [ ] The runbook is in `docs/distribution/key-rotation.md`.
- [ ] Roadmap row UPGRADE-KEY closed and the shipped log current.

## 16. Not verified by this plan

- No code ran for this plan. Line numbers come from reading `origin/main` at `ccc5540a` and the plan
  branches named in Bases.
- The size of a version document with a base64 statement (estimated under 4 KiB, far under the
  64 KiB cap).
- That CLI-REL S0 adopts X1, X2, X5 and X6; this plan only records them.
