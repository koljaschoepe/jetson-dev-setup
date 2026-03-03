# Arasul

> Automated setup tool for turning an NVIDIA Jetson Orin Nano Super into a headless development server. Optimized for SSH + AI coding workflows (Claude Code, Codex).

---

## Complete Step-by-Step Guide

This guide takes you from an unopened box to a fully configured, remotely accessible dev server. We flash **directly to the NVMe SSD** — no SD card required.

### Two Machines, Clear Roles

| Machine | Role | When |
|---------|------|------|
| **Ubuntu Laptop** (x86_64) | Flashing, serial console, oem-config | Initial setup only (Phase 1–4) |
| **Mac** (your workstation) | SSH access, daily development | From Phase 5 onward, permanently |

After initial setup you **never need the Ubuntu laptop again** — the Jetson runs headless and you work exclusively via SSH from your Mac.

### What You Need

#### Hardware Checklist

| # | Component | Details | Source |
|---|-----------|---------|--------|
| 1 | Jetson Orin Nano Super Dev Kit | 8GB LPDDR5 | NVIDIA / Distributor |
| 2 | NVMe M.2 2280 PCIe SSD | 256GB–2TB, e.g. Samsung 980 PRO, WD SN770 | Electronics retailer |
| 3 | USB-C Cable | Data-capable (not charge-only!) | Included or separate |
| 4 | Ethernet Cable | Cat5e or Cat6 | Standard |
| 5 | 19V DC Power Supply | Included with Dev Kit | Included |
| 6 | Phillips Screwdriver | Small (#1), for SSD mounting | Toolbox |
| 7 | **Paperclip** (or tweezers) | To briefly short 2 pins for Recovery Mode (see Phase 2) | Desk |

#### Software on the Ubuntu Laptop (Flash Host)

| # | Software | Installation |
|---|----------|-------------|
| 1 | **NVIDIA SDK Manager** (.deb) | Download from [developer.nvidia.com/sdk-manager](https://developer.nvidia.com/sdk-manager) → **Download .deb (Ubuntu)** |
| 2 | **screen** | `sudo apt install screen` (for serial console) |
| 3 | **NVIDIA Developer Account** | Free registration at [developer.nvidia.com](https://developer.nvidia.com) |

> **Important:** The SDK Manager only runs on **Ubuntu x86_64** (20.04 or 22.04). Download the **.deb variant**, not the Docker image.

#### Software on the Mac (Workstation)

| # | Software | Status |
|---|----------|--------|
| 1 | **SSH Client** | Pre-installed on macOS |
| 2 | **Homebrew** (optional) | Package manager for macOS — needed if you want `screen` for serial console |

**Install Homebrew (if not already present):**

```bash
brew --version

# If not installed:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

---

### Phase 1: Install NVMe SSD

> **When:** Before first power-on. The Jetson is off, no cables connected.

**Step 1.1 — Unbox the Dev Kit**

Check box contents:
- Jetson Orin Nano Super Module (pre-mounted on Carrier Board)
- 19V DC power supply with cable
- Quick Start Guide

**Step 1.2 — Flip the Carrier Board**

- Place the board upside down on an anti-static surface
- The M.2 Key-M slot is on the **bottom** of the Carrier Board
- Look for the long connector with a screw hole next to it

**Step 1.3 — Insert the NVMe SSD**

1. Remove the mounting screw next to the M.2 slot (if present)
2. Insert the NVMe SSD at a **30° angle** into the slot (gold contacts first)
3. Gently press the SSD down until it lies flat
4. Secure with the screw — **don't over-tighten!**

**Step 1.4 — Flip the Board Back**

- Place the Carrier Board right-side up
- Check that the Jetson module (the large green chip with heatsink) is firmly seated

---

### Phase 2: Enter Recovery Mode

> **When:** Right after SSD installation. Do NOT connect the power supply yet.

#### Important: There Are No Physical Buttons!

The Jetson Orin Nano Dev Kit has **no built-in buttons**. Instead, there's the **Button Header (J14)** — a small 12-pin header on the Carrier Board. For Recovery Mode you just need to **briefly short two pins with a paperclip** — takes 3 seconds.

**What works as a "jumper"** (no special cable needed):

| Household item | Instructions |
|----------------|-------------|
| **Paperclip** (recommended) | Straighten so two ends are parallel. Touch both pins simultaneously. |
| **Tweezers** (metal) | Press metal tips onto the two pins. |
| **Stripped wire end** | A short piece of wire, e.g. from an old charging cable. |

> The pins are only **2.54mm apart** — very close together. Any piece of metal that touches both pins simultaneously will work.

#### Finding Button Header (J14)

The header is a small 12-pin connector on the Carrier Board. Look for the label **J14** on the PCB (near the ports).

```
Button Header (J14) — Pin Layout:

     ┌──────────────────────────┐
     │  12  10   8   6   4   2  │
     │  11   9   7   5   3   1  │
     └──────────────────────────┘

  Pins 9+10 → Force Recovery Mode ← THIS IS WHAT YOU NEED
  Pins 7+8  → Reset
  Pins 1+2  → Power On/Off
```

**Step 2.1 — Connect USB-C Cable**

- Plug the **USB-C cable** into the **Jetson's USB-C port** (next to the USB-A ports)
- The other end goes into the **Ubuntu laptop**
- Do **NOT** connect the power supply yet!

**Step 2.2 — Activate Recovery Mode (with Paperclip)**

Straighten paperclip and have it ready. Then **in exactly this order**:

1. **Press paperclip onto Pins 9 and 10** — touch both pins simultaneously and **hold**
2. **While the paperclip connects the pins:** Plug in the **19V power supply**
3. **Wait 2–3 seconds**
4. **Remove paperclip**

The Jetson now starts in Recovery Mode (no screen output, no fan spin — this is normal).

> **Good to know:** If the Jetson is already running and you need Recovery Mode again, you can also do it via software:
> ```bash
> sudo reboot --force forced-recovery
> ```

**Step 2.3 — Verify Recovery Mode**

On the **Ubuntu laptop** terminal:

```bash
lsusb | grep -i nvidia
```

Expected output (similar to):
```
Bus 001 Device 023: ID 0955:7523 NVIDIA Corp. APX
```

If you see `NVIDIA Corp.`, the Jetson is in Recovery Mode. If not:
- Check USB-C cable (must support data, not just charging)
- Try a different USB port on the host (directly on mainboard, not through a hub)
- Repeat Step 2.2

---

### Phase 3: Flash JetPack to NVMe

> **When:** Jetson is in Recovery Mode (Phase 2 complete). You're at the **Ubuntu laptop**.

**Step 3.1 — Install SDK Manager (if not already done)**

On the **Ubuntu laptop**:

1. Go to [developer.nvidia.com/sdk-manager](https://developer.nvidia.com/sdk-manager)
2. Click **Download** → choose **.deb (Ubuntu)**
3. A file like `sdkmanager_2.x.x-xxxxx_amd64.deb` will be downloaded

```bash
cd ~/Downloads
sudo apt install ./sdkmanager_*_amd64.deb
```

> If dependencies are missing: `sudo apt --fix-broken install`

**Step 3.2 — Launch SDK Manager**

```bash
sdkmanager
```

A GUI window opens. Log in with your **NVIDIA Developer Account** (free registration at [developer.nvidia.com](https://developer.nvidia.com)).

**Step 3.3 — Step 1: Development Environment**

| Setting | Value |
|---------|-------|
| Product Category | Jetson |
| Hardware Configuration | **Jetson Orin Nano Super Developer Kit** |
| Target OS | **JetPack 6.2.2** / Linux |
| DeepStream | Deselect (not needed) |

> If the Jetson isn't auto-detected: check USB connection (repeat Phase 2).

Click **Continue**.

**Step 3.4 — Step 2: Components**

- **Jetson Linux** (BSP): Must be selected ✓
- **Jetson Runtime Components**: Recommended ✓
- **Jetson SDK Components** (CUDA, cuDNN, TensorRT): Optional — takes ~5GB, recommended for AI/ML

Accept license agreements. Click **Continue**.

**Step 3.5 — Step 3: Flash Settings (IMPORTANT!)**

This determines **where** JetPack gets installed:

| Setting | Value |
|---------|-------|
| Flash Method | **Manual Setup** |
| Storage Device | **NVMe** ← **Critical! Not eMMC or SD Card!** |
| OEM Configuration | **Pre-Config** (user is created directly in SDK Manager) |

> **Warning:** By default, SDK Manager wants to flash to internal eMMC or SD card. You must **explicitly select NVMe** as the storage target. If the option isn't visible:
> - Make sure the NVMe SSD is physically installed
> - Some JetPack versions only show NVMe when you select "Manual Setup"

Click **Flash**. The process takes **10–30 minutes** depending on SSD speed and network connection.

**Step 3.6 — Wait for Flash to Complete**

The SDK Manager shows progress:

1. Downloading components (one-time, gets cached)
2. Creating filesystem image
3. Flashing to NVMe SSD
4. Installing SDK components

**Do not interrupt!** Don't unplug USB or power.

When flash is complete, the Jetson automatically reboots from the NVMe SSD.

---

### Phase 4: Run Setup via Serial Console

> **When:** Right after flash. The Jetson is booting for the first time from NVMe SSD. Stay at the **Flash machine** (Ubuntu laptop or Mac).
>
> **Goal:** Complete everything in one go via serial console — clone repo, run setup, reboot. After that, only the SSH key needs to be copied from the Mac.

Since you chose **Pre-Config** in Phase 3, username, password, and system settings were already configured in SDK Manager. The Jetson boots into a ready-to-use system.

**Step 4.1 — Connect Serial Console**

The **same USB-C cable** from flashing serves as serial console. Wait **1–3 minutes** after flash until the Jetson has booted.

```bash
# Find serial device
ls /dev/ttyACM*
# Typically: /dev/ttyACM0 or /dev/ttyACM1
```

Connect — depending on host system:

```bash
# Ubuntu laptop
sudo apt install screen          # one-time
sudo screen /dev/ttyACM0 115200

# macOS: find device path, then use screen
ls /dev/cu.usbmodem*             # shows e.g. /dev/cu.usbmodem14101
brew install screen              # one-time
screen /dev/cu.usbmodem* 115200

# macOS alternative: cu is pre-installed (no Homebrew needed)
sudo cu -l /dev/cu.usbmodem14101 -s 115200
```

> **Important:** After connecting, **press Enter** — the console only shows the login prompt then.
>
> **Exit:** `screen` with `Ctrl+A` then `K` — `cu` with `~.` (tilde + period).

**Step 4.2 — Log In and Check Network**

```bash
login: your-username
Password: your-password
```

Ethernet cable must be plugged into the Jetson (router/switch). Check IP (on the **Jetson**, not the laptop!):

```bash
ip link show
# Typical: eth0 — but could also be enP8p1s0 etc.

ip addr show eth0 | grep "inet "
# Output e.g.: inet 192.168.1.42/24 ...
```

> Note the **IP address** — you'll need it in Phase 5 for SSH from the Mac.

**Step 4.3 — Clone Repo and Run Setup**

```bash
git clone https://github.com/koljaschoepe/jetson-dev-setup.git
cd jetson-dev-setup
sudo ./setup.sh --interactive
```

The script prompts for all required values:

```
Customer/Project name: my-project
Jetson username: arasul
Hostname [jetson]: jetson
Swap size [32G]: 32G
Install Tailscale? (true/false) [false]: false
Git name: Your Name
Git email: you@example.com
Install Claude Code? (true/false) [true]: true
```

> **Alternative:** Instead of `--interactive` you can edit `.env` manually:
> ```bash
> cp .env.example .env
> nano .env           # Adjust all CHANGEME values
> sudo ./setup.sh
> ```

**Step 4.4 — Watch Setup Progress**

The script runs through 8 steps:

| Step | What Happens | Duration |
|------|-------------|----------|
| 1 | Disable GUI, stop unnecessary services, tune kernel | ~3 min |
| 2 | Set hostname, enable mDNS (Avahi), optional Tailscale | ~1 min |
| 3 | Switch SSH to key-only, install fail2ban | ~1 min |
| 4 | Partition NVMe (if needed), mount, 32GB swap, create directories | ~2 min |
| 5 | Docker data directory on NVMe, NVIDIA Container Runtime | ~2 min |
| 6 | Node.js 22, Python3, Git, Claude Code CLI, jtop | ~5 min |
| 7 | tmux config, shell aliases, custom prompt, MOTD | ~1 min |
| 8 | Playwright + headless Chromium for browser automation | ~3 min |

**Total: ~18 minutes.** Each step shows progress messages.

> **If a step fails:** Check logs at `/var/log/jetson-setup/`. Individual steps can be re-run: `sudo ./setup.sh --step 4`

**Step 4.5 — Reboot**

```bash
sudo reboot
```

The serial console loses connection. The Jetson is now fully configured — you can close the serial console and unplug the USB-C cable.

---

### Phase 5: Set Up SSH from Mac

> **When:** Setup complete, Jetson is rebooting. From here you switch to your **Mac** — you never need the Ubuntu laptop again.

**Step 5.1 — Create SSH Key (if none exists)**

```bash
ls ~/.ssh/id_ed25519.pub

# If not found: create new key
ssh-keygen -t ed25519 -C "your-name@mac"
# Press Enter for default path, optionally set a passphrase
```

**Step 5.2 — Copy SSH Key to the Jetson**

The Jetson must be on the same network as your Mac via Ethernet.

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub USER@IP-ADDRESS
# IP address from Step 4.2, e.g.: ssh-copy-id -i ~/.ssh/id_ed25519.pub arasul@192.168.1.42
```

You'll be asked for the **password** (from the Pre-Config in Phase 3). After that, the key is stored.

> **Error: `Permission denied (publickey)`?**
>
> The setup script has already disabled password login — `ssh-copy-id` can't transfer the key. In this case, add the key **manually via serial console**:
>
> 1. Display and copy public key on Mac:
>    ```bash
>    cat ~/.ssh/id_ed25519.pub
>    ```
>
> 2. Open serial console to Jetson (Ubuntu laptop or Mac):
>    ```bash
>    # Ubuntu laptop
>    sudo screen /dev/ttyACM0 115200
>    # macOS
>    screen /dev/cu.usbmodem* 115200
>    ```
>
> 3. Log in on the **Jetson** and add key — run commands one at a time (serial console has small paste buffer):
>    ```bash
>    mkdir -p ~/.ssh
>    chmod 700 ~/.ssh
>    echo "PASTE-YOUR-COPIED-KEY-HERE" >> ~/.ssh/authorized_keys
>    chmod 600 ~/.ssh/authorized_keys
>    cat ~/.ssh/authorized_keys
>    ```
>    The `cat` command should show a line starting with `ssh-ed25519 AAAA...`.
>
> 4. Exit serial console (`Ctrl+A` then `K`) and test SSH from Mac again.

**Step 5.3 — Test SSH Connection**

```bash
ssh USER@IP-ADDRESS
```

You should connect **without a password prompt**.

---

### Phase 6: Configure Mac SSH Config (Convenience)

> **When:** SSH connection works (Phase 5 complete). From now on you never need to type an IP address again.

**Step 6.1 — Create Sockets Directory**

```bash
mkdir -p ~/.ssh/sockets
```

**Step 6.2 — Edit SSH Config**

```bash
nano ~/.ssh/config
```

Add at the end (replace `USER` and `HOSTNAME`):

```
# --- Jetson via LAN (mDNS) ---
Host jetson
    HostName HOSTNAME.local
    User USER
    IdentityFile ~/.ssh/id_ed25519
    ControlMaster auto
    ControlPersist 600
    ControlPath ~/.ssh/sockets/%r@%h-%p
    ServerAliveInterval 60
    ServerAliveCountMax 3
    LocalForward 3000 localhost:3000
    LocalForward 8080 localhost:8080
    LocalForward 8888 localhost:8888

# --- Jetson via USB-C Direct Connection ---
Host jetson-usb
    HostName 192.168.55.1
    User USER
    IdentityFile ~/.ssh/id_ed25519
```

> Example: If `JETSON_HOSTNAME=jetson` and `JETSON_USER=arasul`, then `HostName` becomes `jetson.local` and `User` becomes `arasul`.

**Step 6.3 — Test Connection**

```bash
# Via LAN (after reboot, mDNS needs ~10 seconds to propagate)
ssh jetson

# Or via USB-C
ssh jetson-usb
```

---

### Phase 7: Verify Everything

> **When:** You're connected via `ssh jetson`. The Jetson has completed setup.

**Step 7.1 — Check MOTD**

On login you'll see a custom banner with system info (RAM, Disk, Temperature).

**Step 7.2 — Test Core Functions**

```bash
# Start tmux session
t

# Check RAM and swap
free -h
# Expected: ~6GB RAM free, ~32GB swap

# Check NVMe
df -h /mnt/nvme
# Expected: NVMe mounted with plenty of storage

# Projects directory
ls ~/projects
# Expected: symlink to /mnt/nvme/projects/

# Docker check
docker run --rm hello-world
# Expected: "Hello from Docker!"

# NVIDIA GPU in Docker
docker run --rm --runtime=nvidia nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi
# Expected: GPU table with Orin

# Node.js
node --version
# Expected: v22.x.x

# Claude Code (if installed)
claude --version
```

**Step 7.3 — Jetson Monitoring**

```bash
# Interactive dashboard
jtop

# Or one-liner
sudo tegrastats
```

---

## Daily Workflow

```bash
# 1. Connect from Mac
ssh jetson

# 2. Start tmux (or resume existing session)
t

# 3. Navigate to project
p                           # Alias for: cd ~/projects
cd my-project

# 4. Start Claude Code
claude

# 5. Check Jetson status
jtop                        # Interactive dashboard
```

## Useful Aliases

| Alias | Command |
|-------|---------|
| `t` | tmux `dev` session (creates or attaches) |
| `c` | Start Claude Code |
| `p` | `cd ~/projects` |
| `jtop` | Jetson system monitor |
| `dps` | Docker containers (formatted) |
| `powermode` | Show NVPower mode |
| `atui` | Start Arasul TUI |

### Arasul TUI

The Jetson ships with the `arasul` interactive TUI for system management, project workflows, and AI tool integration.

```bash
# Start the TUI
arasul

# Or install from the repo
pip install -e .
arasul
```

Available slash commands in the TUI:

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/status` | System status dashboard |
| `/create` | Create new project (interactive) |
| `/clone` | Clone a GitHub repo (interactive) |
| `/open <name>` | Open/activate a project |
| `/delete` | Delete a project (interactive) |
| `/claude` | Start Claude Code (with auth setup wizard) |
| `/codex` | Start Codex |
| `/git` | GitHub CLI setup wizard |
| `/browser` | Headless browser management (status/test/install/mcp) |
| `/exit` | Quit |

Keyboard shortcuts: `1-9` select project by number, `n` new project, `d` delete, `c` Claude, `x` Codex, `b` back.

## Running Individual Setup Steps

```bash
sudo ./setup.sh --step 4    # NVMe setup only
sudo ./setup.sh --step 6    # Dev tools only
sudo ./setup.sh --step 8    # Browser setup only
```

## What You Get

```
~/projects/         → Symlink to /mnt/nvme/projects/ (fast NVMe storage)
/mnt/nvme/          → NVMe mount with projects/, docker/, models/, backups/
32GB Swap on NVMe   → Enough headroom for Docker + development
Docker + NVIDIA     → GPU containers, data on NVMe
Node.js 22 + Claude → AI-assisted development
tmux + Aliases      → Persistent sessions, shortcuts
SSH hardened        → Key-only auth, fail2ban, UFW firewall
arasul TUI          → Interactive system management via `arasul`
Headless browser    → Playwright + Chromium for AI agent automation
Custom MOTD         → Minimal dashboard on login
```

## Configuration

All device-specific settings are managed centrally in `.env`:

```bash
# Required
CUSTOMER_NAME="my-project"
JETSON_USER="arasul"
JETSON_HOSTNAME="jetson"

# Optional
SWAP_SIZE="32G"
INSTALL_TAILSCALE="false"
INSTALL_CLAUDE="true"
INSTALL_OLLAMA="false"
INSTALL_ARASUL_TUI="true"
NODE_VERSION="22"
POWER_MODE="3"          # 0=7W, 1=15W, 3=25W
```

Full template: [`.env.example`](.env.example)

## Repository Structure

```
├── .env.example                # Configuration template (all variables)
├── .gitignore
├── pyproject.toml              # Python package definition (Arasul TUI)
├── CLAUDE.md                   # Context for Claude Code / AI agents
├── README.md                   # This file
├── LICENSE                     # MIT License
├── CONTRIBUTING.md             # Contribution guidelines
├── CHANGELOG.md                # Version history
├── setup.sh                    # Main orchestrator
├── arasul_tui/
│   ├── app.py                  # TUI application (slash-command interface)
│   ├── commands.py             # Slash-command handlers
│   ├── install.sh              # Installer for `arasul` launcher
│   └── core/                   # Router, State, Registry, Auth, Browser, UI
├── tests/                      # Pytest test suite
├── scripts/
│   ├── 01-system-optimize.sh   # Disable GUI, minimize services, tune kernel
│   ├── 02-network-setup.sh     # Hostname, mDNS (Avahi), optional Tailscale
│   ├── 03-ssh-harden.sh        # Key-only auth, fail2ban, SSH hardening
│   ├── 04-nvme-setup.sh        # Partition NVMe, mount, swap, directories
│   ├── 05-docker-setup.sh      # Docker + NVIDIA Runtime, data on NVMe
│   ├── 06-devtools-setup.sh    # Node.js, Python, Git, Claude Code, jtop
│   ├── 07-quality-of-life.sh   # tmux, aliases, MOTD, power mode
│   └── 08-browser-setup.sh     # Playwright + headless Chromium
├── config/
│   ├── daemon.json.template    # Docker daemon template
│   ├── tmux.conf               # tmux configuration
│   ├── bash_aliases            # Shell aliases
│   └── mac-ssh-config          # SSH config template for Mac
└── agents/
    └── README.md               # Claude Code agent patterns
```

## Security & Performance

### Security

| Measure | Details |
|---------|---------|
| **SSH Key-Only Auth** | Password login disabled, Ed25519 public key only |
| **fail2ban** | 3 failed attempts → 1h ban, repeat offenders → 1 week ban (recidive) |
| **UFW Firewall** | Deny incoming (only SSH + mDNS allowed), allow outgoing |
| **Auto Security Updates** | Ubuntu `-security` patches, Docker/NVIDIA excluded |
| **Network Hardening** | SYN cookies, reverse-path filter, no redirects |

### Performance & Stability

| Measure | Details |
|---------|---------|
| **Kernel Tuning** | `vm.swappiness=10`, `vfs_cache_pressure=50`, `dirty_ratio=10`, 64MB `min_free_kbytes` |
| **OOM Protection** | SSH daemon and Docker protected from OOM killer (`OOMScoreAdjust`) |
| **NVMe Optimization** | `noatime` mount, `none` I/O scheduler, weekly TRIM (`fstrim.timer`) |
| **Journald Limit** | Max 200MB logs, 1 week retention, compressed |
| **Service Minimization** | ~39 running services (desktop, print, WiFi, PackageKit etc. disabled) |
| **Automated Maintenance** | Weekly NVMe health checks and Docker cleanup via cron |

## Troubleshooting

### Flash Issues

| Problem | Solution |
|---------|----------|
| SDK Manager doesn't detect Jetson | Check USB-C cable (data, not charge-only). Try different USB port directly on mainboard. `lsusb \| grep -i nvidia` must show NVIDIA. |
| NVMe not available as flash target | SSD physically installed correctly? Must be PCIe, not SATA SSD! Select "Manual Setup" in SDK Manager. |
| Flash aborts | Stable network? Enough storage on host (~30GB free)? Try again. |

### Boot Issues

| Problem | Solution |
|---------|----------|
| No video output after setup | Normal — headless mode. Use serial console or SSH. |
| Boot hangs | Check NVMe SSD contact. Connect serial console for boot logs. |
| Boots from SD instead of NVMe | Recovery Mode via Button Header Pins 9+10 (see Phase 2), flash to NVMe again. Remove SD card. |

### SSH Issues

| Problem | Solution |
|---------|----------|
| Connection refused | SSH service running? Check via serial console: `systemctl status sshd` |
| Permission denied (publickey) | Key not stored. Add manually via serial console (see Phase 5 troubleshooting box). |
| Locked out after SSH hardening | Connect USB-C from Ubuntu laptop, open serial console (`sudo screen /dev/ttyACM0 115200`), fix SSH config. |
| Firewall blocks connection | `sudo ufw status` to check. Port 22 must be allowed: `sudo ufw allow ssh` |
| `.local` hostname not working | mDNS/Avahi on Jetson: `systemctl status avahi-daemon`. On Mac: restart mDNS: `sudo killall -HUP mDNSResponder` |

### NVMe Issues

| Problem | Solution |
|---------|----------|
| SSD not detected (`lsblk`) | Properly installed? Must be PCIe NVMe, not SATA M.2! |
| Slow performance | `sudo nvme smart-log /dev/nvme0n1` for health check. Thermal throttling? Check `jtop`. |

### Docker Issues

| Problem | Solution |
|---------|----------|
| Daemon won't start | Check `journalctl -u docker`. `daemon.json` syntax correct? |
| GPU not available in container | `nvidia-container-toolkit` installed? `--runtime=nvidia` flag set? |
| Out of storage | `docker system prune -af --volumes` to clean up. |

### RAM Issues

| Problem | Solution |
|---------|----------|
| OOM (Out of Memory) | Check `free -h`. Start containers with memory limits (`--memory=2g`). SSH and Docker are OOM-protected. |
| Only 4–5GB free with 8GB | Normal — GPU reserves 1–2GB from shared RAM. |
| Process killed unexpectedly | OOM killer active? Check `dmesg \| grep -i oom`. SSH/Docker stay protected. |

## Maintenance

Most maintenance runs automatically (security updates, Docker cleanup, NVMe health checks, TRIM). For manual maintenance:

```bash
# System updates (automatic security patches already running)
sudo apt update && sudo apt upgrade -y

# Docker cleanup (also runs weekly via cron)
docker system prune -af --volumes

# NVMe health check (also runs weekly, log: /var/log/jetson-setup/nvme-health.log)
sudo nvme smart-log /dev/nvme0n1

# Clean up logs (journald is limited to 200MB)
sudo journalctl --vacuum-time=7d

# Check swap
swapon --show

# Firewall status
sudo ufw status verbose

# fail2ban status (banned IPs)
sudo fail2ban-client status sshd

# Count running services
systemctl list-units --type=service --state=running --no-pager | wc -l
```

## License

MIT — see [LICENSE](LICENSE) for details.
