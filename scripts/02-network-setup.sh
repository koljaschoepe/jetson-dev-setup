#!/usr/bin/env bash
# =============================================================================
# 02 — Network Setup
# Hostname, mDNS (Bonjour), UFW firewall, optional Tailscale, optional static IP
# =============================================================================
set -euo pipefail

# shellcheck source=../lib/common.sh
source "$(dirname "$0")/../lib/common.sh"

# ---------------------------------------------------------------------------
# Set hostname
# ---------------------------------------------------------------------------
CURRENT_HOSTNAME=$(hostnamectl --static)
if [[ "$CURRENT_HOSTNAME" != "$JETSON_HOSTNAME" ]]; then
    hostnamectl set-hostname "$JETSON_HOSTNAME"
    sed -i "/127.0.1.1/d" /etc/hosts
    echo "127.0.1.1    ${JETSON_HOSTNAME}" >> /etc/hosts
    log "Hostname set: ${JETSON_HOSTNAME}"
else
    skip "Hostname already ${JETSON_HOSTNAME}"
fi

# ---------------------------------------------------------------------------
# mDNS (Avahi) — device reachable as <hostname>.local
# ---------------------------------------------------------------------------
if ! dpkg -l avahi-daemon 2>/dev/null | grep -q "^ii"; then
    apt-get install -y -qq avahi-daemon libnss-mdns
    log "Avahi (mDNS) installed"
fi

systemctl enable --now avahi-daemon 2>/dev/null || true
log "mDNS active — reachable as ${JETSON_HOSTNAME}.local"

# ---------------------------------------------------------------------------
# UFW Firewall
# ---------------------------------------------------------------------------
if ! command -v ufw &>/dev/null; then
    apt-get install -y -qq ufw
fi

if ! ufw status | grep -q "active"; then
    ufw default deny incoming
    ufw default allow outgoing
    ufw limit ssh comment 'SSH rate-limited'
    ufw allow 5353/udp comment 'mDNS'
    ufw --force enable
    log "UFW firewall enabled (SSH rate-limited + mDNS only)"
else
    skip "UFW already active"
fi

# ---------------------------------------------------------------------------
# Static IP (optional)
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
        log "Static IP configured: ${STATIC_IP}"
    else
        warn "No active Ethernet connection found for static IP"
    fi
fi

# ---------------------------------------------------------------------------
# Network info
# ---------------------------------------------------------------------------
ETH_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "not connected")
log "Ethernet IP: ${ETH_IP}"
log "mDNS: ${JETSON_HOSTNAME}.local"

# ---------------------------------------------------------------------------
# Tailscale (optional)
# ---------------------------------------------------------------------------
if [[ "${INSTALL_TAILSCALE}" == "true" ]]; then
    if ! command -v tailscale &>/dev/null; then
        log "Installing Tailscale..."
        curl -fsSL https://tailscale.com/install.sh | sh
        log "Tailscale installed"
        warn "Authentication required: sudo tailscale up"
        warn "Then disable key expiry in the Tailscale admin console"
    else
        skip "Tailscale already installed"
        if tailscale status &>/dev/null 2>&1; then
            TS_IP=$(tailscale ip -4 2>/dev/null || echo "not connected")
            log "Tailscale IP: ${TS_IP}"
        else
            warn "Tailscale installed but not connected: sudo tailscale up"
        fi
    fi
else
    log "Tailscale skipped (INSTALL_TAILSCALE=false)"
fi

log "Network setup complete"
