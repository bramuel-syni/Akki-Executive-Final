#!/usr/bin/env bash
# AKKI VM bootstrap — run ONCE per VM after first provision.
#
# Idempotent: rerun-safe. Does not destroy data, certs or env files.
#
# What it does:
#   1. Installs Docker Engine + compose v2 plugin
#   2. Installs Azure CLI
#   3. Logs the VM in via its system-assigned managed identity
#   4. Creates /etc/akki, /var/lib/akki/{minio,clamav}, /var/log/akki
#   5. Drops the deploy helper scripts under /usr/local/bin
#   6. Installs a systemd unit `akki.service` that:
#        - on boot: runs the secret loader, then `docker compose up -d`
#        - on stop: `docker compose down`
#
# Usage:
#   sudo KEY_VAULT_NAME=akki-prod-kv \
#        ACR_LOGIN_SERVER=akkiprod.azurecr.io \
#        REPO_DIR=/opt/akki \
#        ./bootstrap-vm.sh
#
# Required env:
#   KEY_VAULT_NAME    Azure Key Vault holding all akki.env secrets
#   ACR_LOGIN_SERVER  e.g. akkiprod.azurecr.io  (used for `az acr login`)
#
# Optional env:
#   REPO_DIR          where docker-compose.prod.yml lives (default /opt/akki)

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "bootstrap-vm: must run as root (sudo)" >&2
  exit 1
fi

KEY_VAULT_NAME="${KEY_VAULT_NAME:?KEY_VAULT_NAME is required}"
ACR_LOGIN_SERVER="${ACR_LOGIN_SERVER:?ACR_LOGIN_SERVER is required}"
REPO_DIR="${REPO_DIR:-/opt/akki}"

log() { printf '\033[1;34m[bootstrap]\033[0m %s\n' "$*"; }

# ---------------------------------------------------------------------------
# 1. Docker + compose plugin
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker Engine + compose plugin"
  apt-get update
  apt-get install -y ca-certificates curl gnupg lsb-release
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release; echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  log "Docker already installed: $(docker --version)"
fi

# ---------------------------------------------------------------------------
# 2. Azure CLI
# ---------------------------------------------------------------------------
if ! command -v az >/dev/null 2>&1; then
  log "Installing Azure CLI"
  curl -sL https://aka.ms/InstallAzureCLIDeb | bash
else
  log "Azure CLI already installed: $(az --version | head -1)"
fi

# ---------------------------------------------------------------------------
# 3. Login as the VM managed identity
# ---------------------------------------------------------------------------
log "Logging in via VM managed identity"
az login --identity --output none
# ACR login uses the same identity (assumes AcrPull role on the registry).
log "Logging Docker into ACR via managed identity"
ACR_NAME_SHORT="${ACR_LOGIN_SERVER%%.*}"
az acr login --name "${ACR_NAME_SHORT}" --output none

# ---------------------------------------------------------------------------
# 4. Filesystem layout
# ---------------------------------------------------------------------------
log "Creating /etc/akki, /var/lib/akki/{minio,clamav}, /var/log/akki"
install -d -m 0700 -o root -g root /etc/akki
install -d -m 0755 -o root -g root /var/lib/akki
install -d -m 0755 -o root -g root /var/lib/akki/minio
install -d -m 0755 -o root -g root /var/lib/akki/clamav
install -d -m 0755 -o root -g root /var/log/akki
install -d -m 0755 -o root -g root "${REPO_DIR}"

if [[ ! -f /etc/akki/origin.crt || ! -f /etc/akki/origin.key ]]; then
  log "REMINDER: copy Cloudflare Origin Certificate + key to:"
  log "   /etc/akki/origin.crt   (mode 0644 root:root)"
  log "   /etc/akki/origin.key   (mode 0600 root:root)"
fi

# ---------------------------------------------------------------------------
# 5. Helper scripts
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
log "Installing helper scripts to /usr/local/bin"
install -m 0755 "${SCRIPT_DIR}/akki-load-secrets.sh" /usr/local/bin/akki-load-secrets.sh
install -m 0755 "${SCRIPT_DIR}/akki-deploy.sh"       /usr/local/bin/akki-deploy.sh
install -m 0755 "${SCRIPT_DIR}/akki-rollback.sh"     /usr/local/bin/akki-rollback.sh

# Persist the Key Vault name for the helpers.
cat > /etc/akki/bootstrap.env <<EOF
KEY_VAULT_NAME=${KEY_VAULT_NAME}
ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER}
REPO_DIR=${REPO_DIR}
EOF
chmod 0600 /etc/akki/bootstrap.env

# ---------------------------------------------------------------------------
# 6. systemd unit
# ---------------------------------------------------------------------------
log "Installing /etc/systemd/system/akki.service"
cat > /etc/systemd/system/akki.service <<EOF
[Unit]
Description=AKKI production stack (docker compose)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
EnvironmentFile=/etc/akki/bootstrap.env
ExecStartPre=/usr/local/bin/akki-load-secrets.sh
ExecStart=/usr/bin/docker compose -f \${REPO_DIR}/docker-compose.prod.yml --env-file /etc/akki/akki.env --env-file /etc/akki/image_tag.env up -d
ExecStop=/usr/bin/docker compose -f \${REPO_DIR}/docker-compose.prod.yml down
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable akki.service

log "Bootstrap complete."
log "Next steps:"
log "  1. Copy docker-compose.prod.yml to ${REPO_DIR}/"
log "  2. Place Cloudflare origin cert + key in /etc/akki/"
log "  3. Populate Azure Key Vault '${KEY_VAULT_NAME}' with all secrets (see DEPLOYMENT.md §7)"
log "  4. First deploy: trigger the GitHub Actions workflow OR run"
log "     'sudo /usr/local/bin/akki-deploy.sh <git_sha7>' from this VM."
