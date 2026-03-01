#!/usr/bin/env bash
# =============================================================================
# 01 — System-Optimierung
# Desktop-GUI deaktivieren, unnötige Services stoppen, Kernel tunen
# =============================================================================
set -euo pipefail

log()  { echo -e "\033[0;32m[✓]\033[0m $*"; }
warn() { echo -e "\033[1;33m[!]\033[0m $*"; }
skip() { echo -e "\033[1;33m[→]\033[0m $* (bereits erledigt)"; }

# ---------------------------------------------------------------------------
# Desktop-Umgebung deaktivieren
# ---------------------------------------------------------------------------
CURRENT_TARGET=$(systemctl get-default)
if [[ "$CURRENT_TARGET" == "graphical.target" ]]; then
    log "Wechsle zu multi-user.target (headless)..."
    systemctl set-default multi-user.target
    systemctl stop gdm3 2>/dev/null || true
    systemctl disable gdm3 2>/dev/null || true
    log "Desktop deaktiviert — ~800MB RAM gespart"
else
    skip "Bereits im Headless-Modus"
fi

# ---------------------------------------------------------------------------
# Unnötige Services deaktivieren
# ---------------------------------------------------------------------------
DISABLE_SERVICES=(
    "nvargus-daemon.service"
    "bluetooth.service"
    "cups.service"
    "cups-browsed.service"
    "ModemManager.service"
    "wpa_supplicant.service"
    "colord.service"
    "whoopsie.service"
    "apport.service"
    "unattended-upgrades.service"
)

for svc in "${DISABLE_SERVICES[@]}"; do
    if systemctl is-enabled "$svc" &>/dev/null 2>&1; then
        systemctl disable --now "$svc" 2>/dev/null || true
        log "Deaktiviert: $svc"
    fi
done

# ---------------------------------------------------------------------------
# Desktop-Pakete entfernen (~3GB Speicher)
# ---------------------------------------------------------------------------
if dpkg -l | grep -q ubuntu-desktop 2>/dev/null; then
    log "Entferne Desktop-Pakete (dauert einige Minuten)..."
    apt-get remove --purge -y \
        ubuntu-desktop \
        gdm3 \
        gnome-shell \
        gnome-terminal \
        nautilus \
        firefox \
        thunderbird \
        libreoffice* \
        2>/dev/null || true
    apt-get autoremove --purge -y 2>/dev/null || true
    apt-get clean

    # NetworkManager muss überleben
    apt-get install -y network-manager 2>/dev/null || true
    log "Desktop-Pakete entfernt — ~3GB Speicher frei"
else
    skip "Desktop-Pakete bereits entfernt"
fi

# ---------------------------------------------------------------------------
# System-Updates und Basispakete
# ---------------------------------------------------------------------------
log "Aktualisiere Paketlisten..."
apt-get update -qq

log "Installiere Basispakete..."
apt-get install -y -qq \
    curl \
    wget \
    htop \
    tree \
    jq \
    unzip \
    net-tools \
    nvme-cli \
    smartmontools \
    lsof \
    ca-certificates \
    gnupg \
    2>/dev/null

# ---------------------------------------------------------------------------
# Kernel-Parameter optimieren
# ---------------------------------------------------------------------------
SYSCTL_FILE="/etc/sysctl.d/99-jetson-dev.conf"
if [[ ! -f "$SYSCTL_FILE" ]]; then
    cat > "$SYSCTL_FILE" << 'EOF'
# Jetson Dev Server — Kernel Tuning
vm.swappiness=10
fs.inotify.max_user_watches=524288
fs.inotify.max_user_instances=512
net.core.somaxconn=65535
net.core.rmem_max=16777216
net.core.wmem_max=16777216
fs.file-max=2097152
EOF
    sysctl -p "$SYSCTL_FILE"
    log "Kernel-Parameter optimiert"
else
    skip "Kernel-Parameter bereits konfiguriert"
fi

# ---------------------------------------------------------------------------
# File-Descriptor-Limits erhöhen
# ---------------------------------------------------------------------------
LIMITS_FILE="/etc/security/limits.d/99-jetson-dev.conf"
if [[ ! -f "$LIMITS_FILE" ]]; then
    cat > "$LIMITS_FILE" << EOF
${REAL_USER}    soft    nofile    65536
${REAL_USER}    hard    nofile    131072
${REAL_USER}    soft    nproc     65536
${REAL_USER}    hard    nproc     65536
EOF
    log "File-Descriptor-Limits erhöht für ${REAL_USER}"
else
    skip "File-Descriptor-Limits bereits gesetzt"
fi

log "System-Optimierung abgeschlossen"
log "Freier RAM: $(free -h | awk '/^Mem:/{print $7}')"
