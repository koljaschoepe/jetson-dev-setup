#!/usr/bin/env bash
# =============================================================================
# 05 — Docker Setup (Multi-Platform)
# Docker, optional NVIDIA Container Runtime, Compose V2
# Data root on external storage if available.
# =============================================================================
set -euo pipefail

# shellcheck source=../lib/common.sh
source "$(dirname "$0")/../lib/common.sh"

# shellcheck source=../lib/detect.sh
source "$(dirname "$0")/../lib/detect.sh"

PLATFORM="${PLATFORM:-$(detect_platform)}"
STORAGE_MOUNT="${STORAGE_MOUNT:-$(detect_storage_mount)}"

# ---------------------------------------------------------------------------
# Install Docker
# ---------------------------------------------------------------------------
if ! command -v docker &>/dev/null; then
    log "Installing Docker..."
    if has_nvidia_gpu 2>/dev/null; then
        apt-get install -y -qq docker.io nvidia-container-toolkit 2>/dev/null || {
            warn "Fallback: installing Docker manually..."
            curl -fsSL https://get.docker.com | sh
            apt-get install -y -qq nvidia-container-toolkit 2>/dev/null || true
        }
    else
        apt-get install -y -qq docker.io 2>/dev/null || {
            warn "Fallback: installing Docker manually..."
            curl -fsSL https://get.docker.com | sh
        }
    fi
fi

DOCKER_VERSION=$(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',')
log "Docker version: ${DOCKER_VERSION}"

# Docker 28.x kernel issue is Jetson/JetPack specific
if [[ "$PLATFORM" == "jetson" ]] && [[ "$DOCKER_VERSION" == 28.* ]]; then
    warn "Docker 28.x detected — known kernel issues on JetPack 6.x!"
    warn "Downgrade to 27.5.x recommended"
fi

# ---------------------------------------------------------------------------
# Add user to docker group
# ---------------------------------------------------------------------------
if ! groups "$REAL_USER" | grep -q docker; then
    usermod -aG docker "$REAL_USER"
    log "${REAL_USER} added to docker group"
    warn "Log out and back in for group change to take effect"
else
    skip "${REAL_USER} already in docker group"
fi

# ---------------------------------------------------------------------------
# Configure Docker daemon
# ---------------------------------------------------------------------------
DAEMON_JSON="/etc/docker/daemon.json"

# Determine data root: prefer external storage
if [[ -d "$STORAGE_MOUNT" ]] && mountpoint -q "$STORAGE_MOUNT" 2>/dev/null; then
    DATA_ROOT="${STORAGE_MOUNT}/docker"
    mkdir -p "$DATA_ROOT"
else
    DATA_ROOT="/var/lib/docker"
    warn "External storage not mounted — Docker data stays on root filesystem"
fi

if [[ ! -f "$DAEMON_JSON" ]] || ! grep -q "data-root" "$DAEMON_JSON" 2>/dev/null; then
    if has_nvidia_gpu 2>/dev/null; then
        # NVIDIA runtime configuration
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
        log "Docker daemon configured with NVIDIA runtime (data-root: ${DATA_ROOT})"
    else
        # Standard configuration (no NVIDIA)
        cat > "$DAEMON_JSON" << EOF
{
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
        log "Docker daemon configured (data-root: ${DATA_ROOT})"
    fi
else
    skip "Docker daemon.json already configured"
fi

# ---------------------------------------------------------------------------
# Pin Docker version (prevent auto-upgrade to 28.x on Jetson)
# ---------------------------------------------------------------------------
if [[ "$PLATFORM" == "jetson" ]]; then
    apt-mark hold docker-ce docker-ce-cli 2>/dev/null || \
        apt-mark hold docker.io 2>/dev/null || true
    log "Docker version pinned against auto-upgrade (Jetson)"
fi

# ---------------------------------------------------------------------------
# Docker Compose V2
# ---------------------------------------------------------------------------
if ! docker compose version &>/dev/null 2>&1; then
    apt-get install -y -qq docker-compose-plugin 2>/dev/null || {
        COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | jq -r '.tag_name')
        COMPOSE_ARCH=$(uname -m)
        mkdir -p /usr/local/lib/docker/cli-plugins
        curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-${COMPOSE_ARCH}" \
            -o /usr/local/lib/docker/cli-plugins/docker-compose
        chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    }
    log "Docker Compose V2 installed"
else
    skip "Docker Compose V2 already present"
fi

# ---------------------------------------------------------------------------
# Restart Docker
# ---------------------------------------------------------------------------
systemctl daemon-reload
systemctl enable docker
systemctl restart docker

# Verify NVIDIA runtime (only if GPU present)
if has_nvidia_gpu 2>/dev/null; then
    if docker info 2>/dev/null | grep -q nvidia; then
        log "NVIDIA Container Runtime verified"
    else
        warn "NVIDIA Runtime not detected — GPU access in containers may not work"
    fi
fi

COMPOSE_VER=$(docker compose version 2>/dev/null | awk '{print $NF}' || echo "n/a")
log "Docker setup complete"
log "  Data Root: ${DATA_ROOT}"
if has_nvidia_gpu 2>/dev/null; then
    log "  Runtime:   nvidia (default)"
fi
log "  Compose:   ${COMPOSE_VER}"
