#!/usr/bin/env bash
# =============================================================================
# 04 — NVMe SSD Setup
# Partition, format, mount, swap, directory structure, I/O scheduler,
# weekly TRIM, health monitoring, Docker cleanup cron
# =============================================================================
set -euo pipefail

NVME_PART="${NVME_DEVICE}p1"
SWAP_FILE="${NVME_MOUNT}/swapfile"

# shellcheck source=../lib/common.sh
source "$(dirname "$0")/../lib/common.sh"

# ---------------------------------------------------------------------------
# Check NVMe device
# ---------------------------------------------------------------------------
if ! lsblk "$NVME_DEVICE" &>/dev/null 2>&1; then
    err "NVMe device not found: ${NVME_DEVICE}"
    err "Install M.2 2280 PCIe NVMe SSD and try again"
    exit 1
fi

NVME_SIZE=$(lsblk -b -d -n -o SIZE "$NVME_DEVICE" | head -1)
NVME_SIZE_GB=$(( NVME_SIZE / 1073741824 ))
log "NVMe detected: ${NVME_SIZE_GB} GB at ${NVME_DEVICE}"

# ---------------------------------------------------------------------------
# Partition and format
# ---------------------------------------------------------------------------
if ! lsblk -f "$NVME_PART" &>/dev/null 2>&1; then
    warn "Partitioning ${NVME_DEVICE} — ALL DATA WILL BE ERASED"
    echo "Waiting 5 seconds — Ctrl+C to abort..."
    sleep 5

    parted -s "$NVME_DEVICE" mklabel gpt
    parted -s "$NVME_DEVICE" mkpart primary ext4 0% 100%

    sleep 2
    partprobe "$NVME_DEVICE"
    sleep 1

    mkfs.ext4 -L "jetson-nvme" "$NVME_PART"
    log "NVMe partitioned and formatted as ext4"
else
    FS_TYPE=$(lsblk -f -n -o FSTYPE "$NVME_PART" | head -1)
    if [[ "$FS_TYPE" == "ext4" ]]; then
        skip "NVMe already partitioned (ext4)"
    else
        warn "NVMe partition exists but filesystem is: ${FS_TYPE}"
        warn "Manual formatting required if desired"
    fi
fi

# ---------------------------------------------------------------------------
# Mount NVMe
# ---------------------------------------------------------------------------
mkdir -p "$NVME_MOUNT"

if ! mountpoint -q "$NVME_MOUNT"; then
    mount "$NVME_PART" "$NVME_MOUNT"
    log "NVMe mounted: ${NVME_MOUNT}"
else
    skip "NVMe already mounted"
fi

# fstab entry (UUID-based for stability)
NVME_UUID=$(blkid -s UUID -o value "$NVME_PART")
if ! grep -q "$NVME_UUID" /etc/fstab 2>/dev/null; then
    # Remove old device-path-based entries
    sed -i "\|${NVME_PART}|d" /etc/fstab 2>/dev/null || true
    echo "UUID=${NVME_UUID}    ${NVME_MOUNT}    ext4    defaults,noatime    0    2" >> /etc/fstab
    log "fstab updated (UUID-based for stability)"
fi

chown "${REAL_USER}:${REAL_USER}" "$NVME_MOUNT"

# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------
DIRS=(
    "${NVME_MOUNT}/projects"
    "${NVME_MOUNT}/docker"
    "${NVME_MOUNT}/models"
    "${NVME_MOUNT}/data"
    "${NVME_MOUNT}/backups"
    "${NVME_MOUNT}/tmp"
)

for dir in "${DIRS[@]}"; do
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        chown "${REAL_USER}:${REAL_USER}" "$dir"
        log "Created: $dir"
    fi
done

# ---------------------------------------------------------------------------
# Swap file on NVMe
# ---------------------------------------------------------------------------
# shellcheck disable=SC2153
if [[ ! -f "$SWAP_FILE" ]]; then
    log "Creating ${SWAP_SIZE} swap on NVMe..."

    # Disable zram swap
    systemctl disable nvzramconfig 2>/dev/null || true
    swapoff -a 2>/dev/null || true

    fallocate -l "$SWAP_SIZE" "$SWAP_FILE"
    chmod 600 "$SWAP_FILE"
    mkswap "$SWAP_FILE"
    swapon "$SWAP_FILE"

    if ! grep -q "$SWAP_FILE" /etc/fstab; then
        echo "${SWAP_FILE}    none    swap    sw    0    0" >> /etc/fstab
    fi

    log "Swap created and activated: ${SWAP_SIZE}"
else
    if swapon --show | grep -q "$SWAP_FILE"; then
        skip "Swap already active"
    else
        swapon "$SWAP_FILE"
        log "Swap reactivated"
    fi
fi

# ---------------------------------------------------------------------------
# NVMe I/O scheduler (none is optimal for NVMe)
# ---------------------------------------------------------------------------
NVME_NAME=$(basename "$NVME_DEVICE")
echo none > "/sys/block/${NVME_NAME}/queue/scheduler" 2>/dev/null || true

# Persist via udev rule
UDEV_RULE="/etc/udev/rules.d/60-nvme-scheduler.rules"
if [[ ! -f "$UDEV_RULE" ]]; then
    cat > "$UDEV_RULE" << 'EOF'
ACTION=="add|change", KERNEL=="nvme*", ATTR{queue/scheduler}="none"
EOF
    log "NVMe I/O scheduler set to none"
else
    skip "NVMe I/O scheduler rule already set"
fi

# ---------------------------------------------------------------------------
# Weekly TRIM
# ---------------------------------------------------------------------------
systemctl enable --now fstrim.timer 2>/dev/null || true
log "Weekly TRIM enabled (fstrim.timer)"

# ---------------------------------------------------------------------------
# NVMe health monitoring cron
# ---------------------------------------------------------------------------
HEALTH_CRON="/etc/cron.weekly/nvme-health"
if [[ ! -f "$HEALTH_CRON" ]]; then
    cat > "$HEALTH_CRON" << EOF
#!/bin/bash
smartctl -a "${NVME_DEVICE}" >> /var/log/jetson-setup/nvme-health.log 2>&1
EOF
    chmod +x "$HEALTH_CRON"
    log "Weekly NVMe health check cron installed"
else
    skip "NVMe health cron already exists"
fi

# ---------------------------------------------------------------------------
# Docker cleanup cron
# ---------------------------------------------------------------------------
DOCKER_CRON="/etc/cron.weekly/docker-cleanup"
if [[ ! -f "$DOCKER_CRON" ]]; then
    cat > "$DOCKER_CRON" << 'EOF'
#!/bin/bash
docker system prune -f 2>/dev/null || true
EOF
    chmod +x "$DOCKER_CRON"
    log "Weekly Docker cleanup cron installed"
else
    skip "Docker cleanup cron already exists"
fi

# ---------------------------------------------------------------------------
# Symlink ~/projects
# ---------------------------------------------------------------------------
LINK="${REAL_HOME}/projects"
if [[ ! -L "$LINK" ]]; then
    ln -sf "${NVME_MOUNT}/projects" "$LINK"
    chown -h "${REAL_USER}:${REAL_USER}" "$LINK"
    log "Symlink: ~/projects → ${NVME_MOUNT}/projects"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
NVME_FREE=$(df -h "$NVME_MOUNT" | awk 'NR==2{print $4}')
SWAP_TOTAL=$(free -h | awk '/^Swap:/{print $2}')

log "NVMe setup complete"
log "  Mount:    ${NVME_MOUNT}"
log "  Free:     ${NVME_FREE}"
log "  Swap:     ${SWAP_TOTAL}"
log "  Projects: ~/projects → ${NVME_MOUNT}/projects"
