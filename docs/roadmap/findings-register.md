# Review notes and the findings register

Status: record

Part of the roadmap: [ROADMAP.md](../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rule: fixes ride features. A review finding becomes an acceptance criterion only for a wrong-value
bug, a confidentiality bug or an R1 blocker; everything else is listed here with no dispatch order.

**Hardening notes.** 20.1 ML-pack "fail-open" is overstated: `load_with_fallback`
(`profiling/model_pack/loader.py:151-166`) falls back to the regex baseline, untrusted packs need a
verifiable signature before `joblib.load`, and `trusted=True` applies only to the wheel-shipped default
pack, whose digest is self-attested. 12.2 is closed on the full-frame path only.

**After V1.** No login rate limit or lockout and no password policy (F45). CLI `scan` uses
`pd.read_fwf`; divergence from the engine reader is untested (H-1 G5). Native-kernel fallback
telemetry beyond a warning; GCS and S3 conditional writes; SFTP fingerprint pinning; the
data_discovery keyword denylist; multi-process API support.

**Findings register** (from the archived 2026-10-30 reconciliation and its review; "FRAME finding"
means unverified until that item's FRAME):

| Finding | Summary | Home | State |
|---|---|---|---|
| G1 | CLI `resolve_substrate` ImportError | R1-a | CLOSED (CLI #71) |
| G2 | Four engine version truths; CLI `--version` literal | D-4 | engine CLOSED; CLI literal OPEN |
| G3 | No recorded smoke runs; release docs are templates | R1 gate | OPEN |
| G4 | CLI chunked output bypasses `TransactionalSink` | CLI delivery | verified by reading 2026-10-30 |
| G5 | CLI scan parses fixed width with `pd.read_fwf` | H-1 FRAME; after V1 | verified by reading |
| G6 | Plaintext spill under three temp roots | row 58 (F25) acceptance; F26 FRAME | verified 2026-11-24: the out-of-core temp root (`E:execution/out_of_core/_spill_estimate.py:512-521`) still derives from `tempfile.gettempdir()`; OPEN on row 58 |
| G7 | Cloud table reads were not bounded | row 58 (F25) acceptance | corrected 2026-11-24: the connectors already streamed (GCS `Blob.open` reads ahead 40 MiB, `DEFAULT_CHUNK_SIZE` at `google/cloud/storage/fileio.py:25`; S3 streams, E:connectors/s3.py:251). The whole-object reads were in the profile readers' `to_frame`, S3 and GCS, CSV and Parquet (E:profile/_cloud_readers.py:268, :316, :388, :435). There is no SFTP table reader (E:profile/_readers.py:536-549). The CSV sample window could grow to the whole object (E:profile/_cloud_readers.py:150-193). Engine PR #789 (F25 G7-1, open) bounds `to_frame` to pinned ranges and caps the CSV sample at 64 MiB. The CLI does not run cloud sources yet: `check_cloud_endpoints_supported` (`src/decoy/cli/extras.py:133`) refuses them. The isolated-route materialization cap is still open; OPEN on row 58 |
| G8 | Post-mask leak helper fails open | row POSTMASK-FAIL-CLOSED (1.0); from F34 FRAME | verified 2026-11-24: `_source_identity` (`E:verification/postmask/residual_pii.py:240-274`) returns None on any exception; OPEN |
| G9 | CLI token vault cleartext, unauthenticated (11.8) | row TOKEN-VAULT-MAC (1.x); R2 11.8 | verified 2026-11-24: cleartext at rest by design (0600 file, 0700 dir) with no tamper check; V1 known limitation on the row |
| G10 | License placeholders; per-repo licenses | R1-c | OPEN |
| G11 | Native kernels fall back silently | F29 FRAME (if free) | CLOSED, verified fixed 2026-11-24: `E:execution/pipeline/_native_notice.py`, test `E:tests/unit/execution/pipeline/test_native_fallback_notice.py`. The `any()` versus `all()` gap is in [inbox.md](inbox.md) (V2-LOG, NATIVE-MISSING-WARN) |
| G12 | Engine dependency floors too wide | F10 FRAME; D-4 | UNVERIFIED |
| G13 | Startup DDL beside Alembic in production | F44 platform FRAME | UNVERIFIED |
| G14 | SMTP password in plaintext | F45 criterion; F14 FRAME | verified by reading |
| G15 | No login limit or password policy, cookie without `Secure`, wide CORS | F45 | `Secure` verified; rest UNVERIFIED |
| G16 | Graceful shutdown mismatch in the inline topology | F23 FRAME | UNVERIFIED |
| G17 | Single-process state unenforced | F45 FRAME | UNVERIFIED |
| G18 | Python 3.10 image, no platform lockfile, python-jose | F44 platform; R2 | jose CLOSED (#136); rest OPEN |
| G19 | Security scanning has no local equivalent | R2 AUDIT | OPEN |
| G20 | Local ci-mirror is prose | R1 gate | CLOSED (platform #156) |
| G21 | AUDIT undefined; packets 11 to 20 not on disk | R2 AUDIT | packets CLOSED (#125); definition OPEN |
| G22 | Passport signing key outside the backup set | F33, F14 FRAME | UNVERIFIED |
| G23 | Silent key generation when a key is missing | F14 FRAME | UNVERIFIED |
| G24 | Small platform items (SSO fetch, pool timeouts, body cap, forwarded IPs, `/health`, scheduler package) | F45 FRAME (if free) | UNVERIFIED; scheduler deletion not taken |
| D-row 1 to 2 | F29 engine half and F43 already merged | F29, F43 | CLOSED (#336, CLI #69) |
| D-row 3 | `pk_uniqueness` exists, not catalog-level or OOC safe | F36 | as stated |
| D-row 4 | F23 engine half is NEW | F23 FRAME | UNVERIFIED |
| D-row 5 to 6 | Engine pins disagree; 12.2 likely closed | D-4; notes | CLOSED; full-frame only |
| D-row 7 | Shipped log stale (gap 2026-10-27 to 2026-10-30) | process | OPEN |
| Slice 0 | 14.1 closed (#360); cross-column read handled by `order_work`; 11.1 + 12.3 and 12.1 rows 11, 13; 20.1 overstated | slice 0 | as stated |
| MIRROR-1 | `ci/vendored.toml` `[[mirror]]` rows: the check reads only the copied file's header, so a stale `blob_sha256` or `commit` is never caught (found stale before engine #395) | T0021, 2026-11-07 | OPEN; sentry follow-up, not V1-blocking |
