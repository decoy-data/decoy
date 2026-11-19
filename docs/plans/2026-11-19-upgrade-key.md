Status: plan

# UPGRADE-KEY: update-channel key rotation (roadmap row UPGRADE-KEY)

Owner: Cam. Author: Opus planner. Date: 2026-11-19. Revision 1.

Rules consulted: `dev-rules/README.md`, `00-universal.md`, `risk-and-exceptions.md`,
`development-loop.md`, `feature-dev.md`, `api-and-compatibility.md`, `security.md`,
`release-and-rollback.md`, `config-secrets-and-supply-chain.md`, `testing.md`,
`cross-cutting-concerns.md`, `architecture.md`, and `catalogs/recurring-defects.md`; owner memory
rules: V1 bar, PLAN defines acceptance tests, sentry over prose, root cause not patch, commit message
standard, test depth T0 to T4, one test runner per box, no em-dashes.

Bases: CLI `origin/main` at `c5a156a8`, read from the fresh worktree `wt-plan-upgrade-key`.
Notation: `C:` is CLI `src/decoy/`, `PT:` is CLI `packaging_tools/`, `CT:` is CLI `tests/`.

Plans this one builds on: `plan/cli-rel` (row 94, `release.yml`, S0 with its `publish`, `resign` and
`rollback` modes), `plan/release-chain` (row 88, 88-O offline upgrade, 47-B), `plan/mac-ed25519`
(SSHSIG sidecar), `plan/rel-gate` revision 3 (G0 to G8, frozen surfaces), `plan/win-feas`
revision 3 (CW3 depends on this row, AT-CW3-4). Roadmap: `docs/roadmap/groups/release.md` rows 88,
UPGRADE-KEY, 93 (REL-GATE) and 94 (CLI-REL); `docs/roadmap/decisions.md:10-11`.

Owner decision (2026-11-18, option B), word for word: "the CLI pins a main release key plus an
offline backup key; a document signed by the backup can name a new main key and revoke the old one;
an unknown version-document format gives a coded 'download the latest installer' message. The owner
must create the backup key and keep it offline."

Risk: R2 overall (the install and upgrade trust path, a signing key, a frozen contract that a 1.0
install reads forever). Review: Dennis, then Codex. One owner task (create the backup key). No spend.

## 0. Summary for the owner

Today every installed CLI trusts exactly one key: the main release key in
`C:distribution/release_key.pub.pem`. If that key leaks or is lost, there is no signed way to tell
installed CLIs to trust a new one. Users would see "signature INVALID" on every upgrade and would
have to find out for themselves that they must reinstall.

This plan adds what the owner chose and nothing more:

1. The CLI pins a second public key, the backup key. Its private half stays offline with the owner.
2. The version document may carry one extra field, `key_rotation`: a small statement signed by the
   backup key that says "the main key is now K2; K1 is revoked". The CLI checks that statement
   against the pinned backup key, then checks the version document against K2. It records the
   revocation in `trust_state.json`, so a document signed by K1 is refused from then on.
3. A version document in a format this CLI does not know gives a coded refusal
   (`upgrade_format_unknown`) that tells the user to download the latest installer, instead of
   "version document rejected: ValueError".

Three slices: UK1 (CLI trust core, R2), UK2 (signing tools and the rotation drill, R2), UK3 (runbook
and contract docs, R1). About 1,600 lines with tests and docs. One owner task: create the backup key
offline before the first signed 1.0 candidate (Q2, Q3).

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
  told what to do.
- 1.0 is the last chance: a 1.0 install can only ever trust what 1.0 pins (row UPGRADE-KEY).

### 1.2 Guarantee (what 1.0 promises)

- G1 Rotation. A 1.0 managed install that pins main key K1 and backup key B accepts a version
  document signed by K2 when the document carries a rotation statement, signed by B, that names K2
  as the main key and revokes K1. It then installs bundles signed by K2.
- G2 Revocation sticks. After G1, the install refuses any version document, bundle or local runtime
  whose trust rests on a revoked key, on every later run, including after a local rollback to an
  older runtime that pins K1.
- G3 Nothing else can rotate. A rotation statement that is not signed by the pinned backup key, that
  names the backup key or a revoked key as the main key, that revokes nothing, or whose epoch is
  lower than one already accepted, is refused and changes nothing.
- G4 Unknown format. A version document or rotation statement whose `schema_version` this CLI does
  not know gives exit 3 with code `upgrade_format_unknown` and fixed text that names the download
  page. The text carries no value from the document.
- G5 No regression. A document signed by the pinned main key, with or without a rotation statement
  that names that same key, behaves exactly as today.
- G6 Release builds carry the backup key. A release candidate whose backup pin is still the
  placeholder, or equals the main key, fails `check-keys --release`.

Non-goals (1.0): TUF roles, thresholds or multiple signatures; rotating the backup key itself (Q6);
rotation in `install.sh` or `install.ps1` (a fresh installer always pins the current key); any change
to the startup update notice (it is unsigned and advisory, `C:_update_check.py:117-119`);
re-signing bundles already published (Q1); hardware tokens (Q2).

### 1.3 Failure modes this plan designs against

| # | Failure | Design answer |
|---|---|---|
| F1 | Main key leaks; attacker signs a document with K1 | Rotation revokes K1; G2 keeps it revoked in `trust_state.json` |
| F2 | Attacker strips the rotation statement and serves an old K1-signed document | The revoked set is kept in local state, not only in the document; serial and expiry already refuse a replay (`C:distribution/installer.py:215-244`) |
| F3 | Attacker forges a rotation statement under their own key | `signing.verify_envelope` requires the embedded key to equal the pinned backup key (`C:distribution/signing.py:79-101`) |
| F4 | A replayed older rotation (epoch 2 after epoch 3) | Monotonic `key_epoch` in state; a lower epoch is refused |
| F5 | The release workflow drops `key_rotation` on a later re-sign | `make_version_document.py` embeds the committed statement on every build; `check-keys --release` cross-checks it |
| F6 | A hostile or huge document is parsed before its signature is checked | Pre-verify parse only under a 64 KiB cap and only to pull out the rotation envelope; nothing from it is trusted until `verify_envelope` passes |
| F7 | Two upgrades race; one records a rotation while the other acts on an older decision | The trust decision is taken again inside `installer._exclusive` |
| F8 | Backup pin is the placeholder in a release build | `check-keys --release` fails the candidate; at runtime a rotation in a placeholder build is refused, never silently skipped |
| F9 | A future v2 document reaches a 1.0 install | Coded `upgrade_format_unknown` with the download page |
| F10 | Backup key lost | Rotation becomes impossible; the runbook says so and Q2 asks for two offline copies |

## 2. Established solutions (survey)

Searches run on 2026-11-19: the TUF specification (fetched, section 5.3); a web search for OpenBSD
signify key rotation; a web search for Debian archive key rotation and `debian-archive-keyring`;
plus the documentation of minisign, Sigstore root signing and Android APK signature v3 as known
references. In the codebase: `release_key.py`, `signing.py`, `version_document.py`, `installer.py`,
`cli/upgrade.py`, `sign_release.py`, `make_version_document.py`, `install.sh`, and the related plans.

- **TUF root rotation** (The Update Framework specification, section 5.3 "Update the root role",
  https://theupdateframework.github.io/specification/latest/#update-root). A new root N+1 must be
  signed by a threshold of keys from the trusted root N and by a threshold of the keys it lists; its
  version must be exactly N+1, else the client treats it as a rollback attack. The client walks the
  chain one version at a time, persists each new root, and deletes its cached timestamp and snapshot
  metadata if those keys rotated (fast-forward attack recovery). Root keys are offline; online keys
  sign the timestamp. Taken here: an offline key that vouches for the online key; a monotonic version
  (`epoch`); proof that the new key works (the document itself is signed by the new main key);
  revocation remembered by the client. Not taken: thresholds, roles, a chain of root files, root
  expiry. The owner chose one backup key, so the threshold is 1 of 1 and a cumulative statement (it
  lists every revoked key) replaces the chain walk. The repo already follows TUF for `serial` and
  `expires` (`C:distribution/version_document.py:36-42`).
- **TUF threshold keys** (same specification, root metadata `threshold`). A threshold limits the
  damage of one leaked key. Not taken: the owner chose a single offline backup. Later L1.
- **signify (OpenBSD)** (Ted Unangst, https://flak.tedunangst.com/post/signify;
  https://isopenbsdsecu.re/mitigations/signify/). No rotation protocol and no cross-signing. The
  keys for the current and the next release sit unsigned in `/etc/signify`; keys are made two
  releases ahead, so release N already ships the key for N+1. The trust path is implicit through the
  signed sets. Its known weakness: if the next key is lost, the trust path must be rebuilt from
  scratch. Taken: the key a client will trust next is decided by something the client already
  trusts. Not taken: one key per release.
- **minisign** (https://jedisct1.github.io/minisign/). Signatures carry a key id; there is no rotation
  or revocation mechanism; a new key is published out of band. This is where the CLI is today.
- **apt and Debian archive keys** (https://ftp-master.debian.org/keys.html;
  https://www.debian.org/News/2011/20110209). The new archive key ships in the
  `debian-archive-keyring` package, under the current trust, before the archive switches to it;
  then only the new key signs. Taken: the next key is introduced through a channel the client already
  trusts. Not taken: a separate key-ring package.
- **Sigstore root of trust** (https://github.com/sigstore/root-signing). Sigstore distributes its
  Fulcio and Rekor keys through TUF; root keys are hardware keys held by named keyholders and used
  only in a recorded ceremony. Taken: the backup key is used only in a written ceremony (UK3 runbook),
  never by CI. Not taken: hardware keyholders, validity windows.
- **Android APK Signature Scheme v3**
  (https://source.android.com/docs/security/features/apksigning/v3). A proof-of-rotation lineage,
  each new key signed by the previous one, lets an installed app accept updates under a new key. Not
  taken: the old main key is the one we must be able to distrust, so it cannot vouch for its
  successor.

Result: the design is TUF's root-key pattern cut down to the owner's option B: one offline backup
key, one rotation statement, one epoch counter, one revoked set. Custom code is limited to the
statement checks and the state fields; all signature checks use the existing `signing.py`.

## 3. Design notes

D1. **One offline backup key, pinned.** `C:distribution/release_backup_key.pub.pem` sits beside
`release_key.pub.pem`. It holds the placeholder `__DECOY_RELEASE_BACKUP_PUBLIC_KEY__` until the owner
creates the key (Q2); then the real public half is committed (it is public, so no injection step is
needed). `release_key.pinned_backup_pem()` follows the rules of `pinned_public_pem()`
(`C:distribution/release_key.py:37-63`): a committed key wins; the dev override
`DECOY_RELEASE_BACKUP_PUBKEY_FILE` is honored only while the placeholder is present, with the same
warnings; a placeholder build raises `NoPinnedKeyError`, which matters only when a rotation needs
the backup key.

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
statement. The fingerprint is `sha256(raw key bytes)` in lower-case hex, computed by one function,
`key_rotation.fingerprint(pem)`, over the existing raw-bytes helper in `signing.py` (made public as
`raw_public_bytes`; the private name stays for its one caller).

D3. **Where the statement travels.** Inside the version document, as the optional top-level field
`key_rotation`. The roadmap row says "a version document signed by the backup key can name a new main
key"; a backup-signed statement inside a main-signed document gives that, with one fetch, no new URL,
and no change to `install.sh` (it ignores unknown fields). The v1 contract already says unknown
top-level fields are ignored (`docs/distribution/version-endpoint-contract.md:91`), so
`schema_version` stays `cli-version-document/v1`.

D4. **Resolution order (one function, `key_rotation.resolve_main_key`).** Inputs: the document
bytes, the detached signature, the pinned main and backup keys, and the trust state.

1. If the bytes are at most 64 KiB, parse them as JSON and read `key_rotation` if it is an object.
   A parse error (including `RecursionError`), a non-object, or a size over the cap means "no
   statement". Nothing read here is trusted yet.
2. With a statement: if the backup pin is the placeholder, refuse `upgrade_rotation_unavailable`.
   If the payload `schema_version` is a string other than `cli-key-rotation/v1`, refuse
   `upgrade_format_unknown`. Check the envelope with `signing.verify_envelope(...,
   expected_public_pem=backup, schema_version="cli-key-rotation/v1")`; failure refuses
   `upgrade_rotation_invalid`. Then check: `epoch` is an int (not bool) >= 2; `revokes` is a
   non-empty list of strings that `re.fullmatch("[0-9a-f]{64}")` accepts; `main_key` loads as
   Ed25519; its fingerprint differs from the backup key's and is not in `revokes`. Any failure
   refuses `upgrade_rotation_invalid`. An `epoch` lower than the stored `key_epoch` refuses
   `upgrade_rotation_replayed`. The candidate main key is `main_key`; the revoked set is the stored
   set plus `revokes`.
3. Without a statement: the candidate main key is the pinned main key; the revoked set is the stored
   set.
4. If the candidate's fingerprint is in the revoked set, refuse `upgrade_key_revoked`.
5. Verify the detached signature over the exact bytes with the candidate key through
   `vd.verify_document` (`C:distribution/version_document.py:141`, which calls
   `signing.verify_detached`). On failure apply D6, else refuse with today's text, now coded
   `upgrade_signature_invalid`.
6. Return a `TrustDecision(main_pem, epoch, revoked)`. `epoch` is the statement's epoch or the stored
   one.

No second verifier: steps 2 and 5 call the two existing functions in `signing.py`.

D5. **Trust state.** `trust_state.json` gains `key_epoch` (int, default 1) and `revoked_keys`
(sorted list of fingerprints, default empty). The reader and writer move from
`C:distribution/installer.py:182-212` into a new `C:distribution/trust_state.py`, the one module that
reads or writes the file. The writer takes the union of the stored and new revoked sets (grow-only)
and the larger epoch, and keeps `serial` a top-level integer, because `install.sh` reads it with
`json_top_number` (`PT:install/install.sh:133`, `:289`). The state is written once, atomically,
inside `check_document_freshness` (`C:distribution/installer.py:215`), which already runs under the
install lock and only on a recording run (never on `--check`). The file stays local state, not a
secret, as today (`C:distribution/installer.py:46-48`). The new main key itself is not stored: a
later document either carries the statement (D7) or is signed by a key the newer runtime pins.

D6. **Unknown format.** After step 5 passes, `vd.parse_document` raises a new subclass
`UnknownFormat(ValueError)` when `schema_version` is a string other than `cli-version-document/v1`;
`C:cli/upgrade.py` maps it to `upgrade_format_unknown`. When step 5 fails and the step 1 parse found
a `schema_version` string that starts with `cli-version-document/` and is not v1, the refusal is also
`upgrade_format_unknown` (Q5): a 1.0 install that meets a v2 document signed under a key it does not
know gets the useful message. The text is fixed: "this decoy cannot read the update channel's format.
Download the latest installer from <DOWNLOAD_PAGE_URL>." `DOWNLOAD_PAGE_URL` is a constant beside
`DEFAULT_URL` in `version_document.py` (Q4). No value from the document reaches the output.

D7. **Every later document carries the statement.** A committed file `PT:key_rotation.json` (absent
until the first rotation) holds the current statement. `make_version_document.py` embeds it on every
build when present, after checking it with `signing.verify_envelope` against the committed backup
key. The CLI-REL S0 `publish`, `resign` and `rollback` modes call `make_version_document.py`, so they
carry it without a new flag. This is the cumulative-statement replacement for TUF's chain walk: a
1.0.0 install that never upgraded still finds the statement in whatever document is live.

D8. **One choke point for key use.** Every place that picks a key to verify with goes through
`key_rotation`: `resolve_main_key` for the network paths and `local_key(home)` for local activation
and the 88-O offline bundle path (the pinned main key, refused with `upgrade_key_revoked` if it is
revoked in state). `install_version` calls `resolve_main_key` again under `_exclusive` and uses the
result for the document, the bundle signature (`C:distribution/installer.py:543`) and the manifest
(`:555`). A guard test walks the syntax tree of every module under `C:` and fails if any module
other than `key_rotation.py` calls `release_key.pinned_public_pem` or `pinned_backup_pem`. Covered
spellings (recurring-defects class 5): attribute calls on the module, `import ... as` aliases,
`from release_key import name` and `from ... import name as alias`. One exception, scoped to the
function and recorded with its reason: `C:__main__.py:226` `_key_unresolved`, which only asks
whether a key is pinned.

D9. **Rollback across a rotation (Q1).** A retained runtime whose manifest was signed by a revoked
key cannot be verified with the new key. `activate_local_version` refuses with
`upgrade_rollback_key_rotated` when verification fails and `key_epoch > 1`; the hint says to install
that version again with `decoy upgrade --force --version <v>` if it was re-published under the new
key. `current` is not changed.

D10. **Signer side.** `PT:sign_release.py` gains `rotation`: it reads the backup private key only
from `--backup-key-file` (passphrase-encrypted PKCS8, passphrase by `getpass`), never from
`DECOY_RELEASE_KEY_PEM` or `DECOY_RELEASE_KEY_FILE`, so the CI secret path cannot reach it. It takes
`--new-main-pub`, `--epoch` and `--revoke-pub` (repeatable), refuses an epoch not above the committed
statement's and a revoke list that drops an entry of the committed one, and writes
`key_rotation.json` atomically. `check-keys --release` adds: the backup pin is not the placeholder,
differs from the main pin, and, when `PT:key_rotation.json` exists, its `main_key` equals
`release_key.pub.pem`. No new dependency: `cryptography` already loads encrypted PKCS8.

Design principles (architecture.md): one place per fact (rotation schema and checks in
`key_rotation.py`; the state file in `trust_state.py`; fingerprints in one function); single-purpose
functions; a typed `TrustDecision` instead of three loose values; no flag argument switches behavior
(record versus check stays the existing `record` keyword). The trust-state move answers a real
change pain: `installer.py` is at 731 lines of an 800 cap, and the state file gains a second reason
to change. Established pattern: TUF root rotation, cut to one key (section 2).

## 4. Behavior

### 4.1 Normal upgrade, no rotation ever

Unchanged. `resolve_main_key` returns the pinned key, epoch 1, an empty revoked set. The state file
gains `key_epoch: 1` and `revoked_keys: []` on the next recording write.

### 4.2 First upgrade after a rotation (client pins K1, document signed by K2 with statement)

`decoy upgrade` verifies the statement with B, verifies the document with K2, checks freshness,
downloads the bundle, verifies it with K2, verifies the manifest with K2, swaps, and records
`key_epoch: 2`, `revoked_keys: [fp(K1)]` with the serial. The new runtime pins K2. Output is today's
"upgraded" line.

### 4.3 `decoy upgrade --check` after a rotation

Same checks; reports; writes nothing.

### 4.4 Attack: K1-signed document after the rotation was recorded

Refused `upgrade_key_revoked`, exit 3, nothing written.

### 4.5 Rollback to a retained runtime signed by K1

Refused `upgrade_rollback_key_rotated` (Q1), exit 3, `current` unchanged.

### 4.6 1.0 install meets a v2 document

`upgrade_format_unknown`, exit 3, fixed text with the download page.

### 4.7 Owner rotation ceremony (UK3 runbook)

1. On the offline machine: create K2 with `sign_release.py keygen`, then run
   `sign_release.py rotation --backup-key-file <B> --new-main-pub K2.pub --epoch 2 --revoke-pub K1.pub`.
2. Carry `key_rotation.json` and `K2.pub` (public files only) back. Put K2's private half in the
   `native-release` Environment secret, replacing K1.
3. Commit `PT:key_rotation.json` and the new `release_key.pub.pem`; `check-keys --release` passes.
4. Cut a release. The version document carries the statement from now on.
5. Re-publish the supported older bundles under K2 if they must stay installable by `--version`
   (Q1); otherwise raise `min_supported` to the first K2 release.

## 5. Later (1.x or 2.0)

- L1 Threshold signing (two of three keys) for rotation, as `cli-key-rotation/v2`; 1.0 installs get
  `upgrade_format_unknown` and reinstall.
- L2 Rotating the backup key itself (Q6).
- L3 The startup notice says when the channel format is unknown.
- L4 `install.sh` and `install.ps1` honor a rotation for a user who runs an old cached script.

## 6. Enumerations

### 6.1 Exit paths

All new refusals exit `EXIT_RUNTIME` 3 through `_refuse` (`C:cli/upgrade.py:180-186`), which prints
fixed text plus the exception type and drops the chain:

- `upgrade_signature_invalid`: today's text at `C:cli/upgrade.py:113-118`, now with a code.
- `upgrade_key_revoked`: the candidate main key is in the revoked set (D4 step 4, D8).
- `upgrade_rotation_invalid`: the statement fails `verify_envelope` or a D4 step 2 field check.
- `upgrade_rotation_replayed`: statement epoch below the stored `key_epoch`.
- `upgrade_rotation_unavailable`: a statement arrived but this build's backup pin is the placeholder.
- `upgrade_format_unknown`: D6; replaces `upgrade_document_rejected` (`C:cli/upgrade.py:122`) only
  for an unknown `schema_version`.
- `upgrade_rollback_key_rotated`: D9, on the local activation path at `C:cli/upgrade.py:97-103`.
- Unchanged: `upgrade_no_key` exit 1 (`C:cli/upgrade.py:86`), `upgrade_document_stale`,
  `upgrade_endpoint_unreachable`, `upgrade_install_failed`.
- Signer: `sign_release.py rotation` and `check-keys --release` exit 1 with one line per problem and
  print no key material.

### 6.2 Routes

- Network latest upgrade and `--force` reinstall: `resolve_main_key` before the lock for the early
  checks, again inside `install_version` under `_exclusive` (`C:distribution/installer.py:478-488`).
- Pinned `--version` download (`C:distribution/installer.py:518-523`): same key as the latest route.
- `--check` (`C:cli/upgrade.py:124-142`): resolve, check freshness with `record=False`, write nothing.
- Local activation (`C:cli/upgrade.py:97-103`, `C:distribution/installer.py:398-441`):
  `key_rotation.local_key(home)`, then D9.
- 88-O offline bundle (`plan/release-chain`, not on main): `local_key(home)`; whichever of 88-O and
  UK1 merges second wires it (section 12).
- Fresh install by `install.sh` (`PT:install/install.sh:264-270`) and `install.ps1`: unchanged; they
  pin the current main key when published and ignore `key_rotation`.
- Startup notice (`C:_update_check.py:117`) and `_key_unresolved` (`C:__main__.py:226`): unchanged.
- Release smoke (`PT:smoke_install.py:481`): verifies with the pinned key; a document with a
  statement naming that key still verifies. Unchanged.

### 6.3 Fields

- Version document v1: optional top-level `key_rotation` (an envelope `{alg, payload, signature,
  public_key}`); `schema_version` unchanged (`C:distribution/version_document.py:52`).
- Rotation payload `cli-key-rotation/v1`: `schema_version`, `epoch`, `main_key`, `revokes`, `issued`
  (D2). A missing or unknown schema tag is refused (recurring-defects class 4); extra payload fields
  are ignored.
- `trust_state.json`: adds `key_epoch` (int >= 1, bool refused) and `revoked_keys` (sorted list of
  64-hex strings); `serial` and `latest` keep their form (`C:distribution/installer.py:207-212`).
- New pinned file `C:distribution/release_backup_key.pub.pem`; new committed file
  `PT:key_rotation.json` (absent until a rotation).
- `--json` error object: unchanged shape (`decoy-error-v1`); new `code` values only.

### 6.4 FK shapes

N/A: this row changes the update channel and never reads, resolves or masks foreign keys or any
customer data.

### 6.5 Output surfaces

- Human error lines and `--json` error objects of `decoy upgrade` (codes in 6.1).
- `trust_state.json` in `DECOY_HOME` (local, not a secret).
- The published `version.json` gains `key_rotation` after the first rotation.
- `sign_release.py` stdout and stderr: file paths and fingerprints only, never a private key.
- Docs: `docs/distribution/key-rotation.md` (new runbook), `docs/distribution/version-endpoint-contract.md`,
  and `docs/release/frozen-surfaces.md:23` (the "Version document and installer contract" row).

## 7. Class table

| # | Class | Closing structure | Sentry or property test | Mutation that must turn it red |
|---|---|---|---|---|
| 1 | value leak | every new refusal goes through `_refuse` with fixed text, a code and the exception type only; D6 text has no document value | AT-UK1-16, AT-UK1-9 | M16 put `str(exc)` back in the message; M9 echo the document's `schema_version` |
| 2 | cleanup | a refusal writes nothing: state is written once, after all checks, inside `check_document_freshness`; a refused rotation leaves the state bytes identical | AT-UK1-3, AT-UK1-10 | M10 record state on `--check` |
| 3 | state | `trust_state.py` is the one reader and writer; `revoked_keys` grow-only and `key_epoch` max-only on write | AT-UK1-12 | M12 write the document's revoked list in place of the union |
| 4 | route | every key choice goes through `key_rotation` (D8); network, pinned, force, check, local and offline routes enumerated in 6.2 | AT-UK1-14, AT-UK1-13 | M14 the guard scans only `distribution/`; M13 local activation without the revocation check |
| 5 | referential | a statement names keys by fingerprint; the new main key must differ from the backup key and must not be in `revokes`; `revokes` is cumulative | AT-UK1-5, AT-UK2-5 | M5 drop the main-differs-from-backup check |
| 6 | untrusted input | the pre-verify parse is capped at 64 KiB and only extracts the envelope; nothing is trusted until `verify_envelope` passes against the pinned backup key | AT-UK1-4, AT-UK1-15 | M4 verify against the envelope's embedded key; M15 drop the size cap |
| 7 | TOCTOU (check-then-use) | `install_version` resolves the trust decision again under `_exclusive`, after re-reading the state | AT-UK1-11 | M11 pass the pre-lock decision into `install_version` |
| 8 | weak test | rotation tests use real Ed25519 keys, real signatures and the real `decoy upgrade` command; no verifier is mocked | AT-UK2-5 | M23 make `revokes` hold only the last key (the drill's skipped-epoch client must catch it) |
| 9 | refactor | the trust-state move out of `installer.py` keeps behavior: corrupt state refused, absent state is a first run, `install.sh` still reads `serial` | AT-UK1-18 | M18 nest `serial` so `install.sh`'s top-level read misses it |
| 10 | frozen surface | version document stays `cli-version-document/v1` with one optional field; `cli-key-rotation/v1` is new and closed; both land before REL-GATE G3 and enter the frozen-surface map | AT-UK1-19, AT-UK3-1 | M19 bump `schema_version` when `key_rotation` is present |

## 8. Acceptance tests (red first)

Each test is written first and fails on the base head for the reason given ("guard" means it passes
on base and pins behavior the slice must keep). Tests use ephemeral Ed25519 keys K1, K2, K3 and a
backup B created in the test, injected through `DECOY_RELEASE_PUBKEY_FILE` and
`DECOY_RELEASE_BACKUP_PUBKEY_FILE` in a placeholder build (the existing seam,
`C:distribution/release_key.py:52-57`). A builder may add tests, never weaken these. Every mutation
runs on the final head and the record names that head (recurring-defects class 9). 25 acceptance
rows, 25 mutations (M1 to M25).

### 8.1 UK1 (CLI trust core)

| ID | Test | Red on base because | Mutation |
|---|---|---|---|
| AT-UK1-1 | Guard: a K1-signed document with no statement upgrades as today; a K2-pinned build accepts a K2-signed document whose statement names K2 | guard | M1 require the signer to differ from the pinned key whenever a statement is present |
| AT-UK1-2 | Client pins K1; a K2-signed document carries a B-signed statement (epoch 2, main K2, revokes K1); a K2-signed bundle installs; state holds `key_epoch: 2`, `revoked_keys: [fp(K1)]` and the serial | signature invalid today | M2 verify the bundle with the pinned key instead of the resolved key |
| AT-UK1-3 | After AT-UK1-2, a fresh-serial K1-signed document with no statement is refused `upgrade_key_revoked`; state and `current` byte-identical | K1 is still trusted | M3 read revocations from the document only, not from state |
| AT-UK1-4 | A statement signed by K1, by K2 or by an unrelated key, or with B's public key embedded but a forged signature, is refused `upgrade_rotation_invalid`; nothing written | no rotation code | M4 verify against the envelope's embedded key |
| AT-UK1-5 | A statement whose `main_key` is B, whose `main_key` is in `revokes`, with empty `revokes`, with `epoch` 1 or `true`, or with a fingerprint plus `"\n"` or in upper case, is refused `upgrade_rotation_invalid` | no rotation code | M5 drop the main-differs-from-backup check |
| AT-UK1-6 | With stored `key_epoch: 3`, a valid epoch-2 statement is refused `upgrade_rotation_replayed`; an epoch-3 statement equal to the stored one is accepted | no epoch | M6 skip the epoch comparison |
| AT-UK1-7 | A K1-signed document carrying a valid statement that revokes K1 is refused `upgrade_key_revoked` | K1 signature passes today | M7 verify with the pinned key first and accept on success |
| AT-UK1-8 | Backup pin is the placeholder: a document with a statement is refused `upgrade_rotation_unavailable`; one without a statement upgrades | no backup pin | M8 skip the statement and use the pinned key when the backup is the placeholder |
| AT-UK1-9 | A trusted-key-signed document with `schema_version` `cli-version-document/v2`, a bad-signature document with that schema, and a statement with `cli-key-rotation/v2` each exit 3 with `upgrade_format_unknown` and the fixed text naming `DOWNLOAD_PAGE_URL`; a document with no `schema_version` still gives `upgrade_document_rejected` | prints "version document rejected: ValueError" | M9 echo the document's `schema_version` in the message (the test plants a marker string there) |
| AT-UK1-10 | `decoy upgrade --check` across a rotation reports and leaves `trust_state.json` absent or byte-identical | no rotation | M10 record state on `--check` |
| AT-UK1-11 | Process A records epoch 3 (revokes K1 and K2) between process B's pre-lock resolve (epoch 2, main K2) and B's `install_version`; B refuses `upgrade_key_revoked` (a test hook pauses B after the pre-lock resolve) | no rotation | M11 pass the pre-lock decision into `install_version` |
| AT-UK1-12 | `key_epoch` non-int, bool, 0 or negative, or `revoked_keys` non-list or non-hex, is refused as unreadable state; absent fields read as epoch 1 and an empty set; a write after an epoch-2 statement over a state with an extra revoked fingerprint keeps both | fields do not exist | M12 write the document's revoked list in place of the union |
| AT-UK1-13 | Retained slot signed by K1, runtime pins K2, state epoch 2: `decoy upgrade --version <old>` refuses `upgrade_rollback_key_rotated`, `current` unchanged; with a runtime pinning K1 and K1 revoked in state, local activation refuses `upgrade_key_revoked` before any manifest read | generic activation failure | M13 activate with the pinned key without the revocation check |
| AT-UK1-14 | Guard `CT:sentry/release/test_key_choke_point.py` fails on seeded calls in a scratch copy: `release_key.pinned_public_pem()` in `cli/upgrade.py`, `import decoy.distribution.release_key as rk; rk.pinned_backup_pem()` in `distribution/installer.py`, and `from decoy.distribution.release_key import pinned_backup_pem as p` anywhere under `C:`; passes on the tree with only `__main__._key_unresolved` excepted | guard does not exist | M14 the guard scans only `distribution/` |
| AT-UK1-15 | A 64 KiB plus 1 byte document and a 10,000-deep nested document reach the signature check with no statement and refuse `upgrade_signature_invalid`; a spy shows `json.loads` was not called on the oversize bytes | no pre-verify parse | M15 drop the size cap |
| AT-UK1-16 | Every new code, human and `--json`: output matches `decoy-error-v1`, contains the code, and contains no PEM line, no fingerprint, no URL other than `DOWNLOAD_PAGE_URL`, and no exception message; each raised error has `__cause__` and `__context__` None | codes do not exist | M16 put `str(exc)` back in the message |
| AT-UK1-17 | `DECOY_RELEASE_BACKUP_PUBKEY_FILE` is honored with a warning while the backup pin is the placeholder and ignored with a warning once a real key is committed (the test copies the module with a real pem) | override does not exist | M17 honor the override always |
| AT-UK1-18 | Guard after the move: corrupt state refused, absent state a first run, serial replay refused; `install.sh` under `sh` reads `serial` from a state file written by the new writer and refuses a lower serial | guard (the refactor) | M18 nest `serial` under an object |
| AT-UK1-19 | A v1 document with `key_rotation` installs through `install.sh` (pinned K2) unchanged, and the built wheel lists `decoy/distribution/release_backup_key.pub.pem` | backup pem absent | M19 bump `schema_version` when `key_rotation` is present |

### 8.2 UK2 (signer tools and drill)

| ID | Test | Red on base because | Mutation |
|---|---|---|---|
| AT-UK2-1 | `sign_release.py rotation --backup-key-file B.enc --new-main-pub K2.pub --epoch 2 --revoke-pub K1.pub` (passphrase through a patched `getpass`) writes `key_rotation.json` that `signing.verify_envelope` accepts against B's public key with `cli-key-rotation/v1` | subcommand does not exist | M20 load the key through `load_private_key()` (the CI environment path) |
| AT-UK2-2 | `rotation` refuses: the key given only by `DECOY_RELEASE_KEY_PEM`, a new main key equal to B, an empty revoke list, an epoch not above the committed statement's, a revoke list missing an entry of the committed statement; stderr carries no key text | not built | M21 accept a new main key equal to the backup |
| AT-UK2-3 | `make_version_document.py` embeds `PT:key_rotation.json` byte for byte as `key_rotation` when it exists, omits the field when absent, and refuses a statement that does not verify against the committed backup key | not built | M22 embed without verifying |
| AT-UK2-4 | `check-keys --release` fails on a placeholder backup pin, on a backup equal to the main key, and on a committed statement whose `main_key` differs from `release_key.pub.pem`; passes on a consistent set | checks `install.sh` only | M24 skip the statement cross-check |
| AT-UK2-5 | Drill with real keys and the real `decoy upgrade` command over a file-backed fetch: client 1 (pins K1) goes epoch 1 to 2 to 3; client 2 (pins K1, never saw epoch 2) goes straight to epoch 3; both then refuse a K1-signed and a K2-signed document | not built | M23 make `revokes` hold only the last key |

### 8.3 UK3 (docs)

| ID | Test | Red on base because | Mutation |
|---|---|---|---|
| AT-UK3-1 | Docs check: `docs/distribution/key-rotation.md` exists with `Status: current` and the five ceremony steps of 4.7; `version-endpoint-contract.md` names `key_rotation`, `cli-key-rotation/v1` and the unknown-format rule; the frozen-surface row lists both and the `trust_state.json` fields | docs do not exist | M25 drop `key_rotation` from the contract doc |

## 9. Reuse inventory

- Verification: `signing.verify_envelope` (statement) and `signing.verify_detached` through
  `vd.verify_document` (document, bundle). No new verifier, no new crypto library.
- Key pin rules and dev override: the pattern of `release_key.pinned_public_pem`.
- Freshness and replay: `installer.check_document_freshness`, `vd.check_fresh`, the `serial` rule.
- Atomic state write: `C:_atomic.py` `write_atomic` (already used for the state file).
- Lock: `installer._exclusive` and `C:distribution/lock.py`.
- Error output: `_refuse` and `emit_error` (`decoy-error-v1`).
- Signer: `sign_release.py` `keygen`, `sign_bytes`, `_write_atomic`, `check-keys`;
  `make_version_document.py`.
- Test seams: `DECOY_RELEASE_PUBKEY_FILE`, the injected downloader in `install_version`, the
  existing upgrade e2e harness (`CT:e2e/test_upgrade_error_text.py`).

## 10. Frozen contracts touched

- `cli-version-document/v1`: one optional field, `key_rotation`. Additive; v1 readers already ignore
  unknown fields. Must merge before REL-GATE G3 freezes the "Version document and installer
  contract" row (`docs/release/frozen-surfaces.md:23`).
- New `cli-key-rotation/v1`: frozen from 1.0. Any change after 1.0 is a v2, which 1.0 installs
  answer with `upgrade_format_unknown`.
- `trust_state.json`: two additive fields; `serial` keeps its top-level integer form for `install.sh`.
- Exit codes: none added or changed. Error codes: seven new `code` values; the `--json` error shape
  is unchanged.
- Engine contract: not touched. Nothing in this row reaches the engine, so there is no 2.0 item.

## 11. Placement (checked against CLI CODEMAP "Where Things Go")

| New file | Directory | Basis | Neighbor |
|---|---|---|---|
| `key_rotation.py` | `C:distribution/` | CODEMAP row "Shipped install and update" (`CODEMAP.md:64`); 15 entries today, 18 after, under the fan-out limit of 25 | `release_key.py` |
| `trust_state.py` | `C:distribution/` | same row; takes code out of `installer.py` (731 lines, cap 800) | `installer.py` |
| `release_backup_key.pub.pem` | `C:distribution/` | same row; shipped in the wheel like `release_key.pub.pem` | `release_key.pub.pem` |
| `test_key_rotation.py`, `test_trust_state.py`, `test_upgrade_rotation.py`, `test_sign_release_rotation.py` | `CT:unit/distribution/` | CODEMAP: "new tests go in `tests/unit/distribution/`" | `test_sign_release_sshsig.py` |
| `test_key_choke_point.py` | `CT:sentry/release/` | release-path guards live here | `test_frozen_surface_map.py` |
| `test_rotation_drill.py` | `CT:e2e/` | end-to-end command tests | `test_upgrade_error_text.py` |
| `key_rotation.json` (after the first rotation only) | `PT:` | CODEMAP row "Build-host release tools" (`CODEMAP.md:65`) | `make_version_document.py` |
| `key-rotation.md` | `docs/distribution/` | distribution docs | `version-endpoint-contract.md` |

## 12. Slices

Sizes are production and test lines. Every slice is under 800 lines and 10 production files. Commits:
Conventional Commits subject at most 72 characters, short or no body, final line `cam`, author
`ckeep <decoy@trydecoy.com>`, no other trailers. Test depth: T0 per edit, T1 per commit, T2 at the
gate on the exact head with the slice's mutations. UK1 touches a frozen contract and moves code, so
it escalates to the full suite at the slice (testing.md triggers).

| Slice | Repo | Content | Prod / test | Risk | Depends on |
|---|---|---|---|---|---|
| UK1 | CLI | `key_rotation.py` (statement checks, `resolve_main_key`, `local_key`, `fingerprint`, `TrustDecision`); `trust_state.py` (moved reader and writer plus two fields); `release_key.pinned_backup_pem` and the placeholder pem; `signing.raw_public_bytes`; `vd.UnknownFormat` and `DOWNLOAD_PAGE_URL`; `install_version` and `activate_local_version` use the resolver under the lock; `cli/upgrade.py` codes; the choke-point guard. AT-UK1-1 to AT-UK1-19 | 330 / 560 | R2 | none (main). Rebase onto 47-B if it merges first; if 88-O merges first, UK1 wires its key to `local_key`, else 88-O does |
| UK2 | CLI | `sign_release.py rotation` and `check-keys --release`; `make_version_document.py` embed; the rotation drill. AT-UK2-1 to AT-UK2-5 | 150 / 330 | R2 (handles the backup private key) | UK1 |
| UK3 | CLI | `docs/distribution/key-rotation.md` runbook; contract doc; frozen-surface row; `docs/install.md` line on the unknown-format message; readiness item "backup key pinned" pointing at `check-keys --release`; roadmap row and shipped log. AT-UK3-1 | docs about 200 / 40 | R1 | UK2 |
| OWNER-1 | owner | Create the backup key offline (Q2), keep two copies, hand over the public PEM; commit it (a one-file change, R1) | 3 | owner | before the first signed 1.0 candidate (CLI-REL S0) |

Totals: about 480 production lines, 930 test lines and 200 doc lines; about 1,600 lines.

Dated targets: UK1 merged by 2026-11-24, UK2 by 2026-11-26, UK3 by 2026-11-27, all before REL-GATE
G3 freezes the version-document contract. OWNER-1 by 2026-11-28 (Q3). CLI-REL S0 must run
`check-keys --release`; its plan gets that line when S0 is built. WIN-FEAS CW3 runs these tests on
Windows (AT-CW3-4) after UK1.

## 13. Owner questions

Recommended answer first in each.

- **Q1 Rollback across a rotation.** (a) Recommended: refuse with `upgrade_rollback_key_rotated`. A
  key may be revoked because it leaked, and a runtime it vouched for should not be re-activated on
  its word. For a planned rotation, the runbook re-publishes the supported older bundles under the
  new key, so `decoy upgrade --force --version <v>` still works. (b) For a planned rotation, keep the
  old key valid for local activation only. This needs a `reason` field and a second trust class:
  more code and a weaker rule.
- **Q2 Backup key custody.** (a) Recommended: create it with `sign_release.py keygen` on a machine
  kept offline for the ceremony; store it as passphrase-encrypted PKCS8 on two USB drives kept in two
  places; keep the passphrase apart from the drives; commit only the public half. It is used only for
  a rotation, never by CI. (b) A hardware token with Ed25519 support (for example a YubiKey with
  firmware 5.7 or later): stronger, costs money, and the tool would need a PKCS#11 path, which is a
  new dependency. (c) Paper only: hard to restore without errors.
- **Q3 Deadline for the backup key.** (a) Recommended: 2026-11-28, ahead of the first signed 1.0
  candidate. A 1.0 build without it can never rotate, so `check-keys --release` blocks the release
  and no G0 exception is possible. (b) Any date before CLI-REL S0's first signed candidate.
- **Q4 Download page in the message.** (a) Recommended: `https://trydecoy.com/download`, a constant
  beside `DEFAULT_URL`, moved by RW-C2b if the domain answer (REL-WEB Q1) changes it. (b) Point at
  the install docs page.
- **Q5 Unknown format with a signature this install cannot check.** (a) Recommended: show the same
  `upgrade_format_unknown` text when the bytes name a `cli-version-document/` schema other than v1.
  The text is fixed and points at the official page, so an attacker gains nothing beyond the denial
  of service they can already cause. (b) Show "signature INVALID" whenever the signature fails.
- **Q6 Rotating the backup key.** (a) Recommended: not in 1.0. If the backup key is lost or leaks,
  users reinstall from the website; a `cli-key-rotation/v2` can add backup rotation in 1.x for
  installs made after that. (b) Add an optional `backup_key` field to v1 now: more to test and to
  freeze.

## 14. Pre-mortem

- **The backup key is never created.** The 1.0 release is blocked by `check-keys --release`. Q3 sets
  the date; the board shows OWNER-1.
- **The backup key leaks.** An attacker who also controls the channel can rotate the main key to
  their own. Only offline custody (Q2) and a reinstall (Q6) address it.
- **Installs that never see the rotation.** An attacker holding a leaked K1 can still serve a fresh
  K1-signed document to an install that never fetched a document with the statement. TUF has the
  same limit. The runbook documents it.
- **The statement falls out of later documents.** D7 embeds it on every build from a committed file;
  AT-UK2-3 and AT-UK2-4 catch a missing or stale one.
- **Pre-verify parsing.** Parsing before verification is a new step. It is capped, catches every
  parse error, and only selects which key to verify with; AT-UK1-15 covers the hostile cases.
- **`installer.py` size and 47-B.** The trust-state move keeps `installer.py` under 800 lines. If
  release-chain 47-B restructures `installer.py` first, UK1 rebases; the resolver call sites are a
  few lines.
- **Release-day surprise.** The drill (AT-UK2-5) runs real keys through the real command, so the
  first real rotation is not the first time the code runs.

## 15. Done when

- [ ] UK1, UK2 and UK3 are merged with their acceptance tests and mutations recorded on the exact
      merge heads.
- [ ] The frozen-surface map lists `key_rotation`, `cli-key-rotation/v1` and the state fields before
      REL-GATE G3.
- [ ] OWNER-1 is done: the real backup public key is committed and `check-keys --release` passes on
      the 1.0 candidate.
- [ ] The runbook is in `docs/distribution/key-rotation.md`.
- [ ] Roadmap row UPGRADE-KEY closed and the shipped log current.

## 16. Not verified by this plan

- No code ran for this plan. Line numbers come from reading `origin/main` at `c5a156a8`.
- Whether `install.ps1` ignores the extra field the same way `install.sh` does (it reads fields by
  name; WIN-FEAS CW5 tests it on Windows).
- The size of a version document with a statement (estimated under 3 KiB, far under the 64 KiB cap).
- Whether CLI-REL S0 calls `make_version_document.py` in every mode, as its plan says today.
