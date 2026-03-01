#!/usr/bin/env bash
# =============================================================================
# 06 — Entwicklungstools
# Node.js (nvm), Python venv, Git, Claude Code, jtop
# =============================================================================
set -euo pipefail

NVM_DIR="${REAL_HOME}/.nvm"

log()  { echo -e "\033[0;32m[✓]\033[0m $*"; }
warn() { echo -e "\033[1;33m[!]\033[0m $*"; }
skip() { echo -e "\033[1;33m[→]\033[0m $* (bereits erledigt)"; }

run_as_user() {
    sudo -u "$REAL_USER" -H bash -c "$*"
}

# ---------------------------------------------------------------------------
# Build-Essentials (für native npm/pip-Pakete)
# ---------------------------------------------------------------------------
log "Installiere Build-Tools..."
apt-get install -y -qq \
    build-essential \
    python3-dev \
    python3-venv \
    python3-pip \
    libffi-dev \
    libssl-dev \
    pkg-config \
    2>/dev/null

# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------
if ! command -v git &>/dev/null; then
    apt-get install -y -qq git
fi

if [[ -n "${GIT_USER_NAME:-}" ]] && [[ "$GIT_USER_NAME" != "CHANGEME" ]]; then
    run_as_user "git config --global user.name '${GIT_USER_NAME}'"
    run_as_user "git config --global user.email '${GIT_USER_EMAIL}'"
    log "Git konfiguriert: ${GIT_USER_NAME} <${GIT_USER_EMAIL}>"
else
    warn "Git user.name nicht gesetzt — manuell konfigurieren:"
    warn "  git config --global user.name 'Dein Name'"
    warn "  git config --global user.email 'du@firma.de'"
fi

run_as_user "git config --global init.defaultBranch main"
run_as_user "git config --global pull.rebase true"
run_as_user "git config --global core.editor nano"

# GitHub SSH-Key generieren
GH_KEY="${REAL_HOME}/.ssh/github_ed25519"
if [[ ! -f "$GH_KEY" ]]; then
    run_as_user "mkdir -p ${REAL_HOME}/.ssh && chmod 700 ${REAL_HOME}/.ssh"
    run_as_user "ssh-keygen -t ed25519 -C '${JETSON_HOSTNAME}-${CUSTOMER_NAME}' -f ${GH_KEY} -N ''"
    log "GitHub SSH-Key generiert: ${GH_KEY}"
    echo ""
    echo "  ┌──────────────────────────────────────────────────┐"
    echo "  │ Diesen Key zu GitHub → Settings → SSH Keys:      │"
    echo "  └──────────────────────────────────────────────────┘"
    cat "${GH_KEY}.pub"
    echo ""
else
    skip "GitHub SSH-Key existiert bereits"
fi

SSH_CONFIG="${REAL_HOME}/.ssh/config"
if ! grep -q "github.com" "$SSH_CONFIG" 2>/dev/null; then
    cat >> "$SSH_CONFIG" << EOF

Host github.com
    HostName github.com
    User git
    IdentityFile ${GH_KEY}
    IdentitiesOnly yes
EOF
    chown "${REAL_USER}:${REAL_USER}" "$SSH_CONFIG"
    chmod 600 "$SSH_CONFIG"
    log "SSH für GitHub konfiguriert"
fi

# ---------------------------------------------------------------------------
# Node.js via nvm
# ---------------------------------------------------------------------------
if [[ ! -d "$NVM_DIR" ]]; then
    log "Installiere nvm + Node.js ${NODE_VERSION} LTS..."
    run_as_user "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash"
    run_as_user "export NVM_DIR='${NVM_DIR}' && source '${NVM_DIR}/nvm.sh' && nvm install ${NODE_VERSION} && nvm alias default ${NODE_VERSION}"
    log "Node.js installiert via nvm"
else
    skip "nvm bereits installiert"
fi

NODE_VER=$(run_as_user "export NVM_DIR='${NVM_DIR}' && source '${NVM_DIR}/nvm.sh' && node --version" 2>/dev/null || echo "nicht gefunden")
log "Node.js Version: ${NODE_VER}"

# ---------------------------------------------------------------------------
# Python Virtual Environment
# ---------------------------------------------------------------------------
VENV_DIR="${REAL_HOME}/venvs/default"
if [[ ! -d "$VENV_DIR" ]]; then
    run_as_user "python3 -m venv '${VENV_DIR}' --system-site-packages"
    log "Python venv erstellt: ${VENV_DIR}"
else
    skip "Python venv existiert bereits"
fi

# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------
if [[ "${INSTALL_CLAUDE}" == "true" ]]; then
    if run_as_user "export NVM_DIR='${NVM_DIR}' && source '${NVM_DIR}/nvm.sh' && command -v claude" &>/dev/null 2>&1; then
        skip "Claude Code bereits installiert"
    else
        log "Installiere Claude Code..."
        if run_as_user "export NVM_DIR='${NVM_DIR}' && source '${NVM_DIR}/nvm.sh' && npm install -g @anthropic-ai/claude-code" 2>/dev/null; then
            log "Claude Code installiert via npm"
        else
            warn "npm-Installation fehlgeschlagen — versuche nativen Installer..."
            run_as_user "curl -fsSL https://claude.ai/install.sh | bash" 2>/dev/null || {
                warn "Claude Code konnte nicht installiert werden"
                warn "Manuell versuchen: npm install -g @anthropic-ai/claude-code"
            }
        fi
    fi
else
    log "Claude Code übersprungen (INSTALL_CLAUDE=false)"
fi

# ---------------------------------------------------------------------------
# Ollama (optional — lokale LLM-Inference)
# ---------------------------------------------------------------------------
if [[ "${INSTALL_OLLAMA}" == "true" ]]; then
    if ! command -v ollama &>/dev/null; then
        log "Installiere Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
        # Modell-Verzeichnis auf NVMe
        if [[ -d "${NVME_MOUNT}/models" ]]; then
            mkdir -p /etc/systemd/system/ollama.service.d
            cat > /etc/systemd/system/ollama.service.d/override.conf << EOF
[Service]
Environment="OLLAMA_MODELS=${NVME_MOUNT}/models/ollama"
EOF
            systemctl daemon-reload
            systemctl restart ollama
        fi
        log "Ollama installiert (Modelle: ${NVME_MOUNT}/models/ollama)"
    else
        skip "Ollama bereits installiert"
    fi
else
    log "Ollama übersprungen (INSTALL_OLLAMA=false)"
fi

# ---------------------------------------------------------------------------
# jtop (Jetson-Systemmonitor)
# ---------------------------------------------------------------------------
if ! command -v jtop &>/dev/null; then
    pip3 install --break-system-packages -U jetson-stats 2>/dev/null || \
        pip3 install -U jetson-stats 2>/dev/null || true
    log "jtop installiert"
else
    skip "jtop bereits installiert"
fi

log "Entwicklungstools-Setup abgeschlossen"
