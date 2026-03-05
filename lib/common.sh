#!/usr/bin/env bash
# =============================================================================
# Shared shell library for all setup scripts
# Source this file: source "$(dirname "$0")/../lib/common.sh"
# =============================================================================

# Color constants
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Logging functions
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; }
skip() { echo -e "${YELLOW}[→]${NC} $* (already done)"; }
info() { echo -e "${CYAN}[i]${NC} $*"; }
step() { echo -e "\n${BLUE}═══════════════════════════════════════════════${NC}"; echo -e "${BLUE}  $*${NC}"; echo -e "${BLUE}═══════════════════════════════════════════════${NC}\n"; }

# Run a command as the non-root user
# Usage: run_as_user "command with args" (passed as single string to bash -c)
run_as_user() {
    sudo -u "$REAL_USER" -H -- bash -c "$1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        err "This script must be run with sudo"
        echo "  sudo $0"
        exit 1
    fi
}

# Check internet connectivity
check_internet() {
    if ! curl -s --connect-timeout 5 https://connectivity-check.ubuntu.com/ >/dev/null 2>&1; then
        warn "No internet connection detected"
        return 1
    fi
    return 0
}
