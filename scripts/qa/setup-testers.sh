#!/usr/bin/env bash
# Owner-run, once per node: create the QA tester OS users (QA-BETA plan 5.1). Safe to re-run.
#
# Layout per tester, with H = <home root>/qatester-<slug>:
#   H            root-owned, group qatesters, mode 0750 (the tester cannot swap anything in it)
#   H/bundle     the installed release bundle, root-owned, read-only for the tester
#   H/docs       a copy of the public docs, root-owned, read-only for the tester
#   H/corpus     a link to the shared corpus folder (group qatesters, no access for other)
#   H/work       the tester's own HOME and workspace, mode 0700
#   H/secret     a random test secret file (mode 0600, never a real secret), for P3
#   H/fault      a size-capped volume for the P5 disk-full cell (created for p5 only)
# The users cannot read repository checkouts: keep checkouts mode 0700 under your own account.
# The launcher never creates users.
#
# Default is a dry run that prints the plan. Pass --apply to change the node. Needs root.
# Never run this from a test. The tests set QA_SETUP_TEST_ROOT, which keeps every path under that
# folder and skips users, groups, chown, mounts and the root check; modes and trees still apply.
#
#   sudo scripts/qa/setup-testers.sh --bundle DIR --docs DIR --corpus DIR [--apply]
#
# --bundle and --docs are existing absolute folders. --corpus is a folder this script owns: it
# must not exist, or be empty, or hold the marker file this script wrote. Fill it after setup
# and run setup again to fix its modes.
set -euo pipefail

SLUGS="p1 p2 p3 p4 p5 checklist docwalk"
GROUP=qatesters
MARKER=.decoy-qa-corpus
APPLY=0
BUNDLE=""
DOCS=""
CORPUS=""
TEST_ROOT="${QA_SETUP_TEST_ROOT:-}"

die() { echo "error: $*" >&2; exit 2; }

usage() {
  sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --bundle) BUNDLE="${2:?--bundle needs a folder}"; shift ;;
    --docs) DOCS="${2:?--docs needs a folder}"; shift ;;
    --corpus) CORPUS="${2:?--corpus needs a folder}"; shift ;;
    -h | --help) usage ;;
    *) echo "error: unknown argument: $1" >&2; usage ;;
  esac
  shift
done
[ -n "$BUNDLE" ] && [ -n "$DOCS" ] && [ -n "$CORPUS" ] || usage

OS="$(uname -s)"
case "$OS" in
  Linux) HOME_ROOT=/home ;;
  Darwin) HOME_ROOT=/Users ;;
  *) die "unsupported system: $OS" ;;
esac
if [ -n "$TEST_ROOT" ]; then
  HOME_ROOT="$TEST_ROOT/home"
  APPLY=1
  mkdir -p "$HOME_ROOT"
elif [ "$APPLY" -eq 1 ] && [ "$(id -u)" -ne 0 ]; then
  die "--apply needs root"
fi

# Run a command. A dry run exits before the first change, so this always runs.
run() { "$@"; }
# Run a command that needs real accounts. Skipped in the test mode.
real() {
  if [ -n "$TEST_ROOT" ]; then return 0; fi
  run "$@"
}

canon_dir() { (cd -P -- "$1" 2> /dev/null && pwd -P); }

# A tree root must be an absolute, normalized path with no symlink in it and at least 3 levels.
check_root() {
  local name="$1" path="${2%/}"
  case "$path" in /*) ;; *) die "$name must be an absolute path" ;; esac
  case "$path/" in */../* | */./* | *//*) die "$name must be a normalized path" ;; esac
  [ "$(printf '%s' "$path" | tr -cd / | wc -c | tr -d ' ')" -ge 3 ] || die "$name is too broad: $path"
  [ ! -L "$path" ] || die "$name is a symlink: $path"
  if [ -e "$path" ]; then
    [ -d "$path" ] || die "$name is not a folder: $path"
    [ "$(canon_dir "$path")" = "$path" ] || die "$name has a symlink in its path: $path"
  else
    [ "$name" = corpus ] || die "$name does not exist: $path"
    [ "$(canon_dir "$(dirname "$path")")" = "$(dirname "$path")" ] || die "$name has a symlink in its path: $path"
  fi
}

no_overlap() {
  case "$1/" in "$2/"*) die "$1 overlaps $2" ;; esac
  case "$2/" in "$1/"*) die "$2 overlaps $1" ;; esac
}

BUNDLE="${BUNDLE%/}"
DOCS="${DOCS%/}"
CORPUS="${CORPUS%/}"
check_root bundle "$BUNDLE"
check_root docs "$DOCS"
check_root corpus "$CORPUS"
HOME_ROOT="${HOME_ROOT%/}"
for pair in "$BUNDLE $DOCS" "$BUNDLE $CORPUS" "$DOCS $CORPUS" "$BUNDLE $HOME_ROOT" "$DOCS $HOME_ROOT" "$CORPUS $HOME_ROOT"; do
  # shellcheck disable=SC2086
  no_overlap $pair
done

real_group() {
  [ -z "$TEST_ROOT" ] || return 0
  if [ "$OS" = Linux ]; then
    getent group "$GROUP" > /dev/null || run groupadd "$GROUP"
  else
    dscl . -read "/Groups/$GROUP" > /dev/null 2>&1 || run dseditgroup -o create "$GROUP"
  fi
}

# Create the account, or refuse when an existing one has the wrong home or group.
ensure_user() {
  local user="$1" home="$2"
  [ -z "$TEST_ROOT" ] || return 0
  if id "$user" > /dev/null 2>&1; then
    local have_home have_gid want_gid
    if [ "$OS" = Linux ]; then
      have_home="$(getent passwd "$user" | cut -d: -f6)"
      have_gid="$(id -g "$user")"
      want_gid="$(getent group "$GROUP" | cut -d: -f3)"
      [ "$have_gid" = "$want_gid" ] || die "$user exists with a different primary group"
    else
      have_home="$(dscl . -read "/Users/$user" NFSHomeDirectory | awk '{print $2}')"
      dseditgroup -o checkmember -m "$user" "$GROUP" > /dev/null 2>&1 || die "$user is not in group $GROUP"
    fi
    [ "$have_home" = "$home" ] || die "$user exists with a different home: $have_home"
  elif [ "$OS" = Linux ]; then
    run useradd --create-home --home-dir "$home" --shell /bin/bash --gid "$GROUP" "$user"
  else
    run sysadminctl -addUser "$user" -home "$home" -shell /bin/bash -password -
    run dseditgroup -o edit -a "$user" -t user "$GROUP"
  fi
}

# Replace $2 with the complete tree staged at $1, by renames only.
swap_in() {
  local stage="$1" dest="$2" old="$1.old"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    [ -d "$dest" ] && [ ! -L "$dest" ] || die "$dest is not a real folder"
    mv "$dest" "$old"
  fi
  mv "$stage" "$dest"
  [ ! -d "$old" ] || [ -L "$old" ] || rm -rf "$old"
}

# Copy a source tree into a fresh root-made staging folder, lock it, then swap it in.
install_tree() {
  local src="$1" home="$2" name="$3" stage
  [ ! -L "$home/$name" ] || die "$home/$name is a symlink"
  stage="$(mktemp -d "$home/.stage.XXXXXX")"
  cp -RP "$src/." "$stage/"
  real find "$stage" -xdev -exec chown -h "root:$GROUP" {} +
  chmod -R go-w,o-rwx "$stage"
  chmod -R g+rX "$stage"
  swap_in "$stage" "$home/$name"
}

make_secret() {
  local dir="$1/secret" file="$1/secret/ci-secret"
  [ ! -L "$dir" ] || die "$dir is a symlink"
  mkdir -p "$dir"
  chmod 0700 "$dir"
  if [ ! -e "$file" ]; then
    (umask 077 && head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$file")
  fi
  [ ! -L "$file" ] || die "$file is a symlink"
  chmod 0600 "$file"
  real chown -h "$2" "$dir" "$file"
}

# A size-capped volume for the P5 disk-full cell, so the host filesystem is never filled.
make_fault_volume() {
  local user="$1" home="$2"
  [ -z "$TEST_ROOT" ] || return 0
  [ ! -L "$home/fault" ] || die "$home/fault is a symlink"
  mkdir -p "$home/fault"
  if [ "$OS" = Linux ]; then
    mountpoint -q "$home/fault" || run mount -t tmpfs -o "size=64m,mode=0700,uid=$user" tmpfs "$home/fault"
    grep -qF " $home/fault " /etc/fstab || run sh -c "echo 'tmpfs $home/fault tmpfs size=64m,mode=0700,uid=$user 0 0' >> /etc/fstab"
  else
    [ -e "$home/fault.dmg" ] || run hdiutil create -size 64m -fs APFS -volname "qa-fault" -o "$home/fault.dmg"
    mount | grep -qF " on $home/fault " || run hdiutil attach -nobrowse -mountpoint "$home/fault" "$home/fault.dmg"
  fi
  run chown -h "$user" "$home/fault"
  run touch "$home/fault/.qa-bounded"
}

fix_corpus() {
  if [ -e "$CORPUS" ]; then
    if [ ! -e "$CORPUS/$MARKER" ] && [ -n "$(ls -A "$CORPUS")" ]; then
      die "corpus folder exists, is not empty and was not made by this script: $CORPUS"
    fi
  else
    mkdir "$CORPUS"
  fi
  : > "$CORPUS/$MARKER"
  real chgrp -R "$GROUP" "$CORPUS"
  # The tester group may read. Nobody else has any access.
  chmod -R o-rwx,g+rX,g-w "$CORPUS"
  chmod 0750 "$CORPUS"
}

if [ "$APPLY" -eq 0 ]; then
  echo "dry run: would set up these testers under $HOME_ROOT: $SLUGS"
  echo "dry run: bundle $BUNDLE, docs $DOCS, corpus $CORPUS. Pass --apply as root to change this node."
  exit 0
fi

real_group
fix_corpus

for slug in $SLUGS; do
  user="qatester-$slug"
  home="$HOME_ROOT/$user"
  [ ! -L "$home" ] || die "$home is a symlink"
  ensure_user "$user" "$home"
  if [ -n "$TEST_ROOT" ]; then mkdir -p "$home"; fi
  [ -d "$home" ] || die "$home is missing"
  real chown "root:$GROUP" "$home"
  chmod 0750 "$home"
  install_tree "$BUNDLE" "$home" bundle
  install_tree "$DOCS" "$home" docs
  [ ! -e "$home/corpus" ] || [ -L "$home/corpus" ] || die "$home/corpus is not a link"
  rm -f "$home/corpus"
  ln -s "$CORPUS" "$home/corpus"
  [ ! -L "$home/work" ] || die "$home/work is a symlink"
  mkdir -p "$home/work"
  real chown -h "$user" "$home/work"
  chmod 0700 "$home/work"
  make_secret "$home" "$user"
  [ "$slug" != p5 ] || make_fault_volume "$user" "$home"
done

echo "done. Run the S3 probes before the first pass."
