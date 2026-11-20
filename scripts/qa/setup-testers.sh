#!/usr/bin/env bash
# Owner-run, once per node: create the QA tester OS users (QA-BETA plan 5.1).
#
# Each tester user gets a home that holds only the installed release bundle, a copy of the
# public docs and a read-only link to the corpus. The users cannot read repository checkouts:
# keep checkouts mode 0700 under your own account. The launcher never creates users.
#
# Default is a dry run that prints the plan. Pass --apply to change the node. Needs root.
# Never run this from a test.
#
#   sudo scripts/qa/setup-testers.sh --bundle DIR --docs DIR --corpus DIR [--apply]
#
# Linux uses useradd. macOS uses sysadminctl.
set -euo pipefail

SLUGS=(p1 p2 p3 p4 p5 checklist docwalk)
GROUP=qatesters
APPLY=0
BUNDLE=""
DOCS=""
CORPUS=""

usage() {
  sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
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
for d in "$BUNDLE" "$DOCS" "$CORPUS"; do
  [ -d "$d" ] || { echo "error: not a folder: $d" >&2; exit 2; }
done

OS="$(uname -s)"
case "$OS" in
  Linux) HOME_ROOT=/home ;;
  Darwin) HOME_ROOT=/Users ;;
  *) echo "error: unsupported system: $OS" >&2; exit 2 ;;
esac

run() {
  if [ "$APPLY" -eq 1 ]; then
    "$@"
  else
    echo "dry run: $*"
  fi
}

if [ "$APPLY" -eq 1 ] && [ "$(id -u)" -ne 0 ]; then
  echo "error: --apply needs root" >&2
  exit 2
fi

make_group_linux() {
  getent group "$GROUP" > /dev/null || run groupadd "$GROUP"
}

make_user_linux() {
  local user="$1"
  id "$user" > /dev/null 2>&1 || run useradd --create-home --home-dir "$HOME_ROOT/$user" \
    --shell /bin/bash --gid "$GROUP" "$user"
}

make_user_darwin() {
  local user="$1"
  id "$user" > /dev/null 2>&1 || run sysadminctl -addUser "$user" -home "$HOME_ROOT/$user" \
    -shell /bin/bash -password -
}

[ "$OS" = Linux ] && make_group_linux

for slug in "${SLUGS[@]}"; do
  user="qatester-$slug"
  home="$HOME_ROOT/$user"
  if [ "$OS" = Linux ]; then make_user_linux "$user"; else make_user_darwin "$user"; fi
  run mkdir -p "$home/bundle" "$home/docs"
  run cp -R "$BUNDLE/." "$home/bundle/"
  run cp -R "$DOCS/." "$home/docs/"
  # The corpus stays outside every home. The link is read-only because testers do not own it.
  run ln -sfn "$CORPUS" "$home/corpus"
  run chown -R "$user" "$home"
  run chmod 0700 "$home"
done

# The corpus is readable by the tester group and writable by nobody but its owner.
if [ "$OS" = Linux ]; then
  run chgrp -R "$GROUP" "$CORPUS"
  run chmod -R g+rX,go-w "$CORPUS"
else
  # macOS tester users share no group, so grant read to all and write to none but the owner.
  run chmod -R a+rX,go-w "$CORPUS"
fi

echo "done. Probe the sandbox with the S3 checks before the first pass."
