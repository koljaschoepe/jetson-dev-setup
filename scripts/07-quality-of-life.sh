#!/usr/bin/env bash
# =============================================================================
# 07 — Quality of Life
# tmux, Shell-Aliases, Power-Mode, MOTD, Bash-Prompt
# =============================================================================
set -euo pipefail

log()  { echo -e "\033[0;32m[✓]\033[0m $*"; }
warn() { echo -e "\033[1;33m[!]\033[0m $*"; }
skip() { echo -e "\033[1;33m[→]\033[0m $* (bereits erledigt)"; }

run_as_user() {
    sudo -u "$REAL_USER" -H bash -c "$*"
}

# ---------------------------------------------------------------------------
# tmux
# ---------------------------------------------------------------------------
if ! command -v tmux &>/dev/null; then
    apt-get install -y -qq tmux
    log "tmux installiert"
else
    skip "tmux bereits installiert"
fi

TMUX_CONF="${REAL_HOME}/.tmux.conf"
if [[ -f "${SCRIPT_DIR}/config/tmux.conf" ]]; then
    cp "${SCRIPT_DIR}/config/tmux.conf" "$TMUX_CONF"
    chown "${REAL_USER}:${REAL_USER}" "$TMUX_CONF"
    log "tmux-Konfiguration installiert"
fi

# tmux Plugin Manager
TPM_DIR="${REAL_HOME}/.tmux/plugins/tpm"
if [[ ! -d "$TPM_DIR" ]]; then
    run_as_user "git clone https://github.com/tmux-plugins/tpm '${TPM_DIR}'" 2>/dev/null || true
    log "tmux Plugin Manager installiert (Ctrl-a I für Plugins)"
fi

# ---------------------------------------------------------------------------
# Shell-Aliases
# ---------------------------------------------------------------------------
ALIASES_FILE="${REAL_HOME}/.bash_aliases"
if [[ -f "${SCRIPT_DIR}/config/bash_aliases" ]]; then
    cp "${SCRIPT_DIR}/config/bash_aliases" "$ALIASES_FILE"
    chown "${REAL_USER}:${REAL_USER}" "$ALIASES_FILE"
    log "Shell-Aliases installiert"
elif ! grep -q "jetson-dev" "$ALIASES_FILE" 2>/dev/null; then
    cat "${SCRIPT_DIR}/config/bash_aliases" >> "$ALIASES_FILE" 2>/dev/null || true
    chown "${REAL_USER}:${REAL_USER}" "$ALIASES_FILE"
    log "Shell-Aliases installiert"
fi

# ---------------------------------------------------------------------------
# Bash-Prompt mit Jetson-Kontext
# ---------------------------------------------------------------------------
BASHRC="${REAL_HOME}/.bashrc"
if ! grep -q "jetson-prompt" "$BASHRC" 2>/dev/null; then
    cat >> "$BASHRC" << 'PROMPT'

# jetson-prompt
__jetson_ps1() {
    local git_branch=$(git symbolic-ref --short HEAD 2>/dev/null)
    local ram_used=$(free -m | awk '/^Mem:/{printf "%.1fG", $3/1024}')

    if [[ -n "$git_branch" ]]; then
        echo -e "\[\033[32m\]\u@\h\[\033[0m\]:\[\033[34m\]\w\[\033[33m\] ($git_branch)\[\033[36m\] [${ram_used}]\[\033[0m\]\$ "
    else
        echo -e "\[\033[32m\]\u@\h\[\033[0m\]:\[\033[34m\]\w\[\033[36m\] [${ram_used}]\[\033[0m\]\$ "
    fi
}
PROMPT_COMMAND='PS1=$(__jetson_ps1)'
PROMPT
    chown "${REAL_USER}:${REAL_USER}" "$BASHRC"
    log "Custom Bash-Prompt installiert"
fi

# ---------------------------------------------------------------------------
# Power-Mode setzen
# ---------------------------------------------------------------------------
if command -v nvpmodel &>/dev/null; then
    CURRENT_MODE=$(nvpmodel -q 2>/dev/null | grep "NV Power Mode" | awk -F: '{print $2}' | xargs || true)
    nvpmodel -m "${POWER_MODE}" 2>/dev/null || true
    log "Power-Mode gesetzt: ${POWER_MODE} (vorher: ${CURRENT_MODE:-unbekannt})"
fi

# ---------------------------------------------------------------------------
# Welcome-Message (MOTD)
# ---------------------------------------------------------------------------
cat > /etc/update-motd.d/99-jetson-dev << MOTD
#!/bin/bash
echo ""
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║  Jetson Orin Nano Super — ${CUSTOMER_NAME}"
echo "  ╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Schnellbefehle:"
echo "    t           → tmux 'dev' Session"
echo "    claude      → Claude Code starten"
echo "    jtop        → Systemmonitor (GPU, RAM, Temp)"
echo "    p           → cd ~/projects"
echo "    powermode   → Power-Mode anzeigen"
echo ""
printf "  RAM: %s | " "\$(free -h | awk '/^Mem:/{print \$3"/"\$2}')"
printf "Disk: %s | " "\$(df -h ${NVME_MOUNT} 2>/dev/null | awk 'NR==2{print \$3"/"\$2}' || df -h / | awk 'NR==2{print \$3"/"\$2}')"
printf "Temp: %s°C\n" "\$(cat /sys/devices/virtual/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf "%.0f", \$1/1000}')"
echo ""
MOTD
chmod +x /etc/update-motd.d/99-jetson-dev

chmod -x /etc/update-motd.d/10-help-text 2>/dev/null || true
chmod -x /etc/update-motd.d/50-motd-news 2>/dev/null || true

log "Welcome-Message (MOTD) konfiguriert"
log "Quality-of-Life-Setup abgeschlossen"
