#!/usr/bin/env bash
# Manual rollback helper — pin a specific known-good tag without
# routing through GitHub Actions.
#
# Usage:
#   sudo akki-rollback.sh                       # roll back ONE step
#   sudo akki-rollback.sh <image_tag>           # pin to a specific tag
#   sudo akki-rollback.sh --steps 2             # roll back two steps
#
# Reads /var/lib/akki/last-good-history (newline-separated, oldest first).
# DOES NOT update last-good-tag — a successful manual rollback is
# functionally equivalent to a forward deploy from the operator's POV;
# the next CI deploy will set last-good-tag again.

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "akki-rollback: must run as root (sudo)" >&2
  exit 1
fi

HISTORY="/var/lib/akki/last-good-history"
STEPS=1
TARGET=""

while (( $# )); do
  case "$1" in
    --steps) STEPS="${2:?--steps requires a number}"; shift 2 ;;
    --steps=*) STEPS="${1#--steps=}"; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"; exit 0 ;;
    *) TARGET="$1"; shift ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  if [[ ! -s "$HISTORY" ]]; then
    echo "akki-rollback: no $HISTORY — supply a tag explicitly" >&2
    exit 1
  fi
  # tail the (steps+1)th-from-bottom entry: rolling back ONE step = the
  # entry just above the current head.
  TARGET=$(tail -n $((STEPS + 1)) "$HISTORY" | head -1 || true)
  if [[ -z "$TARGET" ]]; then
    echo "akki-rollback: history shorter than $STEPS step(s)" >&2
    exit 1
  fi
fi

echo "akki-rollback: pinning IMAGE_TAG=${TARGET}"
exec /usr/local/bin/akki-deploy.sh "$TARGET"
