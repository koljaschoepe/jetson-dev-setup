# Arasul — Claude Code Context

## What Is This Repo?
Automated setup scripts to turn a fresh NVIDIA Jetson Orin Nano Super Dev Kit (8GB) into a headless development server. Optimized for remote development via SSH + Claude Code. Used to prepare Jetson devices with a consistent configuration.

## Hardware Context
- **Device:** NVIDIA Jetson Orin Nano Super Developer Kit (2025)
- **SoC:** Orin (6x Arm Cortex-A78AE @ 1.7GHz, 1024 CUDA Cores Ampere GPU)
- **RAM:** 8GB LPDDR5 **shared** between CPU and GPU
- **OS:** JetPack 6.2.2 (Ubuntu 22.04, Jetson Linux 36.5, Kernel 5.15, CUDA 12.6)
- **Arch:** aarch64 / ARM64
- **Storage:** NVMe M.2 2280 SSD (primary storage)
- **Network:** Gigabit Ethernet

## Key Constraints
- Only 8GB RAM shared CPU/GPU — no desktop, minimize services
- ARM64 — not all x86 packages/containers available
- Docker images must be `linux/arm64` or multi-arch
- NVMe is required for Docker/Swap (SD card too slow)
- NVIDIA Container Runtime pre-installed — `--runtime=nvidia` for GPU

## Security Configuration
- SSH: Key-only auth (`/etc/ssh/sshd_config.d/99-jetson-hardened.conf`)
- Firewall: UFW active, only SSH (22) + mDNS (5353) allowed
- fail2ban: sshd jail + recidive jail (repeat offenders 1 week ban)
- Automatic security patches via `unattended-upgrades` (Docker/NVIDIA excluded)
- Network hardening: SYN cookies, reverse-path filter, no redirects

## Performance Tuning
- Kernel: `vm.swappiness=10`, `vfs_cache_pressure=50`, `dirty_ratio=10`, `min_free_kbytes=65536`
- OOM protection: SSH (`OOMScoreAdjust=-900`), Docker (`-500`)
- NVMe: `noatime` mount, `none` I/O scheduler, weekly TRIM
- Journald: 200MB limit, 1 week retention
- ~39 running services (desktop/WiFi/print disabled)

## Configuration
All device-specific variables are in `.env` (created from `.env.example`).
Scripts read variables via exported environment variables from `setup.sh`.

## Repo Structure
```
├── .env.example        # Configuration template
├── pyproject.toml      # Python package definition (Arasul TUI)
├── CLAUDE.md           # This file
├── README.md           # Setup guide
├── setup.sh            # Main orchestrator (sources .env)
├── lib/
│   └── common.sh       # Shared shell library (log, err, check_root, etc.)
├── arasul_tui/
│   ├── app.py          # TUI application (two-level navigation)
│   ├── install.sh      # Installer (venv + launcher)
│   ├── commands/       # Command handlers (9 modules)
│   │   ├── __init__.py      # Re-exports all handlers
│   │   ├── project.py       # /open, /create, /clone, /delete, /info, /repos
│   │   ├── ai.py            # /claude, /auth
│   │   ├── system.py        # /status, /health, /setup, /docker
│   │   ├── security.py      # /keys, /logins, /security
│   │   ├── git_ops.py       # /git (pull/push/log/status + setup wizard)
│   │   ├── browser_cmd.py   # /browser (status/test/install/mcp)
│   │   ├── mcp.py           # /mcp (list/add/test/remove)
│   │   ├── tailscale_cmd.py # /tailscale (status/install/up/down)
│   │   └── meta.py          # /help, /exit
│   └── core/
│       ├── auth.py          # Claude OAuth token management
│       ├── browser.py       # Playwright/headless browser management
│       ├── constants.py     # Shared constants (CLAUDE_JSON path)
│       ├── docker_info.py   # Docker container listing
│       ├── git_info.py      # Git metadata (branch, dirty, language detection)
│       ├── projects.py      # YAML project registry CRUD
│       ├── registry.py      # Command registry (with categories + subcommands)
│       ├── router.py        # Command routing and dispatch (21 commands)
│       ├── security.py      # SSH keys, login history, security audit
│       ├── setup_wizard.py  # Setup step definitions + runner
│       ├── shell.py         # Subprocess helper (run_cmd)
│       ├── state.py         # TUI state (Screen enum, wizard dict)
│       ├── types.py         # CommandResult and type definitions
│       └── ui.py            # Rich UI (project screen, styled panels, checklist)
├── tests/              # Pytest test suite
├── scripts/
│   ├── 01-system-optimize.sh   # Disable GUI, services, tune kernel
│   ├── 02-network-setup.sh     # Hostname, mDNS, UFW firewall, optional Tailscale
│   ├── 03-ssh-harden.sh        # Key-only auth, fail2ban (sshd + recidive)
│   ├── 04-nvme-setup.sh        # Partition, mount, swap, I/O scheduler, crons
│   ├── 05-docker-setup.sh      # Docker, NVIDIA Runtime, Compose
│   ├── 06-devtools-setup.sh    # Node.js, Python, Git, Claude Code
│   ├── 07-quality-of-life.sh   # tmux, aliases, MOTD
│   └── 08-browser-setup.sh     # Playwright + headless Chromium
├── config/
│   ├── tmux.conf               # tmux configuration
│   ├── bash_aliases            # Shell aliases
│   └── mac-ssh-config          # SSH config template for Mac
├── .github/
│   └── workflows/
│       └── ci.yml              # CI (ruff, shellcheck, pytest)
└── agents/
    └── README.md               # Claude Code agent patterns
```

## Script Conventions
- All scripts are idempotent — safe to run multiple times
- Scripts check prerequisites and skip completed steps
- Each script can run standalone or via `setup.sh`
- Logs at `/var/log/jetson-setup/`
- Exit codes: 0=success, 1=error, 2=skipped

## Arasul TUI
- Source code in `arasul_tui/`
- Install locally from the repo:
  - `pip install -e .`
  - `arasul`
- Optional installer:
  - `./arasul_tui/install.sh`
  - Start with `arasul` or alias `atui`
- Two-level navigation: Main Screen → Project Screen
- 21 slash commands across 8 categories:
  - **Projects:** `/open`, `/create`, `/clone`, `/delete`, `/info`, `/repos`
  - **Claude Code:** `/claude`, `/auth`
  - **Git:** `/git` (no args = setup wizard), `/git pull`, `/git push`, `/git log`, `/git status`
  - **System:** `/status`, `/health`, `/setup`, `/docker`
  - **Security:** `/keys`, `/logins`, `/security`
  - **Browser:** `/browser status|test|install|mcp`
  - **MCP:** `/mcp list|add|test|remove`
  - **Network:** `/tailscale status|install|up|down`
  - **Meta:** `/help`, `/exit`
- Keyboard shortcuts: `1-9` (select project), `n` (new), `d` (delete), `c` (Claude), `g` (lazygit), `b` (back)

## Headless Browser (Playwright)
- Playwright + Chromium headless for AI agent browser automation
- Browser cache on NVMe: `/mnt/nvme/playwright-browsers`
- Env variable: `PLAYWRIGHT_BROWSERS_PATH=/mnt/nvme/playwright-browsers`
- MCP server: Playwright MCP configured in `~/.claude.json`
- Claude Code can navigate web pages, take screenshots, fill forms
- Installation: `sudo ./setup.sh --step 8` or `/browser install` in the TUI

## Useful Commands
```bash
jtop                    # Jetson dashboard (GPU, RAM, temp)
sudo tegrastats         # One-line system stats
docker compose up -d    # Start stack
```

## Development Workflow
1. SSH from Mac: `ssh jetson`
2. tmux session: `t` (alias)
3. Project: `cd ~/projects/<project>`
4. Claude Code: `claude`

## Important Paths
- `/mnt/nvme/projects/` — All projects
- `/mnt/nvme/docker/` — Docker data root
- `/mnt/nvme/models/` — AI models (Ollama etc.)
- `/mnt/nvme/playwright-browsers/` — Headless Chromium cache
- `/mnt/nvme/backups/` — Backups
- `/var/log/jetson-setup/` — Setup logs
- `/var/log/jetson-setup/nvme-health.log` — Weekly NVMe SMART data
- `/etc/ssh/sshd_config.d/99-jetson-hardened.conf` — SSH hardening
- `/etc/sysctl.d/99-jetson-dev.conf` — Kernel parameters
- `/etc/cron.weekly/nvme-health` — NVMe health check cron
- `/etc/cron.weekly/docker-cleanup` — Docker cleanup cron

## ARM64 Notes
- `docker buildx` for multi-arch builds
- npm packages with native addons need `build-essential` + `python3`
- PyTorch for Jetson: NVIDIA wheels, not PyPI
- CUDA at `/usr/local/cuda-12.6/`, already in PATH
