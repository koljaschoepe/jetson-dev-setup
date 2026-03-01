#!/usr/bin/env bash
# =============================================================================
# 02 — Netzwerk-Setup
# Hostname, mDNS (Bonjour), optional Tailscale, optional statische IP
# =============================================================================
set -euo pipefail

log()  { echo -e "\033[0;32m[✓]\033[0m $*"; }
warn() { echo -e "\033[1;33m[!]\033[0m $*"; }
skip() { echo -e "\033[1;33m[→]\033[0m $* (bereits erledigt)"; }

# ---------------------------------------------------------------------------
# Hostname setzen
# ---------------------------------------------------------------------------
CURRENT_HOSTNAME=$(hostnamectl --static)
if [[ "$CURRENT_HOSTNAME" != "$JETSON_HOSTNAME" ]]; then
    hostnamectl set-hostname "$JETSON_HOSTNAME"
    sed -i "/127.0.1.1/d" /etc/hosts
    echo "127.0.1.1    ${JETSON_HOSTNAME}" >> /etc/hosts
    log "Hostname gesetzt: ${JETSON_HOSTNAME}"
else
    skip "Hostname bereits ${JETSON_HOSTNAME}"
fi

# ---------------------------------------------------------------------------
# mDNS (Avahi) — Gerät erreichbar als <hostname>.local
# ---------------------------------------------------------------------------
if ! dpkg -l avahi-daemon 2>/dev/null | grep -q "^ii"; then
    apt-get install -y -qq avahi-daemon libnss-mdns
    log "Avahi (mDNS) installiert"
fi

systemctl enable --now avahi-daemon 2>/dev/null || true
log "mDNS aktiv — erreichbar als ${JETSON_HOSTNAME}.local"

# ---------------------------------------------------------------------------
# Statische IP (optional)
# ---------------------------------------------------------------------------
if [[ -n "${STATIC_IP:-}" ]]; then
    local_connection=$(nmcli -t -f NAME,TYPE connection show --active | grep ethernet | head -1 | cut -d: -f1)
    if [[ -n "$local_connection" ]]; then
        nmcli connection modify "$local_connection" \
            ipv4.method manual \
            ipv4.addresses "$STATIC_IP" \
            ipv4.gateway "${STATIC_GATEWAY:-}" \
            ipv4.dns "8.8.8.8,1.1.1.1"
        nmcli connection up "$local_connection"
        log "Statische IP konfiguriert: ${STATIC_IP}"
    else
        warn "Keine aktive Ethernet-Verbindung gefunden für statische IP"
    fi
fi

# ---------------------------------------------------------------------------
# Netzwerk-Info anzeigen
# ---------------------------------------------------------------------------
ETH_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "nicht verbunden")
log "Ethernet IP: ${ETH_IP}"
log "mDNS: ${JETSON_HOSTNAME}.local"

# ---------------------------------------------------------------------------
# Tailscale (optional)
# ---------------------------------------------------------------------------
if [[ "${INSTALL_TAILSCALE}" == "true" ]]; then
    if ! command -v tailscale &>/dev/null; then
        log "Installiere Tailscale..."
        curl -fsSL https://tailscale.com/install.sh | sh
        log "Tailscale installiert"
        warn "Authentifizierung nötig: sudo tailscale up"
        warn "Danach Key-Expiry in der Tailscale Admin Console deaktivieren"
    else
        skip "Tailscale bereits installiert"
        if tailscale status &>/dev/null 2>&1; then
            TS_IP=$(tailscale ip -4 2>/dev/null || echo "nicht verbunden")
            log "Tailscale IP: ${TS_IP}"
        else
            warn "Tailscale installiert aber nicht verbunden: sudo tailscale up"
        fi
    fi
else
    log "Tailscale übersprungen (INSTALL_TAILSCALE=false)"
fi

log "Netzwerk-Setup abgeschlossen"
