# Arasul v0.5.0 — Multi-Platform Support

Transform Arasul from a Jetson-only tool into a universal Linux SBC development server setup. Auto-detect hardware, adapt the TUI dashboard, and run setup scripts on any supported platform.

**Existing Jetson behavior is preserved.** All current features continue to work. New platforms get the same experience, adapted to their hardware.

---

## Supported Platforms (Launch)

| Platform | Models | Arch | GPU | Min RAM |
|----------|--------|------|-----|---------|
| **NVIDIA Jetson** | Orin Nano/NX/AGX, Xavier, TX2 | aarch64 | CUDA (NVIDIA) | 4 GB |
| **Raspberry Pi** | Pi 4 Model B, Pi 5 | aarch64 (64-bit OS required) | None (VideoCore ignored) | 4 GB |

Future expansion to other ARM64 SBCs (Orange Pi, Rock Pi) and x86_64 servers is possible but not in scope for v0.5.0.

---

## Design Principles

1. **Detect, Don't Assume** — Hardware is detected automatically; no hardcoded platform checks that block other devices
2. **Graceful Degradation** — Features unavailable on a platform are silently hidden, not shown as errors
3. **Hybrid Detection** — Static info (device, SoC) cached at install; dynamic info (RAM, temp, disk) read at runtime
4. **Storage Auto-Detect** — Best available storage used automatically: NVMe > USB-SSD > SD card
5. **Interactive Wizard** — Setup asks what to install after detecting hardware, instead of running everything blindly
6. **One Codebase** — No forks; platform-specific logic lives in detection layer + thin conditionals

---

## Current State Analysis

### What's Already Generic (No Changes Needed)

| Component | Why It Works Everywhere |
|-----------|------------------------|
| `lib/common.sh` | Pure utility functions (logging, apt, user management) — 100% portable |
| `03-ssh-harden.sh` | Standard SSH + fail2ban config — works on any Linux |
| `02-network-setup.sh` | UFW + mDNS + hostname — ~95% generic |
| Arasul TUI core | Rich + prompt_toolkit — pure Python, no platform deps |
| Project registry | YAML-based CRUD — filesystem only |
| Git operations | Standard git commands |
| Claude Code integration | npm-based, works on ARM64 |

### What Needs Abstraction

| Component | Jetson-Specific Code | Impact |
|-----------|---------------------|--------|
| `setup.sh` | `check_jetson()` exits on non-Jetson | **Blocks all other platforms** |
| `.env.example` | `JETSON_USER`, `JETSON_HOSTNAME`, `NVME_DEVICE`, `POWER_MODE` | Config assumes Jetson |
| `04-nvme-setup.sh` | Hardcoded NVMe device paths, partition naming | **Breaks on USB-SSD/SD** |
| `05-docker-setup.sh` | `nvidia-container-toolkit` installed unconditionally | **Breaks Docker on non-NVIDIA** |
| `07-quality-of-life.sh` | `nvpmodel`, `tegrastats`, `jetson_clocks` aliases | Commands don't exist on RPi |
| `01-system-optimize.sh` | `nvargus-daemon` disable, `nvme-cli` install | Harmless but unnecessary on RPi |
| TUI Dashboard | `nvpmodel -q`, `/sys/devices/gpu.0/load` | Shows errors/n/a on RPi |
| TUI Paths | `/mnt/nvme` hardcoded in 15+ files | Breaks if no NVMe mounted |
| Templates | CLAUDE.md references Jetson hardware | Misleading on RPi |
| Config files | Named `99-jetson-*.conf` | Cosmetic but confusing |
| `bash_aliases` | `gpu`, `powermode`, `maxperf` aliases | Fail silently on RPi |

---

## Architecture: Hardware Abstraction Layer

### Shell Layer: `lib/detect.sh`

New shared library sourced by all setup scripts. Provides platform detection functions:

```bash
# Detection functions
detect_platform()        # Returns: "jetson" | "raspberry_pi" | "generic"
detect_model()           # Returns: "Orin Nano Super" | "Raspberry Pi 5 Model B" | ...
detect_arch()            # Returns: "aarch64" | "x86_64"
detect_gpu_type()        # Returns: "nvidia" | "videocore" | "none"
detect_ram_mb()          # Returns: RAM in MB (e.g., 8192)

# Storage detection (finds best available)
detect_storage_device()  # Returns: "/dev/nvme0n1" | "/dev/sda" | ""
detect_storage_type()    # Returns: "nvme" | "usb_ssd" | "sd_only"
detect_storage_mount()   # Returns: "/mnt/data" (auto-determined)

# Feature availability
has_nvidia_gpu()         # Returns: 0 (true) or 1 (false)
has_nvme()               # Returns: 0 or 1
has_docker()             # Returns: 0 or 1
```

**Detection strategy:**

```bash
detect_platform() {
    # 1. Jetson: check Tegra release file or L4T package
    [ -f /etc/nv_tegra_release ] && echo "jetson" && return
    dpkg -l nvidia-l4t-core &>/dev/null && echo "jetson" && return
    grep -qi "tegra" /proc/device-tree/compatible 2>/dev/null && echo "jetson" && return

    # 2. Raspberry Pi: check device tree model
    grep -qi "raspberry pi" /proc/device-tree/model 2>/dev/null && echo "raspberry_pi" && return

    # 3. Fallback: generic Linux
    echo "generic"
}

detect_storage_device() {
    # Priority: NVMe > USB SSD > none (use root filesystem)
    if lsblk -dno NAME,TRAN 2>/dev/null | grep -q "nvme"; then
        lsblk -dno PATH,TRAN | awk '$2=="nvme"{print $1; exit}'
    elif lsblk -dno NAME,TRAN 2>/dev/null | grep -q "usb"; then
        lsblk -dno PATH,TRAN,TYPE | awk '$2=="usb" && $3=="disk"{print $1; exit}'
    fi
    # Returns empty if only SD/eMMC (root filesystem)
}
```

### Python Layer: `arasul_tui/core/platform.py`

Singleton platform info object, initialized once at TUI startup:

```python
@dataclass
class GpuInfo:
    type: str           # "nvidia" | "videocore" | "none"
    model: str          # "1024-core Ampere" | "VideoCore VII" | ""
    has_cuda: bool
    cuda_version: str   # "12.6" | ""

@dataclass
class StorageInfo:
    type: str           # "nvme" | "usb_ssd" | "sd_only"
    mount: Path         # /mnt/data | /home
    device: str         # "/dev/nvme0n1" | "/dev/sda" | ""
    total_gb: float
    free_gb: float

@dataclass
class Platform:
    name: str           # "jetson" | "raspberry_pi" | "generic"
    model: str          # "NVIDIA Jetson Orin Nano Super" | "Raspberry Pi 5 Model B"
    arch: str           # "aarch64" | "x86_64"
    ram_mb: int
    gpu: GpuInfo
    storage: StorageInfo
    has_docker: bool
    has_nvidia_runtime: bool

    # Computed properties
    @property
    def project_root(self) -> Path:
        return self.storage.mount / "projects"

    @property
    def is_jetson(self) -> bool:
        return self.name == "jetson"

    @property
    def is_raspberry_pi(self) -> bool:
        return self.name == "raspberry_pi"
```

**Usage across TUI (replaces all hardcoded paths):**

```python
# Before (hardcoded):
DEFAULT_PROJECT_ROOT = Path("/mnt/nvme/projects")
NVME_BROWSER_CACHE = Path("/mnt/nvme/playwright-browsers")

# After (platform-aware):
platform = get_platform()
DEFAULT_PROJECT_ROOT = platform.project_root
BROWSER_CACHE = platform.storage.mount / "playwright-browsers"
```

---

## Implementation Plan

### Phase 1: Detection Layer (`lib/detect.sh` + `core/platform.py`)

**No existing behavior changes. Pure additions.**

- [ ] Create `lib/detect.sh` with all detection functions
  - `detect_platform()` — Jetson, Raspberry Pi, generic
  - `detect_model()` — Full model string from `/proc/device-tree/model`
  - `detect_arch()` — `uname -m`
  - `detect_gpu_type()` — NVIDIA check via nvidia-smi/tegra, else none
  - `detect_storage_device()` — Best storage: NVMe > USB-SSD > root
  - `detect_storage_type()` — Classify the detected storage
  - `detect_ram_mb()` — From `/proc/meminfo`
  - `has_nvidia_gpu()`, `has_nvme()`, `has_docker()` — Boolean helpers
- [ ] Create `arasul_tui/core/platform.py`
  - `Platform` dataclass with all hardware info
  - `GpuInfo` and `StorageInfo` sub-dataclasses
  - `detect()` function that populates Platform from system queries
  - `get_platform()` singleton accessor (cached after first call)
  - Cache static info to `~/.arasul/platform.json` at install time
  - Dynamic info (RAM usage, temp, disk free) refreshed at runtime
- [ ] Unit tests for detection logic (mock `/proc/device-tree/model`, etc.)

### Phase 2: Generic Configuration (`.env` + `setup.sh`)

**Rename Jetson-specific variables. `setup.sh` accepts all platforms.**

- [ ] Rename `.env.example` variables:
  - `JETSON_USER` -> `DEVICE_USER`
  - `JETSON_HOSTNAME` -> `DEVICE_HOSTNAME`
  - `NVME_DEVICE` -> `STORAGE_DEVICE` (auto-detected if empty)
  - `NVME_MOUNT` -> `STORAGE_MOUNT` (auto-determined if empty)
  - `POWER_MODE` -> `POWER_MODE` (only used on Jetson, ignored elsewhere)
  - Add: `PLATFORM` (auto-detected, can be overridden)
- [ ] Refactor `setup.sh`:
  - Replace `check_jetson()` with `detect_platform()` (from `lib/detect.sh`)
  - Remove the `exit 1` on non-Jetson — accept all platforms
  - Auto-detect `STORAGE_DEVICE` and `STORAGE_MOUNT` if not set in `.env`
  - Export `PLATFORM` variable for all scripts to use
  - Source `lib/detect.sh` alongside `lib/common.sh`
- [ ] Backward compatibility: existing `.env` files with `JETSON_*` vars still work
  - Map old var names to new ones if detected

### Phase 3: Interactive Setup Wizard

**`setup.sh --interactive` (default for new installs).**

```
$ sudo ./setup.sh

  Hardware detected:
     Device:  Raspberry Pi 5 Model B (8GB)
     Arch:    aarch64
     Storage: NVMe (PCIe, 256GB) + microSD (32GB)
     GPU:     None (VideoCore VII, no CUDA)

  What would you like to set up?
     [x] System optimization (disable desktop, tune kernel)
     [x] SSH hardening (key-only auth, fail2ban)
     [x] Storage setup (NVMe as primary, swap)
     [x] Docker + Compose
     [x] Dev tools (Node.js 22, Python 3, Git)
     [x] Claude Code
     [ ] Headless browser (Playwright + Chromium)
     [x] Quality of life (tmux, aliases, prompt)

     Press Enter to start, or edit selection...
```

- [ ] Add `--interactive` flag to `setup.sh` (default)
- [ ] Add `--auto` flag to preserve old "run everything" behavior
- [ ] Wizard uses `whiptail` or `dialog` for TUI selection (available on all Debian)
- [ ] Pre-select steps based on detected hardware:
  - Jetson: all steps pre-selected (including GPU-specific)
  - RPi: browser deselected by default (RAM concern on 4GB)
  - Generic: storage setup deselected if no external drive detected
- [ ] Save selections to `~/.arasul/setup-state.json` for re-runs

### Phase 4: Storage Abstraction (`04-storage-setup.sh`)

**Rename `04-nvme-setup.sh` -> `04-storage-setup.sh`. Support NVMe, USB-SSD, SD-only.**

- [ ] Rename script and update references
- [ ] Use `detect_storage_device()` to find best storage
- [ ] Three storage modes:
  - **NVMe**: Partition, format, mount to `/mnt/data` (Jetson + Pi 5 with HAT+)
  - **USB-SSD**: Format, mount to `/mnt/data` (Pi 4 common setup)
  - **SD-only**: Skip mount, use `/home/$USER` for projects (minimal setup)
- [ ] Rename mount point: `/mnt/nvme` -> `/mnt/data` (generic name)
  - Backward compat: symlink `/mnt/nvme` -> `/mnt/data` if old path was used
- [ ] Adjust I/O scheduler per storage type:
  - NVMe: `none` (no scheduling needed)
  - USB-SSD: `mq-deadline`
  - SD: `bfq` (best for flash)
- [ ] TRIM only for NVMe and SSDs that support it
- [ ] Swap sizing based on detected RAM:
  - 4 GB RAM: 8 GB swap
  - 8 GB RAM: 16 GB swap (or `SWAP_SIZE` from .env)

### Phase 5: Platform-Conditional Scripts

**Each script checks `$PLATFORM` and adapts.**

- [ ] `01-system-optimize.sh`:
  - `nvargus-daemon` disable: only on Jetson
  - `nvme-cli` install: only if NVMe detected
  - Config filename: `99-arasul-system.conf` (rename from `99-jetson-dev.conf`)
- [ ] `05-docker-setup.sh`:
  - `nvidia-container-toolkit`: only if `has_nvidia_gpu()`
  - `daemon.json`: NVIDIA runtime section only on Jetson
  - Docker version warning (28.x kernel issue): only on Jetson
  - Data root: use `$STORAGE_MOUNT/docker` (not hardcoded `/mnt/nvme/docker`)
- [ ] `06-devtools-setup.sh`:
  - Claude Code: use `npm install -g` method (works on both platforms)
  - Node.js: NodeSource repo (ARM64 supported for both)
- [ ] `07-quality-of-life.sh`:
  - Power mode (`nvpmodel`): only on Jetson
  - Prompt function: rename `__jetson_ps1` -> `__arasul_ps1`
  - Config filename: `99-arasul-limits.conf` (rename from `99-jetson-dev.conf`)
- [ ] `08-browser-setup.sh`:
  - Playwright cache path: use `$STORAGE_MOUNT/playwright-browsers`
  - Works on both platforms (Playwright supports ARM64)
- [ ] Platform-specific aliases in `config/`:
  - `config/aliases/common` — shared aliases (docker, git, tmux, arasul)
  - `config/aliases/jetson` — `gpu`, `powermode`, `maxperf`, `tegrastats`
  - `config/aliases/raspberry_pi` — `vcgencmd`, `pinout`, `raspi-config`
  - `bash_aliases` assembled from common + platform-specific at install

### Phase 6: TUI Dashboard — Platform-Adaptive

**Dashboard shows hardware-relevant metrics per platform.**

- [ ] Refactor `core/ui/dashboard.py`:
  - Import `get_platform()` from `core/platform.py`
  - Replace hardcoded shell commands with platform-conditional queries
- [ ] Jetson dashboard (existing, preserved):
  - Power Mode, GPU %, Temperature, NVMe disk usage
- [ ] Raspberry Pi dashboard (new):
  - CPU Temperature (`vcgencmd measure_temp` or thermal zone)
  - CPU Frequency (`vcgencmd measure_clock arm`)
  - Throttle Status (`vcgencmd get_throttled` — voltage/temp warnings)
  - Storage disk usage (auto-detected mount)
- [ ] Generic dashboard (fallback):
  - CPU usage, RAM, Disk, Temperature (if thermal zone exists)
- [ ] Update `commands/system.py`:
  - `/status`: show platform-appropriate metrics
  - `/health`: NVMe SMART only if NVMe present; SD health if SD-only

### Phase 7: TUI Path Abstraction

**Replace all hardcoded `/mnt/nvme` references with `platform.storage.mount`.**

- [ ] `core/state.py`: `DEFAULT_PROJECT_ROOT` from platform
- [ ] `core/templates.py`: `NVME_BASE` -> `platform.storage.mount`
- [ ] `core/browser.py`: `NVME_BROWSER_CACHE` -> `platform.storage.mount / "playwright-browsers"`
- [ ] `core/n8n_client.py`: `N8N_DIR` -> `platform.storage.mount / "n8n"`
- [ ] `core/n8n_mcp.py`: n8n paths from platform
- [ ] `core/security.py`: backup paths from platform
- [ ] `core/ui/dashboard.py`: disk usage query uses platform mount
- [ ] `commands/system.py`: health checks use platform storage device
- [ ] `commands/n8n_cmd.py`: directory checks use platform paths
- [ ] `core/setup_wizard.py`: config file paths renamed (`99-arasul-*`)

### Phase 8: Templates — Platform-Aware CLAUDE.md

**Generated CLAUDE.md files reflect actual hardware, not hardcoded Jetson specs.**

- [ ] Refactor `core/templates.py` `_CLAUDE_MD_HEADER`:
  - Use `get_platform()` to generate hardware context dynamically
  - Jetson: current content (CUDA, shared RAM, GPU cores)
  - RPi: CPU specs, no CUDA, storage type, RAM
  - Generic: basic Linux info
- [ ] Template availability per platform:
  - `python-gpu`: Jetson only (needs CUDA)
  - `vision`: Jetson only (needs CUDA for YOLO inference)
  - `api`: All platforms (FastAPI is CPU-only)
  - `notebook`: All platforms
  - `webapp`: All platforms
- [ ] Conda/Miniforge path: use `platform.storage.mount / "miniforge3"`
- [ ] Env paths: use `platform.storage.mount / "envs"`

### Phase 9: Aliases & Quality-of-Life

- [x] Split `config/bash_aliases` into:
  - `config/aliases/common` — works everywhere
  - `config/aliases/jetson` — NVIDIA tools
  - `config/aliases/raspberry_pi` — RPi tools
- [x] `07-quality-of-life.sh` assembles aliases from common + platform
- [x] Rename prompt function: `__jetson_ps1` -> `__arasul_ps1`
- [x] MOTD: show detected platform info on SSH login

### Phase 10: Testing & CI

- [x] Unit tests for `lib/detect.sh` (mock device-tree, cpuinfo)
- [x] Unit tests for `core/platform.py` (mock system calls)
- [x] Integration tests: verify TUI renders without Jetson hardware
- [x] CI matrix: test on `ubuntu-latest` (x86) as "generic" platform
- [x] CI: add `shellcheck` for `lib/detect.sh`
- [x] Update coverage threshold if needed
- [x] Test backward compat: old `.env` files still work

### Phase 11: Documentation & Repo Rename

- [x] Rename GitHub repo: `Jetson-Nano-SSH-Server-Setup` -> `arasul`
- [x] Update all internal references to old repo name
- [x] Rewrite `README.md`:
  - Multi-platform install instructions
  - Platform support matrix
  - Platform-specific notes (Jetson GPU, RPi storage)
- [x] Update `CLAUDE.md` with new architecture
- [x] Update `pyproject.toml` description and URLs
- [ ] GitHub: set up redirect from old repo name
- [x] Release notes for v0.5.0

---

## Feasibility: Research Findings

### Claude Code on Raspberry Pi

- **Works** via `npm install -g @anthropic-ai/claude-code` (native installer has known issues on ARM64)
- Requires 64-bit OS + Node.js v20+ (from NodeSource, not `pi-apps`)
- 4 GB RAM minimum; 8 GB recommended for comfortable dev workflow
- OAuth/auth on headless: same challenge Arasul already solves with `/auth`

### Playwright on Raspberry Pi

- **Officially supported** on ARM64 Linux (Ubuntu 22.04+, Debian 12+)
- 64-bit OS mandatory; armhf (32-bit) not supported
- Pi 5 (4 GB+) recommended; Pi 4 works but Chromium is memory-hungry
- Browser cache on NVMe/SSD translates directly to Pi 5 with M.2 HAT+

### Docker on Raspberry Pi

- **Fully supported** — same features as Jetson minus GPU runtime
- Docker Compose V2 available as `docker-compose-plugin`
- BuildX works for multi-arch builds
- No `nvidia-container-toolkit` — GPU pass-through not possible

### Storage on Raspberry Pi

- **Pi 5**: Native PCIe via M.2 HAT+ — NVMe SSDs work like on Jetson
- **Pi 4**: USB 3.0 SSD via adapter — good performance, widely used
- **Both**: microSD as boot device, external storage for data
- Storage detection via `lsblk` works across all Linux platforms

### Hardware Detection

- `/proc/device-tree/model` — reliable on both Jetson and RPi
- `vcgencmd` — RPi-specific, equivalent to Jetson's `tegrastats`
- `psutil` Python package — cross-platform CPU/RAM/disk metrics
- Thermal zones at `/sys/class/thermal/` — work on both platforms (different zone numbers)

---

## Migration Path

### For Existing Jetson Users

- Existing `.env` files with `JETSON_*` variables continue to work (mapped to new names)
- `/mnt/nvme` paths continue to work (symlinked to `/mnt/data` if renamed)
- All current commands and workflows unchanged
- Dashboard shows same Jetson metrics as before

### For New Raspberry Pi Users

```bash
# 1. Clone and configure
git clone https://github.com/<user>/arasul.git
cd arasul
cp .env.example .env
nano .env  # Set DEVICE_USER, DEVICE_HOSTNAME

# 2. Run setup (interactive wizard)
sudo ./setup.sh

# 3. Start TUI
arasul
```

---

## Resource Budget

### Raspberry Pi 5 (8 GB)

| Component | RAM Usage | Notes |
|-----------|-----------|-------|
| OS + services | ~500 MB | Headless Raspberry Pi OS Lite |
| Docker daemon | ~200 MB | Standard runtime (no NVIDIA) |
| Arasul TUI | ~30 MB | Python process |
| Claude Code | ~100 MB | Node.js process |
| Playwright/Chromium | ~300 MB | Only when browser active |
| **Available for work** | **~6.8 GB** | More headroom than Jetson (no GPU sharing) |

### Raspberry Pi 4 (4 GB)

| Component | RAM Usage | Notes |
|-----------|-----------|-------|
| OS + services | ~400 MB | Headless |
| Docker daemon | ~200 MB | |
| Arasul TUI | ~30 MB | |
| Claude Code | ~100 MB | |
| **Available for work** | **~3.2 GB** | Tight — avoid Playwright, limit Docker containers |

---

## Example Flows

### Setup on Raspberry Pi 5

```
$ sudo ./setup.sh

  Hardware detected:
     Device:  Raspberry Pi 5 Model B Rev 1.0
     RAM:     8 GB
     Arch:    aarch64
     Storage: NVMe 256GB (PCIe) + microSD 32GB (boot)
     GPU:     VideoCore VII (no CUDA)

  Recommended setup for Raspberry Pi 5:
     [x] System optimization
     [x] SSH hardening
     [x] Storage setup (NVMe as /mnt/data)
     [x] Docker + Compose
     [x] Dev tools (Node.js 22, Python 3)
     [x] Claude Code (npm install)
     [ ] Headless browser (Playwright)
     [x] Quality of life (tmux, aliases)

  Press Enter to start...

  [1/7] System optimization.............. done
  [2/7] SSH hardening.................... done
  [3/7] Storage setup (NVMe)............. done
  [4/7] Docker + Compose................. done
  [5/7] Dev tools........................ done
  [6/7] Claude Code...................... done
  [7/7] Quality of life.................. done

  Setup complete! Reboot recommended.
  After reboot: ssh pi5.local, then run 'arasul'
```

### TUI Dashboard on Raspberry Pi

```
  ╔══════════════════════════════════════════════╗
  ║  ARASUL  v0.5.0                              ║
  ║  Raspberry Pi 5 Model B  ·  8 GB RAM         ║
  ╠══════════════════════════════════════════════╣
  ║  CPU: 48°C   Disk: 124G/256G   RAM: 1.2G/8G  ║
  ║  Docker: 3 containers   Claude: authenticated ║
  ╚══════════════════════════════════════════════╝

  Projects:
    1. my-api          ~/projects/my-api
    2. data-pipeline   ~/projects/data-pipeline

  > /
```

### TUI Dashboard on Jetson (unchanged)

```
  ╔══════════════════════════════════════════════╗
  ║  ARASUL  v0.5.0                              ║
  ║  Jetson Orin Nano Super  ·  25W  ·  8 GB      ║
  ╠══════════════════════════════════════════════╣
  ║  GPU: 12%  CPU: 45°C  Disk: 89G/256G  RAM: 2G ║
  ║  Docker: 5 containers   Claude: authenticated  ║
  ╚══════════════════════════════════════════════╝
```

---

## Technical Notes

- All detection uses standard Linux interfaces (`/proc`, `/sys`, `lsblk`, `uname`)
- No additional Python dependencies needed — `platform`, `os`, `subprocess` are stdlib
- `psutil` is already a dependency (used in tests) — available for enhanced metrics
- Storage mount point standardized to `/mnt/data` (new installs); `/mnt/nvme` preserved via symlink for existing
- Config files renamed: `99-jetson-*` -> `99-arasul-*` (existing files left in place, not deleted)
- `.env` backward compat: script checks for both `JETSON_USER` and `DEVICE_USER`
- RPi thermal: `/sys/class/thermal/thermal_zone0/temp` works (same interface as Jetson)
- RPi-specific: `vcgencmd` for throttle detection, clock speeds (gracefully skipped if unavailable)
