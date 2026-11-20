#!/usr/bin/env bash
# Owner-run, once per node: create the QA tester OS users (QA-BETA plan 5.1 and 10a). Safe to re-run.
#
# Root rules (plan 10a):
#   1. Root never writes, chmods, chowns or touches a path inside a directory a tester can write.
#   2. Every root file-system change goes through qa_root_dir, qa_stage_swap or qa_new_file.
#      A static test fails on a raw mkdir, chown, chmod, cp, touch, mv or redirect outside them.
#   3. Sources live under <qa>/src/ (root-owned, not group or world writable), where <qa> is
#      /var/lib/decoy-qa. Create that folder and put the bundle, docs and corpus trees in it first.
#
# Per tester, with <t> = <qa>/testers/qatester-<slug> (group qatester-<slug>, plus qatesters):
#   <t>                       root:<user> 0750
#   <t>/bundle, <t>/docs      root:<user>, files 0640 or 0750, replaced as whole trees each run
#   <t>/secret/ci-secret      p3 only: random test secret, never a real one, root:<user> 0640
#   <t>/fault, <t>/fault.ok   p5 only: size-capped volume for the disk-full cell, and its marker
#   <t>/img/fault.dmg         macOS p5 only: the image file, root-owned, mode 0600
#   <t>/work                  the tester's HOME, <user> 0700, made once; a rerun only checks it
#   <t>/work/inbox            made by the tester, never by this script
# <qa>/corpus is root:qatesters 0750 and is replaced as a whole tree each run.
#
# The users cannot read repository checkouts: keep checkouts mode 0700 under your own account.
# The launcher never creates users. Default is a dry run that prints the plan. Pass --apply as
# root to change the node. Never run this from a test. The tests set QA_SETUP_TEST_ROOT, which
# moves <qa> under that folder and skips users, groups, chown, mounts and the root check.
#
#   sudo scripts/qa/setup-testers.sh --bundle DIR --docs DIR --corpus DIR [--apply]
set -euo pipefail

SLUGS="p1 p2 p3 p4 p5 checklist docwalk"
GROUP=qatesters
APPLY=0
BUNDLE=""
DOCS=""
CORPUS=""
TEST_ROOT="${QA_SETUP_TEST_ROOT:-}"

die() { echo "error: $*" >&2; exit 2; }

usage() {
  sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
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
if [ -z "$BUNDLE" ] || [ -z "$DOCS" ] || [ -z "$CORPUS" ]; then usage; fi

OS="$(uname -s)"
case "$OS" in Linux | Darwin) ;; *) die "unsupported system: $OS" ;; esac
if [ -n "$TEST_ROOT" ]; then
  QA_ROOT="${TEST_ROOT%/}/var/lib/decoy-qa"
  OWNER_UID="$(id -u)"
  ROOT_OWNER="$(id -un)"
  ROOT_GROUP="$(id -gn)"
  APPLY=1
else
  QA_ROOT=/var/lib/decoy-qa
  OWNER_UID=0
  ROOT_OWNER=root
  ROOT_GROUP="$(id -gn 0)"
  if [ "$APPLY" -eq 1 ] && [ "$(id -u)" -ne 0 ]; then die "--apply needs root"; fi
fi

# Run a command that needs real accounts. Skipped in the test mode.
real() {
  if [ -n "$TEST_ROOT" ]; then return 0; fi
  "$@"
}

# The account name a path should belong to: the real tester, or the current user in a test.
owner_name() { if [ -n "$TEST_ROOT" ]; then echo "$ROOT_OWNER"; else echo "$1"; fi; }

canon_dir() { (cd -P -- "$1" 2> /dev/null && pwd -P); }

# True when a symlink resolves to a path inside $1, following the whole chain.
link_inside() {
  local root="$1" l="$2" hops=0 t d
  while [ -L "$l" ]; do
    hops=$((hops + 1))
    [ "$hops" -le 20 ] || return 1
    t="$(readlink "$l")"
    case "$t" in /*) l="$t" ;; *) l="$(dirname "$l")/$t" ;; esac
    d="$(canon_dir "$(dirname "$l")")" || return 1
    l="$d/$(basename "$l")"
  done
  case "$l/" in "$root"/*) return 0 ;; esac
  return 1
}

# Rule 3: a source is a real folder under <qa>/src, QA-owned, and holds only safe entries.
check_source() {
  local name="$1" path="${2%/}" src_root="$QA_ROOT/src" l
  case "$path" in /*) ;; *) die "$name must be an absolute path" ;; esac
  case "$path/" in */../* | */./* | *//*) die "$name must be a normalized path" ;; esac
  [ ! -L "$path" ] || die "$name is a symlink: $path"
  [ -d "$path" ] || die "$name is not a folder: $path"
  [ "$(canon_dir "$path")" = "$path" ] || die "$name has a symlink in its path: $path"
  case "$path/" in "$src_root"/?*) ;; *) die "$name must be under $src_root/" ;; esac
  [ ! -L "$src_root" ] && [ -d "$src_root" ] || die "$src_root is missing or a symlink"
  [ -n "$(find "$src_root" -maxdepth 0 -user "$OWNER_UID")" ] || die "$src_root is not owned by the node owner"
  [ -z "$(find "$src_root" -maxdepth 0 \( -perm -020 -o -perm -002 \))" ] || die "$src_root is group or world writable"
  [ -z "$(find "$path" ! -type d ! -type f ! -type l | head -1)" ] || die "$name holds a special file"
  [ -z "$(find "$path" -type f -links +1 | head -1)" ] || die "$name holds a file with more than one link"
  [ "$(find "$path" | wc -l)" = "$(find "$path" -xdev | wc -l)" ] || die "$name crosses a filesystem"
  while IFS= read -r l; do
    link_inside "$path" "$l" || die "$name holds a symlink that points outside it"
  done < <(find "$path" -type l)
}

no_overlap() {
  case "$1/" in "$2/"*) die "$1 overlaps $2" ;; esac
  case "$2/" in "$1/"*) die "$2 overlaps $1" ;; esac
}

BUNDLE="${BUNDLE%/}"
DOCS="${DOCS%/}"
CORPUS="${CORPUS%/}"
check_source bundle "$BUNDLE"
check_source docs "$DOCS"
check_source corpus "$CORPUS"
no_overlap "$BUNDLE" "$DOCS"
no_overlap "$BUNDLE" "$CORPUS"
no_overlap "$DOCS" "$CORPUS"

if [ "$APPLY" -eq 0 ]; then
  echo "dry run: would set up these testers under $QA_ROOT/testers: $SLUGS"
  echo "dry run: bundle $BUNDLE, docs $DOCS, corpus $CORPUS. Pass --apply as root to change this node."
  exit 0
fi

# ---- The three functions below are the only places root changes the file system. ----

# Make a root-owned folder. Refuse a symlink. With `once`, a folder that exists is only checked.
qa_root_dir() {
  local path="$1" owner="$2" group="$3" mode="$4" once="${5:-}"
  [ ! -L "$path" ] || die "$path is a symlink"
  if [ -e "$path" ]; then
    [ -d "$path" ] || die "$path is not a folder"
    if [ -n "$once" ]; then
      [ -n "$(find "$path" -maxdepth 0 -user "$(owner_name "$owner")" -perm "$mode")" ] || die "$path has the wrong owner or mode"
      return 0
    fi
  else
    mkdir -m 0700 "$path"
  fi
  chmod "$mode" "$path"
  real chown -h "$owner:$group" "$path"
}

# Copy a source tree into a fresh stage next to the target, lock it, then rename it over the target.
qa_stage_swap() {
  local src="$1" dest="$2" owner="$3" group="$4" stage
  [ ! -L "$dest" ] || die "$dest is a symlink"
  [ ! -e "$dest" ] || [ -d "$dest" ] || die "$dest is not a folder"
  stage="$(mktemp -d "$dest.stage.XXXXXX")"
  cp -RP "$src/." "$stage/"
  real find "$stage" -xdev -exec chown -h "$owner:$group" {} +
  chmod -R u=rwX,g=rX,o= "$stage"
  if [ -e "$dest" ]; then mv "$dest" "$stage.old"; fi
  mv "$stage" "$dest"
  if [ -e "$stage.old" ]; then rm -rf "$stage.old"; fi
}

# Create a new file under a temporary name in a root-owned folder, then rename it into place.
qa_new_file() {
  local path="$1" owner="$2" group="$3" mode="$4" kind="$5" tmp
  [ ! -L "$path" ] || die "$path is a symlink"
  [ ! -e "$path" ] || [ -f "$path" ] || die "$path is not a file"
  tmp="$(dirname "$path")/.new.$$.$(basename "$path")"
  case "$kind" in
    secret) (set -C; umask 077; head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$tmp") ;;
    empty) (set -C; umask 077; : > "$tmp") ;;
    image) (umask 077; hdiutil create -size 64m -fs APFS -volname qa-fault "$tmp" > /dev/null) ;;
    *) die "unknown file kind" ;;
  esac
  chmod "$mode" "$tmp"
  real chown -h "$owner:$group" "$tmp"
  mv -f "$tmp" "$path"
}

# ---- Accounts ----

group_gid() {
  if [ "$OS" = Linux ]; then getent group "$1" | cut -d: -f3
  else dscl . -read "/Groups/$1" PrimaryGroupID | awk '{print $2}'; fi
}

ensure_group() {
  if [ "$OS" = Linux ]; then
    getent group "$1" > /dev/null || groupadd "$1"
  else
    dscl . -read "/Groups/$1" > /dev/null 2>&1 || dseditgroup -o create "$1"
  fi
}

# Create the account, or refuse when an existing one has the wrong home or group.
ensure_user() {
  local user="$1" home="$2" have_home have_gid
  if id "$user" > /dev/null 2>&1; then
    if [ "$OS" = Linux ]; then
      have_home="$(getent passwd "$user" | cut -d: -f6)"
      have_gid="$(id -g "$user")"
      id -nG "$user" | tr ' ' '\n' | grep -qx "$GROUP" || die "$user is not in group $GROUP"
    else
      have_home="$(dscl . -read "/Users/$user" NFSHomeDirectory | awk '{print $2}')"
      have_gid="$(dscl . -read "/Users/$user" PrimaryGroupID | awk '{print $2}')"
      dseditgroup -o checkmember -m "$user" "$GROUP" > /dev/null 2>&1 || die "$user is not in group $GROUP"
    fi
    [ "$have_home" = "$home" ] || die "$user exists with a different home: $have_home"
    [ "$have_gid" = "$(group_gid "$user")" ] || die "$user exists with a different primary group"
  elif [ "$OS" = Linux ]; then
    useradd --no-create-home --home-dir "$home" --shell /bin/bash --gid "$user" --groups "$GROUP" "$user"
  else
    sysadminctl -addUser "$user" -home "$home" -shell /bin/bash -GID "$(group_gid "$user")" -password -
    dseditgroup -o edit -a "$user" -t user "$GROUP"
  fi
}

# A size-capped volume for the P5 disk-full cell, so the host filesystem is never filled.
make_fault_volume() {
  local user="$1" t="$2" fresh=0
  qa_root_dir "$t/fault" root "$user" 0750
  if [ "$OS" = Linux ]; then
    if ! mountpoint -q "$t/fault"; then
      mount -t tmpfs -o "size=64m,mode=0700,uid=$(id -u "$user"),gid=$(id -g "$user")" tmpfs "$t/fault"
    fi
  else
    qa_root_dir "$t/img" root "$user" 0700
    [ -e "$t/img/fault.dmg" ] || qa_new_file "$t/img/fault.dmg" root root 0600 image
    if ! mount | grep -qF " on $t/fault "; then
      hdiutil attach -nobrowse -mountpoint "$t/fault" "$t/img/fault.dmg" > /dev/null
      fresh=1
    fi
    if [ "$fresh" -eq 1 ]; then qa_root_dir "$t/fault" "$user" "$user" 0700; fi
  fi
  qa_new_file "$t/fault.ok" root root 0644 empty
}

if [ -z "$TEST_ROOT" ]; then ensure_group "$GROUP"; fi
qa_root_dir "$QA_ROOT/testers" "$ROOT_OWNER" "$ROOT_GROUP" 0755
if [ -z "$TEST_ROOT" ]; then
  qa_stage_swap "$CORPUS" "$QA_ROOT/corpus" root "$GROUP"
else
  qa_stage_swap "$CORPUS" "$QA_ROOT/corpus" "$ROOT_OWNER" "$ROOT_GROUP"
fi

for slug in $SLUGS; do
  user="qatester-$slug"
  t="$QA_ROOT/testers/$user"
  [ -n "$TEST_ROOT" ] || ensure_group "$user"
  [ -n "$TEST_ROOT" ] || ensure_user "$user" "$t"
  if [ -n "$TEST_ROOT" ]; then grp="$ROOT_GROUP"; else grp="$user"; fi
  qa_root_dir "$t" "$ROOT_OWNER" "$grp" 0750
  qa_stage_swap "$BUNDLE" "$t/bundle" "$ROOT_OWNER" "$grp"
  qa_stage_swap "$DOCS" "$t/docs" "$ROOT_OWNER" "$grp"
  qa_root_dir "$t/work" "$user" "$grp" 0700 once
  if [ "$slug" = p3 ]; then
    qa_root_dir "$t/secret" "$ROOT_OWNER" "$grp" 0750
    qa_new_file "$t/secret/ci-secret" "$ROOT_OWNER" "$grp" 0640 secret
  fi
  if [ "$slug" = p5 ] && [ -z "$TEST_ROOT" ]; then make_fault_volume "$user" "$t"; fi
done

echo "done. Run the S3 probes before the first pass."
