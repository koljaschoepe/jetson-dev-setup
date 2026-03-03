#!/usr/bin/env bash
# =============================================================================
# 07 — Quality of Life
# tmux, shell aliases, power mode, MOTD, bash prompt
# =============================================================================
set -euo pipefail

# shellcheck source=../lib/common.sh
source "$(dirname "$0")/../lib/common.sh"

# ---------------------------------------------------------------------------
# tmux
# ---------------------------------------------------------------------------
if ! command -v tmux &>/dev/null; then
    apt-get install -y -qq tmux
    log "tmux installed"
else
    skip "tmux already installed"
fi

TMUX_CONF="${REAL_HOME}/.tmux.conf"
if [[ -f "${SCRIPT_DIR}/config/tmux.conf" ]]; then
    cp "${SCRIPT_DIR}/config/tmux.conf" "$TMUX_CONF"
    chown "${REAL_USER}:${REAL_USER}" "$TMUX_CONF"
    log "tmux configuration installed"
fi

# tmux Plugin Manager
TPM_DIR="${REAL_HOME}/.tmux/plugins/tpm"
if [[ ! -d "$TPM_DIR" ]]; then
    run_as_user "git clone https://github.com/tmux-plugins/tpm '${TPM_DIR}'" 2>/dev/null || true
    log "tmux Plugin Manager installed (Ctrl-a I to install plugins)"
fi

# ---------------------------------------------------------------------------
# Shell aliases
# ---------------------------------------------------------------------------
ALIASES_FILE="${REAL_HOME}/.bash_aliases"
if [[ -f "${SCRIPT_DIR}/config/bash_aliases" ]]; then
    cp "${SCRIPT_DIR}/config/bash_aliases" "$ALIASES_FILE"
    chown "${REAL_USER}:${REAL_USER}" "$ALIASES_FILE"
    log "Shell aliases installed"
elif ! grep -q "jetson-dev" "$ALIASES_FILE" 2>/dev/null; then
    cat "${SCRIPT_DIR}/config/bash_aliases" >> "$ALIASES_FILE" 2>/dev/null || true
    chown "${REAL_USER}:${REAL_USER}" "$ALIASES_FILE"
    log "Shell aliases installed"
fi

# ---------------------------------------------------------------------------
# Bash prompt with Jetson context
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
    log "Custom bash prompt installed"
fi

# ---------------------------------------------------------------------------
# Power mode
# ---------------------------------------------------------------------------
if command -v nvpmodel &>/dev/null; then
    CURRENT_MODE=$(nvpmodel -q 2>/dev/null | grep "NV Power Mode" | awk -F: '{print $2}' | xargs || true)
    nvpmodel -m "${POWER_MODE}" 2>/dev/null || true
    log "Power mode set: ${POWER_MODE} (was: ${CURRENT_MODE:-unknown})"
fi

# ---------------------------------------------------------------------------
# Disable MOTD — Arasul Shell takes over on SSH login
# ---------------------------------------------------------------------------
chmod -x /etc/update-motd.d/* 2>/dev/null || true
log "MOTD disabled (Arasul Shell takes over)"

# Arasul Shell auto-start on SSH login
if ! grep -q "ARASUL_SHELL_ACTIVE" "$BASHRC" 2>/dev/null; then
    cat >> "$BASHRC" << 'AUTOSTART'

# Auto-start Arasul Shell on interactive SSH login
if [ -n "$SSH_CONNECTION" ] && [ -z "$ARASUL_SHELL_ACTIVE" ] && command -v arasul &>/dev/null; then
    export ARASUL_SHELL_ACTIVE=1
    exec arasul
fi
AUTOSTART
    chown "${REAL_USER}:${REAL_USER}" "$BASHRC"
    log "Arasul Shell auto-start configured"
fi

# ---------------------------------------------------------------------------
# Install Arasul TUI (optional)
# ---------------------------------------------------------------------------
if [[ "${INSTALL_ARASUL_TUI:-true}" == "true" ]]; then
    if [[ -d "${SCRIPT_DIR}/arasul_tui" ]] && [[ -f "${SCRIPT_DIR}/pyproject.toml" ]]; then
        run_as_user "bash '${SCRIPT_DIR}/arasul_tui/install.sh'" && log "Arasul TUI installed"
    else
        warn "Arasul TUI sources not found in repo — skipping installation"
    fi
else
    skip "Arasul TUI installation disabled"
fi

log "Quality of life setup complete"
