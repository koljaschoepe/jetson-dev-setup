#!/usr/bin/env bash
# =============================================================================
# Jetson Orin Nano Super — Automated Headless Dev Server Setup
# =============================================================================
# Usage: sudo ./setup.sh [--skip-reboot] [--step N] [--interactive]
#
# Prerequisites:
#   1. JetPack 6.2.2 flashed (SD card or NVMe via SDK Manager)
#   2. oem-config completed (first-boot wizard)
#   3. SSH access to the device
#   4. .env file configured (cp .env.example .env && nano .env)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/var/log/jetson-setup"
SKIP_REBOOT=false
SINGLE_STEP=""

# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

# ---------------------------------------------------------------------------
# Load configuration
# ---------------------------------------------------------------------------
load_config() {
    local env_file="${SCRIPT_DIR}/.env"

    if [[ ! -f "$env_file" ]]; then
        err "No .env file found!"
        echo ""
        info "Create one from the template:"
        echo "  cp .env.example .env"
        echo "  nano .env"
        echo ""
        info "Or start interactive mode:"
        echo "  sudo ./setup.sh --interactive"
        exit 1
    fi

    # shellcheck source=/dev/null
    source "$env_file"

    # Validate required fields
    local missing=false
    for var in CUSTOMER_NAME JETSON_USER JETSON_HOSTNAME; do
        if [[ "${!var:-}" == "CHANGEME" ]] || [[ -z "${!var:-}" ]]; then
            err "Variable $var is not configured in .env"
            missing=true
        fi
    done

    if [[ "$missing" == true ]]; then
        err "Please set all CHANGEME values in .env"
        exit 1
    fi

    # Set defaults
    NVME_DEVICE="${NVME_DEVICE:-/dev/nvme0n1}"
    NVME_MOUNT="${NVME_MOUNT:-/mnt/nvme}"
    SWAP_SIZE="${SWAP_SIZE:-32G}"
    INSTALL_TAILSCALE="${INSTALL_TAILSCALE:-false}"
    NODE_VERSION="${NODE_VERSION:-22}"
    INSTALL_CLAUDE="${INSTALL_CLAUDE:-true}"
    INSTALL_OLLAMA="${INSTALL_OLLAMA:-false}"
    INSTALL_ARASUL_TUI="${INSTALL_ARASUL_TUI:-true}"
    POWER_MODE="${POWER_MODE:-3}"
    DOCKER_LOG_MAX_SIZE="${DOCKER_LOG_MAX_SIZE:-10m}"
    DOCKER_LOG_MAX_FILES="${DOCKER_LOG_MAX_FILES:-3}"
    GIT_USER_NAME="${GIT_USER_NAME:-}"
    GIT_USER_EMAIL="${GIT_USER_EMAIL:-}"

    # Derived variables
    REAL_USER="$JETSON_USER"
    REAL_HOME=$(eval echo "~${REAL_USER}")
}

# ---------------------------------------------------------------------------
# Interactive mode: generate .env
# ---------------------------------------------------------------------------
interactive_config() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  Jetson Dev Setup — Interactive Configuration      ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════╝${NC}"
    echo ""

    local env_file="${SCRIPT_DIR}/.env"

    read -rp "Customer / Project name: " i_customer
    read -rp "Jetson username: " i_user
    read -rp "Hostname [jetson]: " i_hostname
    i_hostname="${i_hostname:-jetson}"
    read -rp "Swap size [32G]: " i_swap
    i_swap="${i_swap:-32G}"
    read -rp "Install Tailscale? (true/false) [false]: " i_tailscale
    i_tailscale="${i_tailscale:-false}"
    read -rp "Git name: " i_git_name
    read -rp "Git email: " i_git_email
    read -rp "Install Claude Code? (true/false) [true]: " i_claude
    i_claude="${i_claude:-true}"
    read -rp "Install Arasul TUI? (true/false) [true]: " i_tui
    i_tui="${i_tui:-true}"

    cp "${SCRIPT_DIR}/.env.example" "$env_file"
    sed -i "s/CUSTOMER_NAME=\"CHANGEME\"/CUSTOMER_NAME=\"${i_customer}\"/" "$env_file"
    sed -i "s/JETSON_USER=\"CHANGEME\"/JETSON_USER=\"${i_user}\"/" "$env_file"
    sed -i "s/JETSON_HOSTNAME=\"jetson\"/JETSON_HOSTNAME=\"${i_hostname}\"/" "$env_file"
    sed -i "s/SWAP_SIZE=\"32G\"/SWAP_SIZE=\"${i_swap}\"/" "$env_file"
    sed -i "s/INSTALL_TAILSCALE=\"false\"/INSTALL_TAILSCALE=\"${i_tailscale}\"/" "$env_file"
    sed -i "s/GIT_USER_NAME=\"CHANGEME\"/GIT_USER_NAME=\"${i_git_name}\"/" "$env_file"
    sed -i "s/GIT_USER_EMAIL=\"CHANGEME\"/GIT_USER_EMAIL=\"${i_git_email}\"/" "$env_file"
    sed -i "s/INSTALL_CLAUDE=\"true\"/INSTALL_CLAUDE=\"${i_claude}\"/" "$env_file"
    sed -i "s/INSTALL_ARASUL_TUI=\"true\"/INSTALL_ARASUL_TUI=\"${i_tui}\"/" "$env_file"

    log ".env file created: ${env_file}"
    echo ""
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
check_jetson() {
    if [[ -f /etc/nv_tegra_release ]]; then
        local l4t_version
        l4t_version=$(head -1 /etc/nv_tegra_release | sed 's/.*R\([0-9]*\).*/\1/')
        log "Jetson detected (L4T R${l4t_version})"
    elif [[ -d /proc/device-tree ]] && grep -q "nvidia" /proc/device-tree/compatible 2>/dev/null; then
        log "Jetson platform detected"
    else
        err "This does not appear to be a Jetson device"
        exit 1
    fi
}

check_user_exists() {
    if ! id "$REAL_USER" &>/dev/null; then
        err "User '${REAL_USER}' does not exist on this system"
        err "Please fix JETSON_USER in .env"
        exit 1
    fi
}

setup_logging() {
    mkdir -p "$LOG_DIR"
    local logfile
    logfile="${LOG_DIR}/setup-$(date +%Y%m%d-%H%M%S).log"
    exec > >(tee -a "$logfile")
    exec 2>&1
    log "Logfile: ${logfile}"
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
INTERACTIVE=false
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --skip-reboot)   SKIP_REBOOT=true; shift ;;
            --step)          SINGLE_STEP="$2"; shift 2 ;;
            --interactive)   INTERACTIVE=true; shift ;;
            -h|--help)
                echo "Usage: sudo ./setup.sh [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --interactive    Interactive mode (generates .env)"
                echo "  --skip-reboot    No reboot after setup"
                echo "  --step N         Run only step N (1-8)"
                echo "  -h, --help       Show this help"
                echo ""
                echo "Steps:"
                echo "  1  System optimization (disable GUI, services)"
                echo "  2  Network (hostname, mDNS, firewall)"
                echo "  3  SSH hardening (key-only, fail2ban)"
                echo "  4  NVMe setup (partition, mount, swap)"
                echo "  5  Docker configuration (NVIDIA Runtime)"
                echo "  6  Dev tools (Node.js, Python, Claude Code)"
                echo "  7  Quality of life (tmux, aliases, jtop)"
                echo "  8  Headless browser (Playwright + Chromium)"
                exit 0
                ;;
            *) err "Unknown option: $1"; exit 1 ;;
        esac
    done
}

# ---------------------------------------------------------------------------
# Run a setup script
# ---------------------------------------------------------------------------
run_script() {
    local num="$1"
    local name="$2"
    local script="${SCRIPT_DIR}/scripts/${num}-${name}.sh"

    if [[ ! -f "$script" ]]; then
        err "Script not found: $script"
        return 1
    fi

    step "Step ${num}: ${name}"

    # Export all config variables for subscripts
    export REAL_USER REAL_HOME NVME_DEVICE NVME_MOUNT SWAP_SIZE
    export INSTALL_TAILSCALE INSTALL_CLAUDE INSTALL_OLLAMA
    export INSTALL_ARASUL_TUI
    export NODE_VERSION POWER_MODE JETSON_HOSTNAME CUSTOMER_NAME
    export GIT_USER_NAME GIT_USER_EMAIL
    export DOCKER_LOG_MAX_SIZE DOCKER_LOG_MAX_FILES
    export STATIC_IP STATIC_GATEWAY
    export SCRIPT_DIR

    if bash "$script"; then
        log "Step ${num} completed successfully"
    else
        local rc=$?
        if [[ $rc -eq 2 ]]; then
            warn "Step ${num} skipped (already configured)"
        else
            err "Step ${num} failed (exit code: ${rc})"
            err "Check logs: ${LOG_DIR}/"
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
echo "║  Customer: ${CUSTOMER_NAME}"
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
        8) run_script "08" "browser-setup" ;;
        *) err "Invalid step: $SINGLE_STEP (must be 1-8)"; exit 1 ;;
    esac
else
    run_script "01" "system-optimize"
    run_script "02" "network-setup"
    run_script "03" "ssh-harden"

    if lsblk "$NVME_DEVICE" &>/dev/null 2>&1; then
        run_script "04" "nvme-setup"
    else
        warn "No NVMe device found at ${NVME_DEVICE} — skipping NVMe setup"
        warn "Run later: sudo ./setup.sh --step 4"
        NVME_MOUNT=""
    fi

    run_script "05" "docker-setup"
    run_script "06" "devtools-setup"
    run_script "07" "quality-of-life"
    run_script "08" "browser-setup"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  Setup complete!                                             ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║  Next steps:                                                 ║"
echo "║  1. Set up Mac SSH config (see config/mac-ssh-config)       ║"
echo "║  2. Reboot: sudo reboot                                     ║"
echo "║  3. Connect: ssh ${JETSON_HOSTNAME}"
echo "║  4. Work: t → claude                                        ║"
echo "╚═══════════════════════════════════════════════════════════════╝"

if [[ "$SKIP_REBOOT" == false ]]; then
    echo ""
    warn "Reboot recommended: sudo reboot"
fi
