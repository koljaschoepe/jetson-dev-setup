#!/usr/bin/env bash
# =============================================================================
# 08 — Headless Browser Setup (Playwright + Chromium)
# =============================================================================
# Installiert Playwright mit Headless Chromium fuer AI Agent Browser-Automation.
# Wird im Arasul-TUI-venv installiert und auf NVMe gespeichert.
#
# Idempotent: Kann mehrfach ausgefuehrt werden, ueberspringt bereits erledigte Schritte.
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; }

REAL_USER="${REAL_USER:-$(logname 2>/dev/null || echo "${SUDO_USER:-$USER}")}"
REAL_HOME=$(eval echo "~${REAL_USER}")
NVME_MOUNT="${NVME_MOUNT:-/mnt/nvme}"
VENV_DIR="${REAL_HOME}/venvs/arasul-tui"
BROWSER_CACHE="${NVME_MOUNT}/playwright-browsers"

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
    err "Arasul TUI venv nicht gefunden: ${VENV_DIR}"
    err "Bitte zuerst arasul_tui/install.sh ausfuehren."
    exit 1
fi

VENV_PIP="${VENV_DIR}/bin/pip"
VENV_PYTHON="${VENV_DIR}/bin/python"

# ---------------------------------------------------------------------------
# 1. System-Dependencies fuer Chromium (headless)
# ---------------------------------------------------------------------------
install_system_deps() {
    log "Installiere System-Dependencies fuer headless Chromium..."
    apt-get update -qq
    apt-get install -y -qq \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libdbus-1-3 \
        libxkbcommon0 \
        libatspi2.0-0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        libwayland-client0 \
        > /dev/null 2>&1
    log "System-Dependencies installiert."
}

# ---------------------------------------------------------------------------
# 2. Playwright Python-Paket installieren
# ---------------------------------------------------------------------------
install_playwright_package() {
    if "${VENV_PYTHON}" -c "import playwright" 2>/dev/null; then
        local version
        version=$("${VENV_PYTHON}" -c "import playwright; print(playwright.__version__)" 2>/dev/null)
        log "Playwright Python bereits installiert (v${version})"
        return 0
    fi

    log "Installiere Playwright Python ins venv..."
    sudo -u "$REAL_USER" "${VENV_PIP}" install --quiet playwright
    local version
    version=$("${VENV_PYTHON}" -c "import playwright; print(playwright.__version__)" 2>/dev/null)
    log "Playwright v${version} installiert."
}

# ---------------------------------------------------------------------------
# 3. Browser-Cache auf NVMe einrichten
# ---------------------------------------------------------------------------
setup_browser_cache() {
    if [[ -d "$BROWSER_CACHE" ]]; then
        log "Browser-Cache existiert bereits: ${BROWSER_CACHE}"
        return 0
    fi

    log "Erstelle Browser-Cache auf NVMe: ${BROWSER_CACHE}"
    mkdir -p "$BROWSER_CACHE"
    chown "${REAL_USER}:${REAL_USER}" "$BROWSER_CACHE"

    local bashrc="${REAL_HOME}/.bashrc"
    if ! grep -q "PLAYWRIGHT_BROWSERS_PATH" "$bashrc" 2>/dev/null; then
        echo "" >> "$bashrc"
        echo "export PLAYWRIGHT_BROWSERS_PATH=\"${BROWSER_CACHE}\"" >> "$bashrc"
        log "PLAYWRIGHT_BROWSERS_PATH in .bashrc eingetragen."
    fi
}

# ---------------------------------------------------------------------------
# 4. Chromium herunterladen
# ---------------------------------------------------------------------------
install_chromium() {
    export PLAYWRIGHT_BROWSERS_PATH="$BROWSER_CACHE"

    local chromium_dir
    chromium_dir=$(find "$BROWSER_CACHE" -maxdepth 2 -name "chrome" -type f 2>/dev/null | head -1)
    if [[ -n "$chromium_dir" ]]; then
        log "Chromium bereits heruntergeladen in ${BROWSER_CACHE}"
        return 0
    fi

    log "Lade Chromium herunter (ARM64, ~180MB)..."
    sudo -u "$REAL_USER" \
        PLAYWRIGHT_BROWSERS_PATH="$BROWSER_CACHE" \
        "${VENV_PYTHON}" -m playwright install chromium
    log "Chromium heruntergeladen nach ${BROWSER_CACHE}"
}

# ---------------------------------------------------------------------------
# 5. MCP-Config fuer Claude Code einrichten
# ---------------------------------------------------------------------------
setup_mcp_config() {
    local claude_json="${REAL_HOME}/.claude.json"

    if "${VENV_PYTHON}" -c "
import json, sys
try:
    d = json.load(open('${claude_json}'))
    mcp = d.get('mcpServers', {})
    if 'playwright' in mcp:
        sys.exit(0)
    sys.exit(1)
except:
    sys.exit(1)
" 2>/dev/null; then
        log "Playwright MCP bereits in claude.json konfiguriert."
        return 0
    fi

    log "Konfiguriere Playwright MCP Server in claude.json..."
    "${VENV_PYTHON}" - "${claude_json}" "${BROWSER_CACHE}" <<'PYEOF'
import json, sys

claude_json_path = sys.argv[1]
browser_cache = sys.argv[2]

try:
    with open(claude_json_path) as f:
        data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    data = {}

if "mcpServers" not in data:
    data["mcpServers"] = {}

data["mcpServers"]["playwright"] = {
    "command": "npx",
    "args": ["-y", "@playwright/mcp@latest", "--headless"],
    "env": {
        "PLAYWRIGHT_BROWSERS_PATH": browser_cache
    }
}

with open(claude_json_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF

    chown "${REAL_USER}:${REAL_USER}" "$claude_json"
    log "Playwright MCP Server konfiguriert."
}

# ---------------------------------------------------------------------------
# 6. Verifikation
# ---------------------------------------------------------------------------
verify_installation() {
    export PLAYWRIGHT_BROWSERS_PATH="$BROWSER_CACHE"

    log "Verifiziere Installation..."
    if sudo -u "$REAL_USER" \
        PLAYWRIGHT_BROWSERS_PATH="$BROWSER_CACHE" \
        "${VENV_PYTHON}" -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('data:text/html,<h1>Arasul Browser OK</h1>')
    title = page.content()
    browser.close()
    assert 'Arasul Browser OK' in title
print('OK')
" 2>/dev/null; then
        log "Headless Chromium funktioniert einwandfrei."
    else
        err "Verifikation fehlgeschlagen. Manuell pruefen:"
        err "  PLAYWRIGHT_BROWSERS_PATH=${BROWSER_CACHE} ${VENV_PYTHON} -m playwright install chromium --with-deps"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  08 — Headless Browser Setup                  ║"
echo "║  Playwright + Chromium fuer AI Agents          ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

install_system_deps
install_playwright_package
setup_browser_cache
install_chromium
setup_mcp_config
verify_installation

echo ""
log "Browser-Setup abgeschlossen."
log "  Cache: ${BROWSER_CACHE}"
log "  MCP:   Playwright MCP Server in ~/.claude.json"
log "  Test:  /browser status (in Arasul TUI)"
echo ""
