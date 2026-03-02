# Jetson Dev Setup — Schritt-für-Schritt Anleitung

## Hardware-Checkliste

- [ ] Jetson Orin Nano Super Dev Kit
- [ ] NVMe M.2 2280 PCIe SSD (256GB–2TB)
- [ ] microSD-Karte 64GB+ (nur für Option B)
- [ ] Ethernet-Kabel
- [ ] USB-C Kabel (für serielle Konsole)
- [ ] 19V Netzteil (mitgeliefert)
- [ ] Mac/PC mit SSH-Client

## Phase 1: Hardware vorbereiten

1. **NVMe SSD einbauen**
   - Jetson ausschalten und Netzteil trennen
   - SSD in den M.2 Slot an der Unterseite einsetzen
   - Mit Schraube fixieren

2. **Verkabelung**
   - Ethernet-Kabel anschließen (zum Router/Switch)
   - USB-C Kabel zum Mac (für serielle Konsole beim Erststart)
   - 19V Netzteil einstecken (zuletzt!)

## Phase 2: JetPack flashen

### Option A: NVMe-Boot (empfohlen)

Voraussetzung: Ubuntu 20.04/22.04 x86-Host mit NVIDIA SDK Manager.

1. SDK Manager installieren: https://developer.nvidia.com/sdk-manager
2. Jetson im Recovery-Modus verbinden (USB-C)
3. JetPack 6.2.2 auswählen und auf NVMe flashen
4. oem-config über serielle Konsole abschließen

### Option B: SD-Karte

1. JetPack 6.2.2 Image herunterladen:
   https://developer.nvidia.com/embedded/jetpack
2. Mit balenaEtcher auf SD-Karte flashen
3. SD-Karte einlegen, booten
4. oem-config über serielle Konsole abschließen:
   ```bash
   screen /dev/tty.usbmodem* 115200
   ```

## Phase 3: Automatisiertes Setup

```bash
# 1. SSH-Key kopieren
ssh-copy-id -i ~/.ssh/id_ed25519.pub BENUTZER@192.168.55.1

# 2. Verbinden
ssh BENUTZER@192.168.55.1

# 3. Setup-Repo klonen
git clone https://github.com/koljaschoepe/jetson-dev-setup.git
cd jetson-dev-setup

# 4. Konfigurieren und ausführen
sudo ./setup.sh --interactive
# ODER:
cp .env.example .env
nano .env
sudo ./setup.sh
```

## Phase 4: Mac SSH-Config einrichten

```bash
# Auf dem Mac:
mkdir -p ~/.ssh/sockets

# Zur ~/.ssh/config hinzufügen:
Host jetson
    HostName jetson.local
    User BENUTZER
    IdentityFile ~/.ssh/id_ed25519
    ControlMaster auto
    ControlPersist 600
    ControlPath ~/.ssh/sockets/%r@%h-%p
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

## Phase 5: Täglicher Workflow

```bash
# Verbinden
ssh jetson

# tmux-Session starten/fortsetzen
t

# Projekt öffnen
p                           # → ~/projects
cd mein-projekt

# Claude Code starten
claude

# Jetson-Status prüfen
jtop
```

## Troubleshooting

### Boot-Probleme
- **Kein Video-Ausgang**: Normal im Headless-Modus. Serielle Konsole nutzen.
- **Boot hängt**: SD-Karte / NVMe Kontakt prüfen. Firmware-Update nötig?

### SSH-Probleme
- **Connection refused**: SSH-Dienst läuft? `systemctl status sshd`
- **Permission denied**: Key kopiert? `ssh-copy-id` erneut ausführen
- **Ausgesperrt**: Über serielle Konsole verbinden, SSH-Config reparieren

### NVMe-Probleme
- **Nicht erkannt**: `lsblk` prüfen. SSD richtig eingesetzt? PCIe, nicht SATA!
- **Langsam**: `sudo nvme smart-log /dev/nvme0n1` für Health-Check

### Docker-Probleme
- **Daemon startet nicht**: `journalctl -u docker` prüfen. daemon.json Syntax?
- **GPU nicht verfügbar**: `nvidia-container-toolkit` installiert?
- **Kein Speicher**: `docker system prune -af --volumes`

### RAM-Probleme
- **OOM (Out of Memory)**: Swap prüfen (`free -h`), Container-Limits setzen
- **Nur 4-5GB frei**: Normal — GPU reserviert 1-2GB vom geteilten RAM

## Wartung

```bash
# System-Updates (manuell, kein Auto-Update auf Edge-Devices)
sudo apt update && sudo apt upgrade -y

# Docker aufräumen
docker system prune -af --volumes

# NVMe-Health prüfen
sudo nvme smart-log /dev/nvme0n1

# Logs aufräumen
sudo journalctl --vacuum-time=7d
```
