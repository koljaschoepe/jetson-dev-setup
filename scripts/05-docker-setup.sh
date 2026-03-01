#!/usr/bin/env bash
# =============================================================================
# 05 — Docker Setup
# Docker + NVIDIA Container Runtime, Daten auf NVMe, Compose V2
# =============================================================================
set -euo pipefail

log()  { echo -e "\033[0;32m[✓]\033[0m $*"; }
warn() { echo -e "\033[1;33m[!]\033[0m $*"; }
skip() { echo -e "\033[1;33m[→]\033[0m $* (bereits erledigt)"; }

# ---------------------------------------------------------------------------
# Docker installieren
# ---------------------------------------------------------------------------
if ! command -v docker &>/dev/null; then
    log "Installiere Docker..."
    apt-get install -y -qq docker.io nvidia-container-toolkit 2>/dev/null || {
        warn "Fallback: Docker manuell installieren..."
        curl -fsSL https://get.docker.com | sh
        apt-get install -y -qq nvidia-container-toolkit
    }
fi

DOCKER_VERSION=$(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',')
log "Docker Version: ${DOCKER_VERSION}"

if [[ "$DOCKER_VERSION" == 28.* ]]; then
    warn "Docker 28.x erkannt — bekannte Kernel-Probleme auf JetPack 6.x!"
    warn "Downgrade auf 27.5.x empfohlen"
fi

# ---------------------------------------------------------------------------
# Benutzer zur docker-Gruppe hinzufügen
# ---------------------------------------------------------------------------
if ! groups "$REAL_USER" | grep -q docker; then
    usermod -aG docker "$REAL_USER"
    log "${REAL_USER} zur docker-Gruppe hinzugefügt"
    warn "Ausloggen und wieder einloggen für Gruppenänderung"
else
    skip "${REAL_USER} bereits in docker-Gruppe"
fi

# ---------------------------------------------------------------------------
# Docker-Daemon konfigurieren
# ---------------------------------------------------------------------------
DAEMON_JSON="/etc/docker/daemon.json"

if [[ -d "$NVME_MOUNT" ]] && mountpoint -q "$NVME_MOUNT" 2>/dev/null; then
    DATA_ROOT="${NVME_MOUNT}/docker"
    mkdir -p "$DATA_ROOT"
else
    DATA_ROOT="/var/lib/docker"
    warn "NVMe nicht gemountet — Docker-Daten bleiben auf SD-Karte"
fi

cat > "$DAEMON_JSON" << EOF
{
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    },
    "default-runtime": "nvidia",
    "data-root": "${DATA_ROOT}",
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "${DOCKER_LOG_MAX_SIZE}",
        "max-file": "${DOCKER_LOG_MAX_FILES}"
    },
    "storage-driver": "overlay2",
    "live-restore": true,
    "default-address-pools": [
        {"base": "172.17.0.0/12", "size": 24}
    ]
}
EOF

log "Docker-Daemon konfiguriert (data-root: ${DATA_ROOT})"

# ---------------------------------------------------------------------------
# Docker-Version pinnen (kein Auto-Upgrade auf 28.x)
# ---------------------------------------------------------------------------
apt-mark hold docker-ce docker-ce-cli 2>/dev/null || \
    apt-mark hold docker.io 2>/dev/null || true
log "Docker-Version gepinnt gegen Auto-Upgrade"

# ---------------------------------------------------------------------------
# Docker Compose V2
# ---------------------------------------------------------------------------
if ! docker compose version &>/dev/null 2>&1; then
    apt-get install -y -qq docker-compose-plugin 2>/dev/null || {
        COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | jq -r '.tag_name')
        mkdir -p /usr/local/lib/docker/cli-plugins
        curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-aarch64" \
            -o /usr/local/lib/docker/cli-plugins/docker-compose
        chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    }
    log "Docker Compose V2 installiert"
else
    skip "Docker Compose V2 bereits vorhanden"
fi

# ---------------------------------------------------------------------------
# Docker neustarten
# ---------------------------------------------------------------------------
systemctl daemon-reload
systemctl enable docker
systemctl restart docker

if docker info 2>/dev/null | grep -q nvidia; then
    log "NVIDIA Container Runtime verifiziert"
else
    warn "NVIDIA Runtime nicht erkannt — GPU-Zugriff in Containern evtl. nicht möglich"
fi

COMPOSE_VER=$(docker compose version 2>/dev/null | awk '{print $NF}' || echo "n/a")
log "Docker-Setup abgeschlossen"
log "  Data Root: ${DATA_ROOT}"
log "  Runtime:   nvidia (default)"
log "  Compose:   ${COMPOSE_VER}"
