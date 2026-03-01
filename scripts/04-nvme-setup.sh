#!/usr/bin/env bash
# =============================================================================
# 04 — NVMe SSD Setup
# Partitionieren, Formatieren, Mounten, Swap, Verzeichnisstruktur
# =============================================================================
set -euo pipefail

NVME_PART="${NVME_DEVICE}p1"
SWAP_FILE="${NVME_MOUNT}/swapfile"

log()  { echo -e "\033[0;32m[✓]\033[0m $*"; }
warn() { echo -e "\033[1;33m[!]\033[0m $*"; }
err()  { echo -e "\033[0;31m[✗]\033[0m $*"; }
skip() { echo -e "\033[1;33m[→]\033[0m $* (bereits erledigt)"; }

# ---------------------------------------------------------------------------
# NVMe-Gerät prüfen
# ---------------------------------------------------------------------------
if ! lsblk "$NVME_DEVICE" &>/dev/null 2>&1; then
    err "NVMe-Gerät nicht gefunden: ${NVME_DEVICE}"
    err "M.2 2280 PCIe NVMe SSD einbauen und erneut versuchen"
    exit 1
fi

NVME_SIZE=$(lsblk -b -d -n -o SIZE "$NVME_DEVICE" | head -1)
NVME_SIZE_GB=$(( NVME_SIZE / 1073741824 ))
log "NVMe erkannt: ${NVME_SIZE_GB} GB an ${NVME_DEVICE}"

# ---------------------------------------------------------------------------
# Partitionieren und Formatieren
# ---------------------------------------------------------------------------
if ! lsblk -f "$NVME_PART" &>/dev/null 2>&1; then
    warn "Partitioniere ${NVME_DEVICE} — ALLE DATEN WERDEN GELÖSCHT"
    echo "5 Sekunden warten — Ctrl+C zum Abbrechen..."
    sleep 5

    parted -s "$NVME_DEVICE" mklabel gpt
    parted -s "$NVME_DEVICE" mkpart primary ext4 0% 100%

    sleep 2
    partprobe "$NVME_DEVICE"
    sleep 1

    mkfs.ext4 -L "jetson-nvme" "$NVME_PART"
    log "NVMe partitioniert und als ext4 formatiert"
else
    FS_TYPE=$(lsblk -f -n -o FSTYPE "$NVME_PART" | head -1)
    if [[ "$FS_TYPE" == "ext4" ]]; then
        skip "NVMe bereits partitioniert (ext4)"
    else
        warn "NVMe-Partition existiert aber Dateisystem ist: ${FS_TYPE}"
        warn "Manuelles Formatieren nötig falls gewünscht"
    fi
fi

# ---------------------------------------------------------------------------
# NVMe mounten
# ---------------------------------------------------------------------------
mkdir -p "$NVME_MOUNT"

if ! mountpoint -q "$NVME_MOUNT"; then
    mount "$NVME_PART" "$NVME_MOUNT"
    log "NVMe gemountet: ${NVME_MOUNT}"
else
    skip "NVMe bereits gemountet"
fi

# fstab-Eintrag (UUID-basiert für Stabilität)
NVME_UUID=$(blkid -s UUID -o value "$NVME_PART")
if ! grep -q "$NVME_UUID" /etc/fstab 2>/dev/null; then
    # Alte gerätepfad-basierte Einträge entfernen
    sed -i "\|${NVME_PART}|d" /etc/fstab 2>/dev/null || true
    echo "UUID=${NVME_UUID}    ${NVME_MOUNT}    ext4    defaults,noatime    0    2" >> /etc/fstab
    log "fstab aktualisiert (UUID-basiert für Stabilität)"
fi

chown "${REAL_USER}:${REAL_USER}" "$NVME_MOUNT"

# ---------------------------------------------------------------------------
# Verzeichnisstruktur
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
        log "Erstellt: $dir"
    fi
done

# ---------------------------------------------------------------------------
# Swap-Datei auf NVMe
# ---------------------------------------------------------------------------
if [[ ! -f "$SWAP_FILE" ]]; then
    log "Erstelle ${SWAP_SIZE} Swap auf NVMe..."

    # zram-Swap deaktivieren
    systemctl disable nvzramconfig 2>/dev/null || true
    swapoff -a 2>/dev/null || true

    fallocate -l "$SWAP_SIZE" "$SWAP_FILE"
    chmod 600 "$SWAP_FILE"
    mkswap "$SWAP_FILE"
    swapon "$SWAP_FILE"

    if ! grep -q "$SWAP_FILE" /etc/fstab; then
        echo "${SWAP_FILE}    none    swap    sw    0    0" >> /etc/fstab
    fi

    log "Swap erstellt und aktiviert: ${SWAP_SIZE}"
else
    if swapon --show | grep -q "$SWAP_FILE"; then
        skip "Swap bereits aktiv"
    else
        swapon "$SWAP_FILE"
        log "Swap reaktiviert"
    fi
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
# Zusammenfassung
# ---------------------------------------------------------------------------
NVME_FREE=$(df -h "$NVME_MOUNT" | awk 'NR==2{print $4}')
SWAP_TOTAL=$(free -h | awk '/^Swap:/{print $2}')

log "NVMe-Setup abgeschlossen"
log "  Mount:    ${NVME_MOUNT}"
log "  Frei:     ${NVME_FREE}"
log "  Swap:     ${SWAP_TOTAL}"
log "  Projekte: ~/projects → ${NVME_MOUNT}/projects"
