#!/bin/sh
# Decoy CLI installer: self-hosted, signed, per-platform bundle.
#
# Lays down a managed, self-contained runtime (bundled CPython + matched
# engine/native/CLI wheels) under ~/.decoy and a `decoy` launcher on PATH. The user
# brings no Python of their own.
#
# Trust model (config-secrets-and-supply-chain + security): this script arrives over
# TLS from the Decoy host and PINS the release public key inline. It verifies the
# hosted version document's Ed25519 signature AND the bundle's Ed25519 signature AND a
# SHA-256 checksum against the signed document BEFORE anything is laid down. A failed
# signature OR checksum is a HARD REFUSAL, never a warning-and-continue. Established
# methodology: Ed25519 via a system tool; no hand-rolled verification. The tool is chosen
# once, before any download, and only if it passes a known-answer test (a good signature
# accepted, a changed message rejected):
#   openssl  : the raw Ed25519 signature produced by `decoy.distribution.signing` /
#              `packaging_tools.sign_release` (`<file>.sig`), checked with
#              `openssl pkeyutl -verify -rawin`, the exact bytes `decoy upgrade` checks.
#              Needs OpenSSL 3; LibreSSL 3.3 (stock macOS) and OpenSSL 1.1.1 cannot.
#   sshsig   : the same release key's OpenSSH signature (`<file>.sshsig`, namespace
#              decoy-release), checked with `ssh-keygen -Y verify` against the pinned
#              OpenSSH form of the key. Stock macOS ships a capable ssh-keygen.
# With neither, the script exits 69 ("cannot verify") before downloading anything.
#
# Freshness (TUF-style timestamp "version"/"expires"): the signed document carries a
# monotonic `serial` and an `expires` deadline. An expired document is refused, and the
# highest accepted serial / newest latest are kept in $DECOY_HOME/trust_state.json (shared
# with `decoy upgrade`, decoy.distribution.installer) so a replayed older signed document
# cannot freeze or downgrade a client.
#
# Usage:
#   curl -LsSf https://trydecoy.com/cli/install.sh | sh
#   sh install.sh [--version X.Y.Z] [uninstall]
#
# Env overrides (also used by the test harness):
#   DECOY_HOME            install root (default: ~/.decoy)
#   DECOY_BIN_DIR         launcher dir on PATH (default: ~/.local/bin)
#   DECOY_VERSION_URL     version document URL (default: the hosted endpoint)
#   DECOY_BUNDLE_BASE     base for pinned (non-latest) bundles: <base>/v<version>/decoy-<version>-<target>.tar.gz
#                         (default: the GitHub release downloads of louiskeep/decoy)
#   DECOY_RELEASE_PUBKEY_FILE  override the pinned key (dev/test builds ONLY: honored solely
#                         while PINNED_PUBKEY below is still the placeholder, with a loud
#                         warning; ignored with a warning once a release injects the real key)
#   DECOY_LOCAL_BUNDLE    install from a local tarball instead of downloading (offline)
#   DECOY_OPENSSL         absolute path of an OpenSSL 3 `openssl` to use. When set it is the only
#                         candidate: if it fails the known answer the install exits 69 and no
#                         other verifier is tried.
set -eu

DEFAULT_VERSION_URL="https://trydecoy.com/cli/version.json"
DEFAULT_BUNDLE_BASE="https://github.com/louiskeep/decoy/releases/download"
DECOY_HOME="${DECOY_HOME:-$HOME/.decoy}"
DECOY_BIN_DIR="${DECOY_BIN_DIR:-$HOME/.local/bin}"
DECOY_VERSION_URL="${DECOY_VERSION_URL:-$DEFAULT_VERSION_URL}"

# --- pinned release public key -------------------------------------------------
# DEV/PLACEHOLDER key. Replaced at launch with the real release key's public half
# (generated once in the release secret store; see packaging_tools/README.md). The matching
# private key signs the version document and every bundle.
PINNED_PUBKEY='-----BEGIN PUBLIC KEY-----
__DECOY_RELEASE_PUBLIC_KEY__
-----END PUBLIC KEY-----'

# Same release key as PINNED_PUBKEY, as the base64 ssh-ed25519 blob that ssh-keygen -Y verify
# reads (it cannot import the PEM). `packaging_tools/sign_release.py inject-keys` fills both and
# `check-keys` proves they are one key.
PINNED_SSH_PUBKEY='__DECOY_RELEASE_SSH_PUBLIC_KEY__'

# Known answer for the SSHSIG route: a throwaway key (private half discarded) signed the one
# byte 0x72 in namespace decoy-release. A verifier that accepts it and rejects 0x73 is real.
KAT_SSH_PUBKEY='AAAAC3NzaC1lZDI1NTE5AAAAIH7vnyAF/LccI7MtEWXzWlBQ2gudYsUsOWkcHtw5FX25'
KAT_SSHSIG='-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgfu+fIAX8txwjsy0RZfNaUFDaC5
1ixSw5aRwe3DkVfbkAAAANZGVjb3ktcmVsZWFzZQAAAAAAAAAGc2hhNTEyAAAAUwAAAAtz
c2gtZWQyNTUxOQAAAEB+iuN19bqZQ1G1GtU7swHFU6KZmfoimlg1V+XtaVZ0Sl2l+VEFk8
8E3UhqgWQjknqU9A958r4mZ/pn8MmDXyUC
-----END SSH SIGNATURE-----'

# Known answer for the OpenSSL route: RFC 8032 section 7.1 TEST 2 (public key as SPKI PEM, message
# 0x72, signature as base64 because the real check reads base64 sidecars). 0x73 must fail.
KAT_PEM='-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAPUAXw+hDiVqStwqnTRt+vJyYLM8uxJaMwM1V8Sr0Zgw=
-----END PUBLIC KEY-----'
KAT_SIG_B64='kqAJqfDUyrhyDoILX2QlQKKye1QWUD+Ps3YiI+vbadoIWsHkPhWZbkWPNhPQ8R2MOHsurrQwKu6wDSkWErsMAA=='

SSH_IDENTITY="decoy-release@decoy.dev"
SSH_NAMESPACE="decoy-release"
# Homebrew, MacPorts and Linuxbrew locations for an OpenSSL 3, tried after PATH. Globs are intended.
OPENSSL_FALLBACKS="/opt/homebrew/opt/openssl@*/bin/openssl /opt/homebrew/opt/openssl/bin/openssl /opt/homebrew/bin/openssl /usr/local/opt/openssl@*/bin/openssl /usr/local/bin/openssl /opt/local/bin/openssl /home/linuxbrew/.linuxbrew/bin/openssl"
SSH_KEYGEN_FALLBACK="/usr/bin/ssh-keygen"

die() { printf 'decoy install: %s\n' "$*" >&2; exit 1; }
info() { printf 'decoy install: %s\n' "$*" >&2; }
need() { command -v "$1" >/dev/null 2>&1 || die "required tool not found: $1"; }

detect_target() {
  _os=$(uname -s 2>/dev/null || echo unknown)
  _arch=$(uname -m 2>/dev/null || echo unknown)
  case "$_arch" in
    x86_64|amd64) _arch=x86_64 ;;
    aarch64) _arch=aarch64 ;;
    arm64) _arch=arm64 ;;
  esac
  case "$_os" in
    Linux)
      case "$_arch" in
        x86_64) echo linux-x86_64 ;;
        aarch64) echo linux-aarch64 ;;
        *) echo "" ;;
      esac ;;
    Darwin)
      case "$_arch" in
        arm64) echo macos-arm64 ;;
        # macOS Intel is intentionally unsupported at launch (not in the matrix).
        *) echo "" ;;
      esac ;;
    # Windows is gated off the advertised matrix this cycle (POSIX-shaped managed
    # runtime; the Windows lifecycle is unverified). Refuse rather than install an
    # unrunnable path. See docs/distribution/decisions/2026-10-26-windows-target-gated.md.
    MINGW*|MSYS*|CYGWIN*|Windows_NT) echo "" ;;
    *) echo "" ;;
  esac
}

fetch() {
  # fetch URL OUTFILE -- curl or wget, failing loudly on HTTP error.
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf "$1" -o "$2"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$1" -O "$2"
  else
    die "need curl or wget to download"
  fi
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

# Low-level checks. Only verify_file (the real checks) and the known-answer tests call them, so the
# probe exercises the same commands the install relies on. stdin is always a named file or
# /dev/null: under `curl | sh` an inherited stdin would let the tool swallow the rest of the script.
verify_sig() {
  # verify_sig OPENSSL DATA_FILE SIG_B64_FILE PUBKEY_PEM -- raw detached Ed25519.
  _raw="$WORK/raw.sig"
  "$1" base64 -d -A -in "$3" -out "$_raw" </dev/null 2>/dev/null || { rm -f "$_raw"; return 1; }
  if "$1" pkeyutl -verify -pubin -inkey "$4" -rawin -in "$2" -sigfile "$_raw" </dev/null >/dev/null 2>&1; then
    rm -f "$_raw"; return 0
  fi
  rm -f "$_raw"; return 1
}

verify_sshsig() {
  # verify_sshsig SSH_KEYGEN ALLOWED_SIGNERS DATA_FILE SIGNATURE_FILE. `-Y verify` binds the pinned
  # key through the allowed-signers file; `-Y check-novalidate` would accept any key.
  "$1" -Y verify -f "$2" -I "$SSH_IDENTITY" -n "$SSH_NAMESPACE" -s "$4" < "$3" >/dev/null 2>&1
}

verify_file() {
  # verify_file DATA_FILE SIDECAR_BASE -- the only signature check. The sidecar is
  # SIDECAR_BASE.sig or SIDECAR_BASE.sshsig and is never derived from DATA_FILE.
  # Anything but a selected verifier plus a present sidecar returns 1.
  case "$VERIFIER_KIND" in
    openssl) [ -f "$2.sig" ] && verify_sig "$VERIFIER_BIN" "$1" "$2.sig" "$PUBKEY" ;;
    sshsig) [ -f "$2.sshsig" ] && verify_sshsig "$VERIFIER_BIN" "$WORK/allowed_signers" "$1" "$2.sshsig" ;;
    *) return 1 ;;
  esac
}

write_allowed_signers() {
  # write_allowed_signers FILE BASE64_KEY_BLOB
  printf '%s namespaces="%s" ssh-ed25519 %s\n' "$SSH_IDENTITY" "$SSH_NAMESPACE" "$2" > "$1"
}

kat_openssl() {
  # Passes only if the binary accepts the RFC 8032 signature on 0x72 and rejects it on 0x73.
  mkdir -p "$WORK/kat" || return 1
  printf '%s\n' "$KAT_PEM" > "$WORK/kat/pub.pem"
  printf '%s\n' "$KAT_SIG_B64" > "$WORK/kat/sig.b64"
  printf r > "$WORK/kat/good"; printf s > "$WORK/kat/bad"
  verify_sig "$1" "$WORK/kat/good" "$WORK/kat/sig.b64" "$WORK/kat/pub.pem" || return 1
  verify_sig "$1" "$WORK/kat/bad" "$WORK/kat/sig.b64" "$WORK/kat/pub.pem" && return 1
  return 0
}

kat_sshsig() {
  mkdir -p "$WORK/kat" || return 1
  write_allowed_signers "$WORK/kat/allowed_signers" "$KAT_SSH_PUBKEY"
  printf '%s\n' "$KAT_SSHSIG" > "$WORK/kat/sig.sshsig"
  printf r > "$WORK/kat/good"; printf s > "$WORK/kat/bad"
  verify_sshsig "$1" "$WORK/kat/allowed_signers" "$WORK/kat/good" "$WORK/kat/sig.sshsig" || return 1
  verify_sshsig "$1" "$WORK/kat/allowed_signers" "$WORK/kat/bad" "$WORK/kat/sig.sshsig" && return 1
  return 0
}

note_tried() { TRIED="${TRIED}decoy install:   tried: $*
"; }

refuse_unverifiable() {
  # Exit 69 (EX_UNAVAILABLE): the host cannot check signatures. Never says INVALID or tampering,
  # because nothing was found wrong with the release.
  {
    printf 'decoy install: cannot verify Ed25519 signatures: no usable openssl or ssh-keygen was found. Nothing was downloaded or installed.\n'
    printf '%s' "$TRIED"
    printf 'decoy install: macOS: /usr/bin/ssh-keygen ships with macOS; restore it, or brew install openssl@3\n'
    printf 'decoy install: Linux: OpenSSL 3.0 or newer is required (RHEL 8: dnf install openssl3 from EPEL; Ubuntu 20.04 / Debian 10: a newer distro or brew install openssl@3)\n'
    printf 'decoy install: or name one: DECOY_OPENSSL=/path/to/openssl sh install.sh\n'
  } >&2
  exit 69
}

try_openssl() {
  # try_openssl PATH -- selects it if it passes the known answer, else records why not.
  _ver=$("$1" version </dev/null 2>&1 | head -n1 | tr -cd '[:print:]' | cut -c1-80 || true)
  if kat_openssl "$1"; then
    VERIFIER_KIND=openssl; VERIFIER_BIN=$1; VERIFIER_DESC=$_ver
    return 0
  fi
  note_tried "$1 ($_ver): failed the Ed25519 known answer"
  return 1
}

select_verifier() {
  # Runs once, after $WORK exists and before any download. Sets VERIFIER_KIND and VERIFIER_BIN.
  TRIED=""; VERIFIER_KIND=""; VERIFIER_BIN=""; VERIFIER_DESC=""
  if [ -n "${DECOY_OPENSSL:-}" ]; then
    # An explicit choice is never second-guessed: no fallback, so a typo cannot silently verify
    # with a different binary.
    case "$DECOY_OPENSSL" in
      /*) ;;
      *) note_tried "$DECOY_OPENSSL (DECOY_OPENSSL must be an absolute path)"; refuse_unverifiable ;;
    esac
    if [ -f "$DECOY_OPENSSL" ] && [ -x "$DECOY_OPENSSL" ]; then
      try_openssl "$DECOY_OPENSSL" || true
    else
      note_tried "$DECOY_OPENSSL (DECOY_OPENSSL is not an executable file)"
    fi
    [ -n "$VERIFIER_KIND" ] || refuse_unverifiable
  else
    for _c in "$(command -v openssl 2>/dev/null || true)" "$(command -v openssl3 2>/dev/null || true)" $OPENSSL_FALLBACKS; do
      if [ -n "$_c" ] && [ -f "$_c" ] && [ -x "$_c" ] && try_openssl "$_c"; then break; fi
    done
    if [ -z "$VERIFIER_KIND" ]; then
      case "$PINNED_SSH_PUBKEY" in
        *"__DECOY_RELEASE_SSH_PUBLIC""_KEY__"*) note_tried "ssh-keygen (the OpenSSH release key is not pinned in this build)" ;;
        *)
          for _c in "$(command -v ssh-keygen 2>/dev/null || true)" "$SSH_KEYGEN_FALLBACK"; do
            [ -n "$_c" ] && [ -f "$_c" ] && [ -x "$_c" ] || continue
            if kat_sshsig "$_c"; then
              VERIFIER_KIND=sshsig; VERIFIER_BIN=$_c; VERIFIER_DESC="known answer passed"
              break
            fi
            note_tried "$_c: failed the SSHSIG known answer"
          done ;;
      esac
    fi
    [ -n "$VERIFIER_KIND" ] || refuse_unverifiable
  fi
  if [ "$VERIFIER_KIND" = sshsig ]; then
    write_allowed_signers "$WORK/allowed_signers" "$PINNED_SSH_PUBKEY"
  fi
  info "verifier: $VERIFIER_KIND $VERIFIER_BIN ($VERIFIER_DESC)"
}

# Whitespace-tolerant so it reads both the signed canonical document and the Python-written
# trust_state.json whatever its spacing; an unmatched field is empty and callers fail closed.
json_top_number() { grep -oE "\"$2\"[[:space:]]*:[[:space:]]*[0-9]+" "$1" | head -n1 | sed 's/.*://;s/[[:space:]]//g'; }
# Extract one string field from CANONICAL (sorted, compact) JSON. Safe because the
# document is emitted by decoy.distribution.version_document in canonical form and the values
# (version strings, hex, URLs) contain no '"' or '}'.
json_top_string() { grep -o "\"$2\":\"[^\"]*\"" "$1" | head -n1 | sed 's/.*":"//;s/"$//'; }
json_artifact_field() {
  # json_artifact_field FILE TARGET FIELD
  grep -o "\"$2\":{[^}]*}" "$1" | head -n1 \
    | grep -o "\"$3\":\"[^\"]*\"" | head -n1 | sed 's/.*":"//;s/"$//'
}

uninstall() {
  info "removing $DECOY_HOME and $DECOY_BIN_DIR/decoy"
  rm -f "$DECOY_BIN_DIR/decoy"
  rm -rf "$DECOY_HOME"
  info "uninstalled. (remove the PATH line from your shell profile if you added one.)"
  exit 0
}

ACTION=install
PIN_VERSION=""
while [ $# -gt 0 ]; do
  case "$1" in
    uninstall) ACTION=uninstall ;;
    --version) shift; PIN_VERSION="${1:-}" ;;
    --version=*) PIN_VERSION="${1#--version=}" ;;
    -h|--help) printf 'usage: install.sh [--version X.Y.Z] [uninstall]\n'; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
  shift
done

[ "$ACTION" = uninstall ] && uninstall

need tar
need mktemp

FRESHNESS_DOC=""
TARGET=$(detect_target)
[ -n "$TARGET" ] || die "unsupported platform ($(uname -s)/$(uname -m)). Supported: linux-x86_64, linux-aarch64, macos-arm64. (macOS Intel and Windows are not supported at launch.)"
info "target: $TARGET"

# First-install-only bootstrap (Cam decision). This script lays down a FRESH runtime and
# REFUSES to replace an existing one: it never moves aside, deletes, or overwrites a
# managed runtime, so it has no backup/restore/signal-trap recovery to get wrong. All
# same-version repair and every upgrade go through `decoy upgrade`, which stages a fresh
# version dir and flips `current` atomically (decoy.distribution.installer). Refuse early,
# before any download or extraction, so an existing install is never even partially touched.
VERSIONS="$DECOY_HOME/versions"
has_version_dir() {
  [ -d "$VERSIONS" ] || return 1
  for _d in "$VERSIONS"/*/; do
    # A glob with no match leaves the literal pattern, which -d rejects; default globbing
    # also excludes dot dirs, so .incoming/.staging never count as an existing install.
    if [ -d "$_d" ]; then
      return 0
    fi
  done
  return 1
}
if [ -e "$DECOY_HOME/current" ] || [ -L "$DECOY_HOME/current" ] || has_version_dir; then
  info "an existing Decoy runtime is installed at $DECOY_HOME."
  info "this bootstrap installs only; it will NOT replace an existing runtime."
  # Print a command that runs NOW: an interrupted first install can leave versions/<v>
  # with no `current` and no PATH launcher, where a bare `decoy upgrade` is not found.
  RECOVER=""
  if [ -x "$DECOY_HOME/current/decoy" ]; then
    RECOVER="$DECOY_HOME/current/decoy"
  else
    for _d in "$VERSIONS"/*/; do
      if [ -x "${_d}decoy" ]; then RECOVER="${_d}decoy"; break; fi
    done
  fi
  if [ -n "$RECOVER" ]; then
    info "to upgrade, run:  \"$RECOVER\" upgrade"
    info "to repair, run:   \"$RECOVER\" upgrade --force"
  else
    info "no runnable runtime was found under $VERSIONS; remove it first with: sh install.sh uninstall"
  fi
  info "to remove it first, run:    sh install.sh uninstall"
  die "refusing to overwrite an existing install"
fi

WORK=$(mktemp -d)
INCOMING=""
cleanup() {
  # First-install-only: nothing existing is ever moved aside, so cleanup just drops the
  # temp workdir and any quarantine dir. There is no backup/restore window to recover, so
  # an EXIT-only trap is enough -- an interruption can at worst leak a temp dir, never
  # strand `current` (which is only ever changed by the single atomic flip below).
  rm -rf "$WORK" "${INCOMING:-/nonexistent}"
}
trap cleanup EXIT

# The markers are split so the release step's placeholder substitution cannot rewrite these tests.
PUBKEY="$WORK/pub.pem"
case "$PINNED_PUBKEY" in
  *"__DECOY_RELEASE_PUBLIC""_KEY__"*) KEY_IS_PLACEHOLDER=1 ;;
  *) KEY_IS_PLACEHOLDER=0 ;;
esac
case "$PINNED_SSH_PUBKEY" in
  *"__DECOY_RELEASE_SSH_PUBLIC""_KEY__"*) SSH_KEY_IS_PLACEHOLDER=1 ;;
  *) SSH_KEY_IS_PLACEHOLDER=0 ;;
esac
# One real form and one placeholder is a broken release build, not a dev build.
[ "$KEY_IS_PLACEHOLDER" = "$SSH_KEY_IS_PLACEHOLDER" ] || die "release keys incomplete -- refusing (one pinned key form is still a placeholder)"

# Choose the verifier before the key is written and before anything is fetched.
select_verifier

# Pinned key -> PEM file (test override allowed).
if [ -n "${DECOY_RELEASE_PUBKEY_FILE:-}" ] && [ "$KEY_IS_PLACEHOLDER" = 1 ]; then
  info "WARNING: trusting the release key from DECOY_RELEASE_PUBKEY_FILE=$DECOY_RELEASE_PUBKEY_FILE instead of a pinned key. This is a dev/test build; never do this with a real install."
  cp "$DECOY_RELEASE_PUBKEY_FILE" "$PUBKEY"
else
  if [ -n "${DECOY_RELEASE_PUBKEY_FILE:-}" ]; then
    info "WARNING: DECOY_RELEASE_PUBKEY_FILE is set but IGNORED: this installer pins its release key and an environment variable cannot replace the trust anchor."
  fi
  printf '%s\n' "$PINNED_PUBKEY" > "$PUBKEY"
fi

# Base URL for pinned bundles: release assets, independent of where the version document is served.
BASE_URL="${DECOY_BUNDLE_BASE:-$DEFAULT_BUNDLE_BASE}"
BASE_SET="${DECOY_BUNDLE_BASE:-}"
conv_url() { printf '%s' "${BASE_URL%"${BASE_URL##*[!/]}"}/v$VERSION/decoy-$VERSION-$TARGET.tar.gz"; }

# Only the sidecar the selected verifier reads is fetched or required.
if [ "$VERIFIER_KIND" = sshsig ]; then SIDEXT=sshsig; else SIDEXT=sig; fi

if [ -n "${DECOY_LOCAL_BUNDLE:-}" ]; then
  # Offline / air-gapped: install from a local tarball + its signature sidecar + .sha256.
  TARBALL="$DECOY_LOCAL_BUNDLE"
  SIDECAR="$DECOY_LOCAL_BUNDLE"
  SHAFILE="$DECOY_LOCAL_BUNDLE.sha256"
  [ -f "$TARBALL" ] && [ -f "$SIDECAR.$SIDEXT" ] && [ -f "$SHAFILE" ] || die "offline install needs $TARBALL plus .$SIDEXT and .sha256 sidecars"
  VERSION="${PIN_VERSION:-local}"
  EXPECT_SHA=$(cut -d' ' -f1 < "$SHAFILE")
else
  # Fetch + verify the signed version document.
  VDOC="$WORK/version.json"
  fetch "$DECOY_VERSION_URL" "$VDOC" || die "could not fetch version document: $DECOY_VERSION_URL"
  fetch "$DECOY_VERSION_URL.$SIDEXT" "$WORK/vdoc.$SIDEXT" || die "could not fetch version-document signature"
  verify_file "$VDOC" "$WORK/vdoc" || die "version-document signature INVALID -- refusing (possible tampering)"
  info "version document signature verified"

  # The signature only proves WHO signed it; refuse a document of any other schema, as
  # `decoy upgrade` does (version_document.parse_document).
  [ "$(json_top_string "$VDOC" schema_version)" = "cli-version-document/v1" ] \
    || die "version document has an unexpected schema_version -- refusing"

  # Freshness: refuse an expired or replayed (lower-serial) signed document.
  SERIAL=$(json_top_number "$VDOC" serial)
  EXPIRES=$(json_top_string "$VDOC" expires)
  [ -n "$SERIAL" ] || die "version document has no valid 'serial' -- refusing"
  case "$EXPIRES" in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z) ;;
    *) die "version document has no valid 'expires' -- refusing" ;;
  esac
  # UTC timestamps in this fixed format compare as 14-digit integers.
  EXP_N=$(printf '%s' "$EXPIRES" | tr -dc '0-9')
  NOW_N=$(date -u +%Y%m%d%H%M%S)
  [ "$NOW_N" -lt "$EXP_N" ] || die "version document expired at $EXPIRES -- refusing (stale or replayed)"
  TRUST_STATE="$DECOY_HOME/trust_state.json"
  # Fast refusal only. The authoritative read-compare-write runs in first_install under the
  # install lock; this script never writes trust_state.json. An existing state file whose
  # serial cannot be read is a refusal, never "nothing seen".
  if [ -e "$TRUST_STATE" ]; then
    SEEN_SERIAL=$(json_top_number "$TRUST_STATE" serial || true)
    [ -n "$SEEN_SERIAL" ] || die "$TRUST_STATE exists but has no readable 'serial' -- refusing"
    if [ "$SERIAL" -lt "$SEEN_SERIAL" ]; then
      die "version document serial $SERIAL is older than the newest accepted ($SEEN_SERIAL) -- refusing (rollback/replay)"
    fi
  fi

  LATEST=$(json_top_string "$VDOC" latest)
  [ -n "$LATEST" ] || die "version document has no 'latest'"
  VERSION="${PIN_VERSION:-$LATEST}"
  # Yank enforcement (parity with installer.install_version / is_yanked): a version the
  # SIGNED document lists as yanked is refused, whether it is latest or an explicit pin.
  # The version is constrained to a PEP 440-safe charset first so it is a literal in the
  # membership test below, never a pattern.
  case "$VERSION" in
    ''|*[!0-9A-Za-z.+!_-]*) die "invalid version string: $VERSION" ;;
  esac
  YANKED_LIST=$(grep -o '"yanked":\[[^]]*\]' "$VDOC" | head -n1 || true)
  case "$YANKED_LIST" in
    *"\"$VERSION\""*) die "version $VERSION is yanked -- refusing" ;;
  esac

  FRESHNESS_DOC="$VDOC"

  if [ "$VERSION" = "$LATEST" ]; then
    URL=$(json_artifact_field "$VDOC" "$TARGET" url)
    EXPECT_SHA=$(json_artifact_field "$VDOC" "$TARGET" sha256)
    SIGURL=$(json_artifact_field "$VDOC" "$TARGET" sig)
    [ -n "$URL" ] && [ -n "$EXPECT_SHA" ] && [ -n "$SIGURL" ] || die "version document lists no bundle for $TARGET"
    if [ -n "$BASE_SET" ]; then
      # A configured base (mirror, allowlist) wins for latest too; the signed sha256 still applies.
      URL=$(conv_url)
      SIGURL="$URL.$SIDEXT"
    fi
    # The document names only the .sig URL; the .sshsig sits beside the artifact, and the
    # SSHSIG check itself proves the file, so the signed schema needs no new field.
    [ "$SIDEXT" = sig ] || SIGURL="$URL.$SIDEXT"
  else
    # Pinned to a non-latest version: the signed version document carries only the
    # latest release's checksum, so construct URLs by convention and take the checksum
    # from the published .sha256 sidecar below. That sidecar is UNSIGNED, so for a pin
    # the Ed25519 signature (verified against the pinned key, always) is the sole trust
    # anchor; the sidecar is only a best-effort corruption check and is skipped if its
    # fetch fails. "flipped byte refuses on checksum" is therefore a guarantee of the
    # latest path (signed checksum); on a pin, a flipped byte refuses on SIGNATURE.
    # Likewise the offline DECOY_LOCAL_BUNDLE path has no version document: its mandatory
    # .sha256 sidecar is unsigned corruption detection only, and yank status cannot be
    # checked (no network by design) -- the pinned-key signature is still enforced.
    URL=$(conv_url)
    SIGURL="$URL.$SIDEXT"
    EXPECT_SHA=""
  fi

  TARBALL="$WORK/decoy-$VERSION-$TARGET.tar.gz"
  SIDECAR="$WORK/bundle"
  fetch "$URL" "$TARBALL" || die "could not download bundle: $URL"
  fetch "$SIGURL" "$SIDECAR.$SIDEXT" || die "could not download bundle signature: $SIGURL"
  if [ -z "$EXPECT_SHA" ]; then
    fetch "$URL.sha256" "$TARBALL.sha256" 2>/dev/null && EXPECT_SHA=$(cut -d' ' -f1 < "$TARBALL.sha256") || true
  fi
fi

# 1) checksum (corruption + the signed checksum when we have it)
if [ -n "$EXPECT_SHA" ]; then
  GOT_SHA=$(sha256_of "$TARBALL")
  [ "$GOT_SHA" = "$EXPECT_SHA" ] || die "bundle checksum MISMATCH (expected $EXPECT_SHA got $GOT_SHA) -- refusing"
  info "bundle checksum verified"
fi
# 2) signature (the trust anchor) -- hard refusal on failure
verify_file "$TARBALL" "$SIDECAR" || die "bundle signature INVALID -- refusing (possible tampering)"
info "bundle signature verified"

# 3) quarantine-extract, then promote. Nothing is laid down live until every check
#    above passed and the native self-check below passes. ($VERSIONS was set above, where
#    the first-install-only guard already refused any existing runtime.)
mkdir -p "$VERSIONS"
INCOMING="$VERSIONS/.incoming.$$"
rm -rf "$INCOMING"; mkdir -p "$INCOMING"
tar -xzf "$TARBALL" -C "$INCOMING"
# The archive holds a single top-level dir decoy-<version>-<target>/.
BUNDLE_ROOT=$(find "$INCOMING" -mindepth 1 -maxdepth 1 -type d | head -n1)
[ -n "$BUNDLE_ROOT" ] || die "bundle archive is malformed (no top-level dir)"
PYBIN="$BUNDLE_ROOT/python/bin/python3"
[ -x "$PYBIN" ] || die "bundle is missing its interpreter"

# The bundled interpreter runs IMPORT-ISOLATED and bytecode-free (-I -B):
#  -I drops the CWD and PYTHONPATH/PYTHON* env from sys.path, so this bootstrap -- which
#     the user may curl|sh from inside any directory -- cannot be tricked into importing a
#     planted decoy/decoy_engine package from a hostile working dir and forging a passing
#     verify/self-check. Imports resolve only from the bundle's own site.
#  -B keeps bytecode writes off: the manifest does not sign caches and the verifier rejects
#     any found on disk, so these install-time checks must not leave an unsigned __pycache__
#     behind. -I ignores the env var, so the explicit -B flag is what guarantees this; the
#     export is kept to shield any non-isolated child. (See decoy.distribution.manifest.)
export PYTHONDONTWRITEBYTECODE=1

# 3a) manifest verify (defense in depth: the signature already established trust; this
#     catches a truncated/altered extraction OR a planted bytecode cache). Reuses the
#     shipped verifier.
"$PYBIN" -I -B -m decoy.distribution.verify_extracted "$BUNDLE_ROOT" || die "bundle manifest verification FAILED -- refusing"

# 3b) identity check (HIGH: a validly-signed but wrong-version/target bundle served at a
#     pinned URL must NOT be installed as if it were the requested one). Compare the
#     bundle's DECLARED version + target (BUNDLE_INFO.json, signed into the manifest)
#     against what was requested, BEFORE the bundle's interpreter runs its self-check and BEFORE any slot is created. A mismatch refuses, having
#     laid down nothing.
BINFO="$BUNDLE_ROOT/BUNDLE_INFO.json"
[ -f "$BINFO" ] || die "bundle is missing BUNDLE_INFO.json; cannot verify its identity -- refusing"
DECLARED_VERSION=$(json_top_string "$BINFO" version)
DECLARED_TARGET=$(json_top_string "$BINFO" target)
[ -n "$DECLARED_VERSION" ] && [ -n "$DECLARED_TARGET" ] || die "bundle BUNDLE_INFO.json has no version/target -- refusing"
[ "$DECLARED_TARGET" = "$TARGET" ] || die "refusing: bundle declares target '$DECLARED_TARGET' but this host is '$TARGET' -- nothing installed"
# When a specific version was requested (every path except an offline bundle with no
# --version, where VERSION is the literal 'local'), the bytes must declare it.
if [ "$VERSION" != "local" ]; then
  [ "$DECLARED_VERSION" = "$VERSION" ] || die "refusing: bundle declares version '$DECLARED_VERSION' but '$VERSION' was requested (resolution mismatch) -- versions/$VERSION left untouched"
fi

# 3c) native-present self-check: LOUD refusal if the companion is missing/mismatched.
"$PYBIN" -I -B -m decoy.distribution.selfcheck || die "native companion self-check FAILED -- refusing this install"

# 4) place the fresh runtime + flip `current` + write the PATH launcher, all under the SAME
#    per-installation lock `decoy upgrade` takes (decoy.distribution.lock), so a bootstrap
#    and an upgrade/repair can never interleave. The shell has no portable flock, so the
#    bundled interpreter runs the critical section: under the lock it re-checks that no
#    runtime exists (the early guard above is only a fast refusal), renames the verified
#    bundle into versions/$VERSION, flips `current` atomically, and writes the launcher by
#    temp-file + rename. Nothing existing is ever replaced; an interruption before the flip
#    leaves nothing live and after it the new runtime live. (Same-version repair + upgrade
#    are `decoy upgrade`'s job: it stages a fresh versions/<version>+<build> and flips.)
DEST="$VERSIONS/$VERSION"
DECOY_HOME="$DECOY_HOME" DECOY_BIN_DIR="$DECOY_BIN_DIR" \
  "$PYBIN" -I -B -m decoy.distribution.first_install "$BUNDLE_ROOT" "$VERSION" ${FRESHNESS_DOC:+"$FRESHNESS_DOC"} \
  || die "could not install $VERSION (existing runtime, concurrent install, or placement failure) -- nothing was replaced"
rm -rf "$INCOMING"

info "installed decoy $VERSION -> $DEST"
info "launcher: $DECOY_BIN_DIR/decoy"
case ":$PATH:" in
  *":$DECOY_BIN_DIR:"*) : ;;
  *) info "add $DECOY_BIN_DIR to your PATH, then restart your shell:"
     info "  export PATH=\"$DECOY_BIN_DIR:\$PATH\"" ;;
esac
info "done. run: decoy --version"
