#!/usr/bin/env bash
# =============================================================================
# 03 — SSH Hardening
# Key-only auth, disable root login, fail2ban with recidive jail
# IMPORTANT: SSH key must be copied first!
# =============================================================================
set -euo pipefail

# shellcheck source=../lib/common.sh
source "$(dirname "$0")/../lib/common.sh"

# ---------------------------------------------------------------------------
# Safety check: SSH keys present?
# ---------------------------------------------------------------------------
AUTH_KEYS="${REAL_HOME}/.ssh/authorized_keys"
if [[ ! -f "$AUTH_KEYS" ]] || [[ ! -s "$AUTH_KEYS" ]]; then
    err "No SSH authorized_keys found for ${REAL_USER}!"
    err ""
    err "Copy your SSH key first:"
    err "  ssh-copy-id -i ~/.ssh/id_ed25519.pub ${REAL_USER}@${JETSON_HOSTNAME}.local"
    err ""
    err "SSH hardening skipped to prevent lockout"
    exit 2
fi

KEY_COUNT=$(wc -l < "$AUTH_KEYS")
log "${KEY_COUNT} SSH key(s) found in authorized_keys"

# ---------------------------------------------------------------------------
# Harden SSH daemon
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
        log "SSH hardened: password auth disabled, root login disabled"
    else
        err "SSH configuration invalid — reverting"
        rm -f "$SSHD_DROPIN"
        exit 1
    fi
else
    skip "SSH already hardened"
fi

# ---------------------------------------------------------------------------
# fail2ban with recidive jail
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

[recidive]
enabled  = true
logpath  = /var/log/fail2ban.log
banaction = %(banaction_allports)s
bantime  = 1w
findtime = 1d
maxretry = 5
EOF

    systemctl enable --now fail2ban
    log "fail2ban installed (3 attempts → 1h ban, repeat offenders → 1 week ban)"
else
    # Ensure recidive jail exists even if fail2ban was already installed
    if [[ -f /etc/fail2ban/jail.local ]] && ! grep -q "recidive" /etc/fail2ban/jail.local 2>/dev/null; then
        cat >> /etc/fail2ban/jail.local << 'EOF'

[recidive]
enabled  = true
logpath  = /var/log/fail2ban.log
banaction = %(banaction_allports)s
bantime  = 1w
findtime = 1d
maxretry = 5
EOF
        systemctl restart fail2ban
        log "Recidive jail added to fail2ban"
    else
        skip "fail2ban already installed"
    fi
fi

log "SSH hardening complete"
warn "Test SSH key login from your Mac before closing this session!"
