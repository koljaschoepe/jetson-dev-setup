# jetson-dev-setup

> Automatisiertes Setup-Tool für NVIDIA Jetson Orin Nano Super als Headless Development Server. Optimiert für SSH + Claude Code Workflows.

Dieses Tool wird verwendet, um Jetson Orin Nano Super Geräte für Kunden und Projekte einheitlich und reproduzierbar vorzubereiten.

## Voraussetzungen

### Hardware

| Komponente | Empfohlen |
|-----------|-----------|
| Jetson Orin Nano Super Dev Kit | 8GB, JetPack 6.2+ |
| NVMe SSD | M.2 2280 PCIe, 512GB–2TB |
| microSD | 64GB+ UHS-I (falls nicht NVMe-Boot) |
| Netzteil | Mitgeliefertes 19V DC |
| Ethernet | Cat5e/Cat6, Gigabit |

### Ersteinrichtung (manuell)

Diese Schritte benötigen physischen Zugang und können nicht automatisiert werden:

**Option A: NVMe-Boot (empfohlen)**

1. NVIDIA SDK Manager auf einem Ubuntu 20.04/22.04 x86-Host installieren
2. Jetson per USB-C verbinden und JetPack 6.2+ direkt auf NVMe flashen
3. oem-config über serielle Konsole abschließen

**Option B: SD-Karte + NVMe als Datenspeicher**

1. JetPack 6.2+ SD-Image mit [balenaEtcher](https://balena.io/etcher) flashen
2. SD-Karte einlegen, Ethernet + USB-C + 19V anschließen
3. oem-config über serielle Konsole abschließen:
   ```bash
   screen /dev/tty.usbmodem* 115200
   ```

**Danach (beide Optionen):**

4. SSH-Key kopieren:
   ```bash
   ssh-copy-id -i ~/.ssh/id_ed25519.pub BENUTZER@192.168.55.1
   ```

## Quick Start

```bash
# Auf den Jetson verbinden
ssh BENUTZER@192.168.55.1

# Repo klonen
git clone https://github.com/koljaschoepe/jetson-dev-setup.git
cd jetson-dev-setup

# Konfiguration erstellen (interaktiv)
sudo ./setup.sh --interactive

# ODER: manuell konfigurieren
cp .env.example .env
nano .env
sudo ./setup.sh
```

## Was passiert?

| Schritt | Was wird gemacht | Dauer |
|---------|-----------------|-------|
| 1 | GUI deaktivieren, RAM optimieren, Kernel tunen | ~3 Min |
| 2 | Hostname setzen, mDNS aktivieren, optional Tailscale | ~1 Min |
| 3 | SSH härten (Key-Only, fail2ban) | ~1 Min |
| 4 | NVMe partitionieren, mounten, Swap, Verzeichnisse | ~2 Min |
| 5 | Docker + NVIDIA Runtime, Daten auf NVMe | ~2 Min |
| 6 | Node.js, Python, Git, Claude Code, jtop | ~5 Min |
| 7 | tmux, Aliases, Prompt, MOTD | ~1 Min |

**Gesamt: ~15 Minuten** von frischem JetPack zum fertigen Dev-Server.

## Konfiguration

Alle kundenspezifischen Einstellungen werden zentral in `.env` verwaltet:

```bash
# Pflichtfelder
CUSTOMER_NAME="Firma-XY"
JETSON_USER="arasul"
JETSON_HOSTNAME="jetson"

# Optionale Einstellungen
SWAP_SIZE="32G"
INSTALL_TAILSCALE="false"
INSTALL_CLAUDE="true"
INSTALL_OLLAMA="false"
NODE_VERSION="22"
POWER_MODE="3"          # 0=7W, 1=15W, 3=25W
```

Vollständige Vorlage: [`.env.example`](.env.example)

## Nach dem Setup

1. SSH-Config auf dem Mac einrichten (siehe `config/mac-ssh-config`)
2. Jetson neustarten: `sudo reboot`
3. Verbinden: `ssh jetson`
4. Arbeiten:
   ```bash
   t                          # tmux Session
   cd ~/projects/mein-projekt # Projekte auf NVMe
   claude                     # Claude Code starten
   ```

## Einzelne Schritte ausführen

```bash
sudo ./setup.sh --step 4    # Nur NVMe-Setup
sudo ./setup.sh --step 6    # Nur Dev-Tools
```

## Was du bekommst

```
~/projects/         → Symlink zu /mnt/nvme/projects/ (schneller NVMe-Speicher)
/mnt/nvme/          → NVMe-Mount mit projects/, docker/, models/, backups/
32GB Swap auf NVMe  → Genug Headroom für Docker + Entwicklung
Docker + NVIDIA     → GPU-Container, Daten auf NVMe
Node.js 22 + Claude → AI-unterstützte Entwicklung
tmux + Aliases      → Persistente Sessions, Shortcuts
SSH gehärtet        → Key-Only Auth, fail2ban, mDNS
Custom MOTD         → RAM/Disk/Temp beim Login
```

## Nützliche Aliases

| Alias | Befehl |
|-------|--------|
| `t` | tmux `dev` Session |
| `c` | Claude Code starten |
| `p` | `cd ~/projects` |
| `jtop` | Jetson Systemmonitor |
| `dps` | Docker Container (formatiert) |
| `powermode` | NVPower-Mode anzeigen |
| `maxperf` | 25W + Max Clocks |
| `ram` | RAM + Swap |
| `temps` | Temperatur-Sensoren |

## Repo-Struktur

```
├── .env.example           # Konfigurations-Vorlage (alle Variablen)
├── .gitignore
├── CLAUDE.md              # Kontext für Claude Code
├── README.md              # Diese Datei
├── setup.sh               # Hauptorchestrator
├── scripts/
│   ├── 01-system-optimize.sh
│   ├── 02-network-setup.sh
│   ├── 03-ssh-harden.sh
│   ├── 04-nvme-setup.sh
│   ├── 05-docker-setup.sh
│   ├── 06-devtools-setup.sh
│   └── 07-quality-of-life.sh
├── config/
│   ├── daemon.json.template   # Docker-Daemon Vorlage
│   ├── tmux.conf              # tmux-Konfiguration
│   ├── bash_aliases           # Shell-Aliases
│   └── mac-ssh-config         # SSH-Config für Mac
└── agents/
    └── README.md              # Claude Code Agent-Patterns
```

## Für neue Kunden-Geräte

```bash
# 1. Repo klonen (auf dem Jetson)
git clone https://github.com/koljaschoepe/jetson-dev-setup.git
cd jetson-dev-setup

# 2. Konfigurieren
sudo ./setup.sh --interactive

# 3. Fertig — SSH-Config an Kunden übergeben
cat config/mac-ssh-config
```

## Lizenz

MIT
