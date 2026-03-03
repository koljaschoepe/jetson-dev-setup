#!/usr/bin/env bash
# =============================================================================
# 03 — SSH-Härtung
# Key-Only Auth, Root-Login deaktivieren, fail2ban
# WICHTIG: SSH-Key muss vorher kopiert sein!
# =============================================================================
set -euo pipefail

log()  { echo -e "\033[0;32m[✓]\033[0m $*"; }
warn() { echo -e "\033[1;33m[!]\033[0m $*"; }
err()  { echo -e "\033[0;31m[✗]\033[0m $*"; }
skip() { echo -e "\033[1;33m[→]\033[0m $* (bereits erledigt)"; }

# ---------------------------------------------------------------------------
# Sicherheitsprüfung: SSH-Keys vorhanden?
# ---------------------------------------------------------------------------
AUTH_KEYS="${REAL_HOME}/.ssh/authorized_keys"
if [[ ! -f "$AUTH_KEYS" ]] || [[ ! -s "$AUTH_KEYS" ]]; then
    err "Keine SSH authorized_keys für ${REAL_USER} gefunden!"
    err ""
    err "Zuerst SSH-Key kopieren:"
    err "  ssh-copy-id -i ~/.ssh/id_ed25519.pub ${REAL_USER}@${JETSON_HOSTNAME}.local"
    err ""
    err "SSH-Härtung übersprungen um Aussperrung zu verhindern"
    exit 2
fi

KEY_COUNT=$(wc -l < "$AUTH_KEYS")
log "${KEY_COUNT} SSH-Key(s) in authorized_keys gefunden"

# ---------------------------------------------------------------------------
# SSH-Daemon härten
# ---------------------------------------------------------------------------
SSHD_DROPIN="/etc/ssh/sshd_config.d/99-jetson-hardened.conf"

if [[ ! -f "$SSHD_DROPIN" ]]; then
    cat > "$SSHD_DROPIN" << 'EOF'
# Jetson Dev Server — SSH Hardening
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
X11Forwarding no
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 3
AllowAgentForwarding yes
AllowTcpForwarding yes
PrintLastLog no
EOF

    if sshd -t 2>/dev/null; then
        systemctl restart sshd
        log "SSH gehärtet: Passwort-Auth deaktiviert, Root-Login deaktiviert"
    else
        err "SSH-Konfiguration ungültig — wird zurückgesetzt"
        rm -f "$SSHD_DROPIN"
        exit 1
    fi
else
    skip "SSH bereits gehärtet"
fi

# ---------------------------------------------------------------------------
# fail2ban
# ---------------------------------------------------------------------------
if ! dpkg -l fail2ban 2>/dev/null | grep -q "^ii"; then
    apt-get install -y -qq fail2ban

    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 3

[sshd]
enabled  = true
port     = ssh
logpath  = %(sshd_log)s
backend  = systemd
maxretry = 3
EOF

    systemctl enable --now fail2ban
    log "fail2ban installiert (3 Versuche → 1h Sperre)"
else
    skip "fail2ban bereits installiert"
fi

log "SSH-Härtung abgeschlossen"
warn "SSH-Key-Login von deinem Mac testen bevor du diese Session schließt!"
