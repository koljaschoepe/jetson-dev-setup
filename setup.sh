#!/usr/bin/env bash
# =============================================================================
# Jetson Orin Nano Super — Automatisiertes Headless Dev-Server Setup
# =============================================================================
# Usage: sudo ./setup.sh [--skip-reboot] [--step N]
#
# Voraussetzungen:
#   1. JetPack 6.2.2 geflasht (SD-Karte oder NVMe via SDK Manager)
#   2. oem-config abgeschlossen (Erststart-Assistent)
#   3. SSH-Zugang zum Gerät
#   4. .env Datei konfiguriert (cp .env.example .env && nano .env)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/var/log/jetson-setup"
SKIP_REBOOT=false
SINGLE_STEP=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; }
step() { echo -e "\n${BLUE}═══════════════════════════════════════════════${NC}"; echo -e "${BLUE}  $*${NC}"; echo -e "${BLUE}═══════════════════════════════════════════════${NC}\n"; }
info() { echo -e "${CYAN}[i]${NC} $*"; }

# ---------------------------------------------------------------------------
# Konfiguration laden
# ---------------------------------------------------------------------------
load_config() {
    local env_file="${SCRIPT_DIR}/.env"

    if [[ ! -f "$env_file" ]]; then
        err "Keine .env Datei gefunden!"
        echo ""
        info "Erstelle eine .env aus der Vorlage:"
        echo "  cp .env.example .env"
        echo "  nano .env"
        echo ""
        info "Oder starte den interaktiven Modus:"
        echo "  sudo ./setup.sh --interactive"
        exit 1
    fi

    # shellcheck source=/dev/null
    source "$env_file"

    # Pflichtfelder prüfen
    local missing=false
    for var in CUSTOMER_NAME JETSON_USER JETSON_HOSTNAME; do
        if [[ "${!var:-}" == "CHANGEME" ]] || [[ -z "${!var:-}" ]]; then
            err "Variable $var ist nicht konfiguriert in .env"
            missing=true
        fi
    done

    if [[ "$missing" == true ]]; then
        err "Bitte alle CHANGEME-Werte in .env anpassen"
        exit 1
    fi

    # Defaults setzen
    NVME_DEVICE="${NVME_DEVICE:-/dev/nvme0n1}"
    NVME_MOUNT="${NVME_MOUNT:-/mnt/nvme}"
    SWAP_SIZE="${SWAP_SIZE:-32G}"
    INSTALL_TAILSCALE="${INSTALL_TAILSCALE:-false}"
    NODE_VERSION="${NODE_VERSION:-22}"
    INSTALL_CLAUDE="${INSTALL_CLAUDE:-true}"
    INSTALL_OLLAMA="${INSTALL_OLLAMA:-false}"
    POWER_MODE="${POWER_MODE:-3}"
    DOCKER_LOG_MAX_SIZE="${DOCKER_LOG_MAX_SIZE:-10m}"
    DOCKER_LOG_MAX_FILES="${DOCKER_LOG_MAX_FILES:-3}"
    GIT_USER_NAME="${GIT_USER_NAME:-}"
    GIT_USER_EMAIL="${GIT_USER_EMAIL:-}"

    # Abgeleitete Variablen
    REAL_USER="$JETSON_USER"
    REAL_HOME=$(eval echo "~${REAL_USER}")
}

# ---------------------------------------------------------------------------
# Interaktiver Modus: .env generieren
# ---------------------------------------------------------------------------
interactive_config() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  Jetson Dev Setup — Interaktive Konfiguration     ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════╝${NC}"
    echo ""

    local env_file="${SCRIPT_DIR}/.env"

    read -rp "Kundenname / Projektname: " i_customer
    read -rp "Jetson Benutzername: " i_user
    read -rp "Hostname [jetson]: " i_hostname
    i_hostname="${i_hostname:-jetson}"
    read -rp "Swap-Größe [32G]: " i_swap
    i_swap="${i_swap:-32G}"
    read -rp "Tailscale installieren? (true/false) [false]: " i_tailscale
    i_tailscale="${i_tailscale:-false}"
    read -rp "Git Name: " i_git_name
    read -rp "Git Email: " i_git_email
    read -rp "Claude Code installieren? (true/false) [true]: " i_claude
    i_claude="${i_claude:-true}"

    cp "${SCRIPT_DIR}/.env.example" "$env_file"
    sed -i "s/CUSTOMER_NAME=\"CHANGEME\"/CUSTOMER_NAME=\"${i_customer}\"/" "$env_file"
    sed -i "s/JETSON_USER=\"CHANGEME\"/JETSON_USER=\"${i_user}\"/" "$env_file"
    sed -i "s/JETSON_HOSTNAME=\"jetson\"/JETSON_HOSTNAME=\"${i_hostname}\"/" "$env_file"
    sed -i "s/SWAP_SIZE=\"32G\"/SWAP_SIZE=\"${i_swap}\"/" "$env_file"
    sed -i "s/INSTALL_TAILSCALE=\"false\"/INSTALL_TAILSCALE=\"${i_tailscale}\"/" "$env_file"
    sed -i "s/GIT_USER_NAME=\"CHANGEME\"/GIT_USER_NAME=\"${i_git_name}\"/" "$env_file"
    sed -i "s/GIT_USER_EMAIL=\"CHANGEME\"/GIT_USER_EMAIL=\"${i_git_email}\"/" "$env_file"
    sed -i "s/INSTALL_CLAUDE=\"true\"/INSTALL_CLAUDE=\"${i_claude}\"/" "$env_file"

    log ".env Datei erstellt: ${env_file}"
    echo ""
}

# ---------------------------------------------------------------------------
# Prüfungen
# ---------------------------------------------------------------------------
check_root() {
    if [[ $EUID -ne 0 ]]; then
        err "Dieses Script muss mit sudo ausgeführt werden"
        echo "  sudo ./setup.sh"
        exit 1
    fi
}

check_jetson() {
    if [[ -f /etc/nv_tegra_release ]]; then
        local l4t_version
        l4t_version=$(head -1 /etc/nv_tegra_release | sed 's/.*R\([0-9]*\).*/\1/')
        log "Jetson erkannt (L4T R${l4t_version})"
    elif [[ -d /proc/device-tree ]] && grep -q "nvidia" /proc/device-tree/compatible 2>/dev/null; then
        log "Jetson-Plattform erkannt"
    else
        err "Dies scheint kein Jetson-Gerät zu sein"
        exit 1
    fi
}

check_user_exists() {
    if ! id "$REAL_USER" &>/dev/null; then
        err "Benutzer '${REAL_USER}' existiert nicht auf diesem System"
        err "Bitte JETSON_USER in .env korrigieren"
        exit 1
    fi
}

setup_logging() {
    mkdir -p "$LOG_DIR"
    local logfile="${LOG_DIR}/setup-$(date +%Y%m%d-%H%M%S).log"
    exec > >(tee -a "$logfile")
    exec 2>&1
    log "Logfile: ${logfile}"
}

# ---------------------------------------------------------------------------
# Argumente parsen
# ---------------------------------------------------------------------------
INTERACTIVE=false
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --skip-reboot)   SKIP_REBOOT=true; shift ;;
            --step)          SINGLE_STEP="$2"; shift 2 ;;
            --interactive)   INTERACTIVE=true; shift ;;
            -h|--help)
                echo "Usage: sudo ./setup.sh [OPTIONEN]"
                echo ""
                echo "Optionen:"
                echo "  --interactive    Interaktiver Modus (.env wird generiert)"
                echo "  --skip-reboot    Kein Reboot nach Setup"
                echo "  --step N         Nur Schritt N ausführen (1-7)"
                echo "  -h, --help       Diese Hilfe anzeigen"
                echo ""
                echo "Schritte:"
                echo "  1  System-Optimierung (GUI deaktivieren, Services)"
                echo "  2  Netzwerk (Hostname, mDNS)"
                echo "  3  SSH-Härtung (Key-Only, fail2ban)"
                echo "  4  NVMe-Setup (Partition, Mount, Swap)"
                echo "  5  Docker-Konfiguration (NVIDIA Runtime)"
                echo "  6  Entwicklungstools (Node.js, Python, Claude Code)"
                echo "  7  Quality of Life (tmux, Aliases, jtop)"
                exit 0
                ;;
            *) err "Unbekannte Option: $1"; exit 1 ;;
        esac
    done
}

# ---------------------------------------------------------------------------
# Script ausführen
# ---------------------------------------------------------------------------
run_script() {
    local num="$1"
    local name="$2"
    local script="${SCRIPT_DIR}/scripts/${num}-${name}.sh"

    if [[ ! -f "$script" ]]; then
        err "Script nicht gefunden: $script"
        return 1
    fi

    step "Schritt ${num}: ${name}"

    # Alle Konfig-Variablen exportieren für Subscripts
    export REAL_USER REAL_HOME NVME_DEVICE NVME_MOUNT SWAP_SIZE
    export INSTALL_TAILSCALE INSTALL_CLAUDE INSTALL_OLLAMA
    export NODE_VERSION POWER_MODE JETSON_HOSTNAME CUSTOMER_NAME
    export GIT_USER_NAME GIT_USER_EMAIL
    export DOCKER_LOG_MAX_SIZE DOCKER_LOG_MAX_FILES
    export SCRIPT_DIR

    if bash "$script"; then
        log "Schritt ${num} erfolgreich abgeschlossen"
    else
        local rc=$?
        if [[ $rc -eq 2 ]]; then
            warn "Schritt ${num} übersprungen (bereits konfiguriert)"
        else
            err "Schritt ${num} fehlgeschlagen (Exit Code: ${rc})"
            err "Logs prüfen: ${LOG_DIR}/"
            exit 1
        fi
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
parse_args "$@"
check_root

if [[ "$INTERACTIVE" == true ]]; then
    interactive_config
fi

load_config
check_jetson
check_user_exists
setup_logging

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  Jetson Orin Nano Super — Headless Dev Server Setup          ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║  Kunde:    ${CUSTOMER_NAME}"
echo "║  User:     ${REAL_USER}"
echo "║  Home:     ${REAL_HOME}"
echo "║  Hostname: ${JETSON_HOSTNAME}"
echo "║  NVMe:     ${NVME_DEVICE} → ${NVME_MOUNT}"
echo "║  Swap:     ${SWAP_SIZE}"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

if [[ -n "$SINGLE_STEP" ]]; then
    case "$SINGLE_STEP" in
        1) run_script "01" "system-optimize" ;;
        2) run_script "02" "network-setup" ;;
        3) run_script "03" "ssh-harden" ;;
        4) run_script "04" "nvme-setup" ;;
        5) run_script "05" "docker-setup" ;;
        6) run_script "06" "devtools-setup" ;;
        7) run_script "07" "quality-of-life" ;;
        *) err "Ungültiger Schritt: $SINGLE_STEP (muss 1-7 sein)"; exit 1 ;;
    esac
else
    run_script "01" "system-optimize"
    run_script "02" "network-setup"
    run_script "03" "ssh-harden"

    if lsblk "$NVME_DEVICE" &>/dev/null 2>&1; then
        run_script "04" "nvme-setup"
    else
        warn "Kein NVMe-Gerät bei ${NVME_DEVICE} gefunden — NVMe-Setup übersprungen"
        warn "Später ausführen: sudo ./setup.sh --step 4"
        NVME_MOUNT=""
    fi

    run_script "05" "docker-setup"
    run_script "06" "devtools-setup"
    run_script "07" "quality-of-life"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Setup abgeschlossen!                                     ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║  Nächste Schritte:                                           ║"
echo "║  1. Mac SSH-Config einrichten (siehe config/mac-ssh-config)  ║"
echo "║  2. Neustart: sudo reboot                                   ║"
echo "║  3. Verbinden: ssh ${JETSON_HOSTNAME}"
echo "║  4. Arbeiten: t → claude                                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"

if [[ "$SKIP_REBOOT" == false ]]; then
    echo ""
    warn "Neustart empfohlen: sudo reboot"
fi
