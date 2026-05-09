#!/usr/bin/env bash
# AKKI deploy helper — invoked by GitHub Actions over SSH.
#
# Usage:
#   sudo akki-deploy.sh <image_tag>
#
# Behaviour:
#   1. Refresh secrets from Key Vault (so rotations land within one deploy).
#   2. Write IMAGE_TAG into /etc/akki/image_tag.env (compose env-file).
#   3. `docker compose pull` for backend+frontend.
#   4. `docker compose up -d --no-deps backend frontend`.
#   5. Poll https://akki.syni.ai/api/health for up to 60s.
#   6. On success → record tag in /var/lib/akki/last-good-history.
#   7. On failure → roll back to the previous good tag, redeploy, exit 1.
#
# Logs to /var/log/akki/deploy.log AND stderr (so the GitHub Action sees them).

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "akki-deploy: must run as root (sudo)" >&2
  exit 1
fi

NEW_TAG="${1:?Usage: akki-deploy.sh <image_tag>}"

# shellcheck disable=SC1091
source /etc/akki/bootstrap.env
REPO_DIR="${REPO_DIR:-/opt/akki}"
COMPOSE_FILE="${REPO_DIR}/docker-compose.prod.yml"
IMAGE_TAG_ENV="/etc/akki/image_tag.env"
HISTORY="/var/lib/akki/last-good-history"
LAST_GOOD="/var/lib/akki/last-good-tag"
HEALTH_URL="${HEALTH_URL:-https://akki.syni.ai/api/health}"
LOG_DIR="/var/log/akki"
LOG_FILE="${LOG_DIR}/deploy.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

ts() { date -u +%FT%TZ; }
log() { printf '\033[1;32m[deploy %s]\033[0m %s\n' "$(ts)" "$*"; }

log "Starting deploy → tag=${NEW_TAG}"

# 1. Refresh secrets ---------------------------------------------------------
log "Refreshing secrets from Key Vault"
/usr/local/bin/akki-load-secrets.sh

write_image_tag_env() {
  local tag="$1"
  printf 'IMAGE_TAG=%s\n' "$tag"  >  "${IMAGE_TAG_ENV}.tmp"
  printf 'ACR_NAME=%s\n' "${ACR_LOGIN_SERVER}" >> "${IMAGE_TAG_ENV}.tmp"
  chmod 0644 "${IMAGE_TAG_ENV}.tmp"
  mv "${IMAGE_TAG_ENV}.tmp" "${IMAGE_TAG_ENV}"
}

compose() {
  docker compose -f "$COMPOSE_FILE" \
    --env-file /etc/akki/akki.env \
    --env-file "${IMAGE_TAG_ENV}" \
    "$@"
}

poll_health() {
  local deadline=$(( $(date +%s) + 60 ))
  while (( $(date +%s) < deadline )); do
    if curl -fsS --max-time 4 "${HEALTH_URL}" >/dev/null 2>&1; then
      log "Healthcheck OK at ${HEALTH_URL}"
      return 0
    fi
    sleep 3
  done
  log "Healthcheck FAILED after 60s polling ${HEALTH_URL}"
  return 1
}

rollback() {
  if [[ ! -s "$LAST_GOOD" ]]; then
    log "NO last-good-tag recorded — cannot auto-rollback. Manual intervention required."
    return 1
  fi
  local prev_tag ; prev_tag=$(< "$LAST_GOOD")
  log "Rolling back to previous good tag=${prev_tag}"
  write_image_tag_env "$prev_tag"
  compose pull backend frontend || true
  compose up -d --no-deps backend frontend
  if poll_health; then
    log "Rollback healthy — service restored on ${prev_tag}"
    return 0
  fi
  log "ROLLBACK ALSO FAILED — manual recovery required"
  return 1
}

# 2-4. Pull-and-up the new tag ----------------------------------------------
log "Writing image_tag.env"
write_image_tag_env "$NEW_TAG"

log "docker compose pull (backend, frontend)"
compose pull backend frontend

log "docker compose up -d --no-deps backend frontend"
compose up -d --no-deps backend frontend

# 5-7. Healthcheck + rollback ------------------------------------------------
if poll_health; then
  log "Deploy SUCCESS tag=${NEW_TAG}"
  printf '%s\n' "$NEW_TAG" >> "$HISTORY"
  printf '%s\n' "$NEW_TAG" >  "$LAST_GOOD"
  exit 0
fi

log "Deploy FAILED healthcheck — initiating rollback"
if rollback; then
  exit 1   # rolled back, but the new tag failed → CI must fail
fi
exit 2     # rollback also failed — page someone
