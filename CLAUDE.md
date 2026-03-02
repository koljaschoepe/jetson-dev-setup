# Jetson Dev Setup — Claude Code Kontext

## Was ist dieses Repo?
Automatisierte Setup-Scripts um ein frisches NVIDIA Jetson Orin Nano Super Dev Kit (8GB) in einen Headless Development Server umzuwandeln. Optimiert für Remote-Entwicklung via SSH + Claude Code. Wird verwendet um Jetson-Geräte für Kunden einheitlich vorzubereiten.

## Hardware-Kontext
- **Gerät:** NVIDIA Jetson Orin Nano Super Developer Kit (2025)
- **SoC:** Orin (6× Arm Cortex-A78AE @ 1.7GHz, 1024 CUDA Cores Ampere GPU)
- **RAM:** 8GB LPDDR5 **geteilt** zwischen CPU und GPU
- **OS:** JetPack 6.2.2 (Ubuntu 22.04, Jetson Linux 36.5, Kernel 5.15, CUDA 12.6)
- **Arch:** aarch64 / ARM64
- **Speicher:** NVMe M.2 2280 SSD (Primärspeicher)
- **Netzwerk:** Gigabit Ethernet

## Schlüssel-Einschränkungen
- Nur 8GB RAM geteilt CPU/GPU — kein Desktop, Services minimieren
- ARM64 — nicht alle x86-Pakete/Container verfügbar
- Docker-Images müssen `linux/arm64` oder multi-arch sein
- NVMe ist Pflicht für Docker/Swap (SD-Karte zu langsam)
- NVIDIA Container Runtime vorinstalliert — `--runtime=nvidia` für GPU

## Sicherheits-Konfiguration
- SSH: Key-Only Auth (`/etc/ssh/sshd_config.d/99-jetson-hardened.conf`)
- Firewall: UFW aktiv, nur SSH (22) + mDNS (5353) erlaubt
- fail2ban: sshd-Jail + recidive-Jail (Wiederholungstäter 1 Woche Ban)
- Automatische Security-Patches via `unattended-upgrades` (Docker/NVIDIA ausgenommen)
- Netzwerk-Hardening: SYN-Cookies, Reverse-Path-Filter, keine Redirects

## Performance-Tuning
- Kernel: `vm.swappiness=10`, `vfs_cache_pressure=50`, `dirty_ratio=10`, `min_free_kbytes=65536`
- OOM-Schutz: SSH (`OOMScoreAdjust=-900`), Docker (`-500`)
- NVMe: `noatime`-Mount, `none` I/O-Scheduler, wöchentlich TRIM
- Journald: 200MB Limit, 1 Woche Retention
- ~39 laufende Services (Desktop/WiFi/Print deaktiviert)

## Konfiguration
Alle kundenspezifischen Variablen stehen in `.env` (erstellt aus `.env.example`).
Scripts lesen Variablen über exportierte Umgebungsvariablen von `setup.sh`.

## Repo-Struktur
```
├── .env.example           # Konfigurations-Vorlage
├── CLAUDE.md              # Diese Datei
├── README.md              # Setup-Anleitung
├── setup.sh               # Hauptorchestrator (sourced .env)
├── scripts/
│   ├── 01-system-optimize.sh  # GUI deaktivieren, Services, Kernel tunen
│   ├── 02-network-setup.sh    # Hostname, mDNS, optional Tailscale
│   ├── 03-ssh-harden.sh       # Key-Only Auth, fail2ban
│   ├── 04-nvme-setup.sh       # Partition, Format, Mount, Swap
│   ├── 05-docker-setup.sh     # Docker, NVIDIA Runtime, Compose
│   ├── 06-devtools-setup.sh   # Node.js, Python, Git, Claude Code
│   └── 07-quality-of-life.sh  # tmux, Aliases, MOTD
├── config/
│   ├── daemon.json.template   # Docker-Daemon Vorlage
│   ├── tmux.conf              # tmux-Konfiguration
│   ├── bash_aliases           # Shell-Aliases
│   └── mac-ssh-config         # SSH-Config-Template für Mac
└── agents/
    └── README.md              # Claude Code Agent-Patterns
```

## Script-Konventionen
- Alle Scripts sind idempotent — mehrfach ausführbar
- Scripts prüfen Voraussetzungen und überspringen erledigte Schritte
- Jedes Script kann einzeln oder via `setup.sh` ausgeführt werden
- Logs unter `/var/log/jetson-setup/`
- Exit-Codes: 0=Erfolg, 1=Fehler, 2=Übersprungen

## Typische Befehle auf dem Gerät
```bash
# Systemüberwachung
jtop                          # Jetson Dashboard (GPU, RAM, Temp)
sudo tegrastats               # Einzeilige System-Stats
sudo nvpmodel -q              # Aktueller Power-Mode
sudo jetson_clocks --show     # Aktuelle Taktfrequenzen

# Docker
docker ps                     # Laufende Container
docker system df              # Speicherverbrauch
docker compose up -d          # Stack starten

# Power
sudo nvpmodel -m 0            # 15W Standard
sudo nvpmodel -m 2            # 25W Super-Modus
sudo jetson_clocks            # Clocks auf Maximum

# Speicher
df -h /mnt/nvme               # NVMe freier Speicher
sudo nvme smart-log /dev/nvme0n1  # NVMe Health
free -h                       # RAM + Swap

# Sicherheit
sudo ufw status verbose       # Firewall-Status
sudo fail2ban-client status sshd  # Gebannte IPs
sudo unattended-upgrades --dry-run  # Ausstehende Security-Patches
```

## Entwicklungs-Workflow
1. SSH vom Mac: `ssh jetson`
2. tmux Session: `t` (Alias)
3. Projekt: `cd ~/projects/<projekt>`
4. Claude Code: `claude`

## Wichtige Pfade
- `/mnt/nvme/projects/` — Alle Projekte
- `/mnt/nvme/docker/` — Docker Data Root
- `/mnt/nvme/models/` — AI-Modelle (Ollama etc.)
- `/mnt/nvme/backups/` — Backups
- `/var/log/jetson-setup/` — Setup-Logs
- `/var/log/jetson-setup/nvme-health.log` — Wöchentliche NVMe SMART-Daten
- `/etc/ssh/sshd_config.d/99-jetson-hardened.conf` — SSH-Härtung
- `/etc/sysctl.d/99-jetson-dev.conf` — Kernel-Parameter
- `/etc/cron.weekly/nvme-health` — NVMe-Health-Check Cron
- `/etc/cron.weekly/docker-cleanup` — Docker-Cleanup Cron

## ARM64-Besonderheiten
- `docker buildx` für Multi-Arch-Builds
- npm-Pakete mit nativen Addons brauchen `build-essential` + `python3`
- PyTorch für Jetson: NVIDIA-Wheels, nicht PyPI
- CUDA unter `/usr/local/cuda-12.6/`, bereits im PATH
