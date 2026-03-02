# jetson-dev-setup

> Automatisiertes Setup-Tool für NVIDIA Jetson Orin Nano Super als Headless Development Server. Optimiert für SSH + Claude Code Workflows.

---

## Komplette Schritt-für-Schritt Anleitung

Diese Anleitung führt dich vom ungeöffneten Karton zum fertigen, remote-erreichbaren Dev-Server. Wir flashen **direkt auf die NVMe SSD** — keine SD-Karte nötig.

### Zwei Rechner, klare Rollen

| Rechner | Rolle | Wann |
|---------|-------|------|
| **Ubuntu-Laptop** (x86_64) | Flashen, serielle Konsole, oem-config | Nur bei Ersteinrichtung (Phase 1–4) |
| **Mac** (dein Arbeitsrechner) | SSH-Zugang, tägliche Entwicklung | Ab Phase 5, danach dauerhaft |

Nach der Ersteinrichtung brauchst du den Ubuntu-Laptop **nie wieder** — der Jetson läuft headless und du arbeitest ausschließlich per SSH vom Mac.

### Was du brauchst

#### Hardware-Checkliste

| # | Komponente | Details | Woher |
|---|-----------|---------|-------|
| 1 | Jetson Orin Nano Super Dev Kit | 8GB LPDDR5 | NVIDIA / Distributor |
| 2 | NVMe M.2 2280 PCIe SSD | 256GB–2TB, z.B. Samsung 980 PRO, WD SN770 | Elektronikhandel |
| 3 | USB-C Kabel | Daten-fähig (nicht nur Ladekabel!) | Beigelegt oder separat |
| 4 | Ethernet-Kabel | Cat5e oder Cat6 | Standard |
| 5 | 19V DC Netzteil | Im Dev Kit enthalten | Beigelegt |
| 6 | Kreuzschraubendreher | Klein (Phillips #1), für SSD-Montage | Werkzeugkasten |
| 7 | **Büroklammer** (oder Pinzette) | Zum kurzzeitigen Verbinden von 2 Pins für den Recovery-Modus (siehe Phase 2) | Schreibtisch |

#### Software auf dem Ubuntu-Laptop (Flash-Host)

| # | Software | Installation |
|---|---------|-------------|
| 1 | **NVIDIA SDK Manager** (.deb) | Von [developer.nvidia.com/sdk-manager](https://developer.nvidia.com/sdk-manager) → **Download .deb (Ubuntu)** herunterladen |
| 2 | **screen** | `sudo apt install screen` (für serielle Konsole) |
| 3 | **NVIDIA Developer Account** | Kostenlos registrieren unter [developer.nvidia.com](https://developer.nvidia.com) |

> **Wichtig:** Der SDK Manager läuft **nur auf Ubuntu x86_64** (20.04 oder 22.04). Lade die **.deb-Variante** herunter, nicht das Docker-Image.

#### Software auf dem Mac (Arbeitsrechner)

| # | Software | Status |
|---|---------|--------|
| 1 | **SSH-Client** | Vorinstalliert auf macOS |
| 2 | **Homebrew** (optional) | Paketmanager für macOS — wird benötigt, falls du `screen` für die serielle Konsole nutzen willst |

**Homebrew installieren (falls noch nicht vorhanden):**

```bash
# Prüfen ob Homebrew bereits installiert ist
brew --version

# Falls nicht: Homebrew installieren
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

> Nach der Installation zeigt das Script die nötigen PATH-Befehle an. Typischerweise:
> ```bash
> echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
> eval "$(/opt/homebrew/bin/brew shellenv)"
> ```
> Danach Terminal neu starten oder den `eval`-Befehl ausführen.

---

### Phase 1: NVMe SSD einbauen

> **Wann:** Vor dem ersten Einschalten. Der Jetson ist aus, kein Kabel angeschlossen.

**Schritt 1.1 — Dev Kit aus der Verpackung nehmen**

Inhalt der Box prüfen:
- Jetson Orin Nano Super Modul (auf Carrier Board vormontiert)
- 19V DC Netzteil mit Kabel
- Quick Start Guide

**Schritt 1.2 — Carrier Board umdrehen**

- Lege das Board mit der Unterseite nach oben auf eine antistatische Unterlage
- Der M.2 Key-M Slot befindet sich auf der **Unterseite** des Carrier Boards
- Du erkennst ihn am langen Steckplatz mit einer Schraube daneben

**Schritt 1.3 — NVMe SSD einsetzen**

1. Entferne die Befestigungsschraube neben dem M.2 Slot (falls vorhanden)
2. Setze die NVMe SSD in einem **30°-Winkel** in den Slot ein (goldene Kontakte voran)
3. Drücke die SSD vorsichtig nach unten, bis sie flach aufliegt
4. Befestige sie mit der Schraube — **nicht zu fest anziehen!**

**Schritt 1.4 — Board wieder umdrehen**

- Carrier Board mit der Oberseite nach oben hinlegen
- Prüfe, dass das Jetson-Modul (der große grüne Chip mit Kühlkörper) fest sitzt

---

### Phase 2: Jetson in Recovery-Modus versetzen

> **Wann:** Direkt nach dem SSD-Einbau. Noch KEIN Netzteil anschließen.

#### Wichtig: Es gibt keine physischen Buttons!

Das Jetson Orin Nano Dev Kit hat **keine eingebauten Taster**. Stattdessen gibt es den **Button Header (J14)** — eine kleine 12-Pin-Leiste auf dem Carrier Board. Für den Recovery-Modus musst du nur **zwei Pins kurz mit einer Büroklammer verbinden** — das dauert 3 Sekunden.

**Was als "Jumper" funktioniert** (du brauchst kein spezielles Kabel):

| Haushaltsmittel | Anleitung |
|----------------|-----------|
| **Büroklammer** (empfohlen) | Aufbiegen, sodass zwei Enden parallel abstehen. Damit beide Pins gleichzeitig berühren. |
| **Pinzette** (Metall) | Metallspitzen auf die zwei Pins drücken. |
| **Abisoliertes Kabelende** | Ein kurzes Stück Draht, z.B. aus einem alten Ladekabel. |

> Die Pins haben nur **2,54 mm Abstand** — das ist sehr nah beieinander. Jedes Stück Metall, das zwei Pins gleichzeitig berührt, reicht.

#### Button Header (J14) finden

Der Header ist ein kleiner 12-Pin-Stecker auf dem Carrier Board. Suche nach der Beschriftung **J14** auf dem PCB (in der Nähe der Anschlüsse).

```
Button Header (J14) — Pin-Belegung:

     ┌──────────────────────────┐
     │  12  10   8   6   4   2  │
     │  11   9   7   5   3   1  │
     └──────────────────────────┘

  Pins 9+10 → Force Recovery Mode ← DAS BRAUCHST DU
  Pins 7+8  → Reset
  Pins 1+2  → Power On/Off
```

**Schritt 2.1 — USB-C Kabel verbinden**

- Stecke das **USB-C Kabel** in den **USB-C Port des Jetson** (neben den USB-A Ports)
- Das andere Ende kommt in den **Ubuntu-Laptop**
- Noch **kein Netzteil** anschließen!

**Schritt 2.2 — Recovery-Modus aktivieren (mit Büroklammer)**

Büroklammer aufbiegen und bereithalten. Dann **exakt in dieser Reihenfolge**:

1. **Büroklammer auf Pins 9 und 10** drücken — beide Pins gleichzeitig berühren und **halten**
2. **Während die Büroklammer die Pins verbindet:** Stecke das **19V Netzteil** ein
3. **Warte 2–3 Sekunden**
4. **Büroklammer entfernen**

Der Jetson startet jetzt **nicht** normal, sondern geht in den Recovery-Modus (kein Bildschirm-Output, kein Fan-Spin — das ist normal).

> **Gut zu wissen:** Falls der Jetson später bereits läuft und du erneut in den Recovery-Modus musst, geht das auch per Software:
> ```bash
> sudo reboot --force forced-recovery
> ```

**Schritt 2.3 — Recovery-Modus verifizieren**

Auf dem **Ubuntu-Laptop** im Terminal prüfen:

```bash
lsusb | grep -i nvidia
```

Erwartete Ausgabe (ähnlich wie):
```
Bus 001 Device 023: ID 0955:7523 NVIDIA Corp. APX
```

Wenn du `NVIDIA Corp.` siehst, ist der Jetson im Recovery-Modus. Falls nicht:
- Prüfe das USB-C Kabel (muss Daten unterstützen, nicht nur Laden)
- Versuche einen anderen USB-Port am Host (direkt am Mainboard, nicht über Hub)
- Wiederhole Schritt 2.2

---

### Phase 3: JetPack auf NVMe flashen

> **Wann:** Jetson ist im Recovery-Modus (Phase 2 abgeschlossen). Du sitzt am **Ubuntu-Laptop**.

**Schritt 3.1 — SDK Manager installieren (falls noch nicht geschehen)**

Auf dem **Ubuntu-Laptop**:

1. Gehe zu [developer.nvidia.com/sdk-manager](https://developer.nvidia.com/sdk-manager)
2. Klicke auf **Download** → wähle **.deb (Ubuntu)**
3. Es wird eine Datei wie `sdkmanager_2.x.x-xxxxx_amd64.deb` heruntergeladen

```bash
# Im Download-Verzeichnis:
cd ~/Downloads
sudo apt install ./sdkmanager_*_amd64.deb
```

> Falls Abhängigkeiten fehlen, anschließend: `sudo apt --fix-broken install`

**Schritt 3.2 — SDK Manager starten**

```bash
sdkmanager
```

Ein GUI-Fenster öffnet sich. Melde dich mit deinem **NVIDIA Developer Account** an (kostenlos registrieren unter [developer.nvidia.com](https://developer.nvidia.com)).

**Schritt 3.3 — Step 1: Development Environment**

| Einstellung | Wert |
|------------|------|
| Product Category | Jetson |
| Hardware Configuration | **Jetson Orin Nano Super Developer Kit** |
| Target OS | **JetPack 6.2.2** / Linux |
| DeepStream | Abwählen (brauchen wir nicht) |

> Falls der Jetson nicht automatisch erkannt wird: Prüfe die USB-Verbindung (Phase 2 wiederholen).

Klicke **Continue**.

**Schritt 3.4 — Step 2: Components**

- **Jetson Linux** (BSP): Muss ausgewählt sein ✓
- **Jetson Runtime Components**: Empfohlen ✓
- **Jetson SDK Components** (CUDA, cuDNN, TensorRT): Optional — nimmt ~5GB, empfohlen für AI/ML

Akzeptiere die Lizenzvereinbarungen. Klicke **Continue**.

**Schritt 3.5 — Step 3: Flash-Einstellungen (WICHTIG!)**

Hier wird festgelegt, **wohin** JetPack installiert wird:

| Einstellung | Wert |
|------------|------|
| Flash Method | **Manual Setup** |
| Storage Device | **NVMe** ← **Kritisch! Nicht eMMC oder SD Card!** |
| OEM Configuration | **Pre-Config** (Benutzer wird direkt im SDK Manager angelegt) |

> **Achtung:** Standardmäßig will SDK Manager auf die interne eMMC oder SD-Karte flashen. Du musst **explizit NVMe** als Speicherziel auswählen. Wenn die Option nicht sichtbar ist:
> - Stelle sicher, dass die NVMe SSD physisch eingebaut ist
> - Manche JetPack-Versionen zeigen NVMe erst, wenn du "Manual Setup" wählst

Klicke **Flash**. Der Vorgang dauert **10–30 Minuten** je nach SSD-Geschwindigkeit und Netzwerkverbindung (SDK-Komponenten werden heruntergeladen).

**Schritt 3.6 — Flash-Fortschritt abwarten**

Der SDK Manager zeigt den Fortschritt an:

1. ⏳ Herunterladen der Komponenten (einmalig, wird gecacht)
2. ⏳ Erstellen des Filesystem-Images
3. ⏳ Flashen auf die NVMe SSD
4. ⏳ Installieren der SDK-Komponenten

**Nicht unterbrechen!** Kein USB-Kabel ziehen, keinen Strom trennen.

Wenn der Flash abgeschlossen ist, startet der Jetson automatisch von der NVMe SSD neu.

---

### Phase 4: Setup über serielle Konsole ausführen

> **Wann:** Direkt nach dem Flash. Der Jetson bootet zum ersten Mal von der NVMe SSD. Du bleibst am **Flash-Rechner** (Ubuntu-Laptop oder Mac).
>
> **Ziel:** Alles in einem Rutsch über die serielle Konsole erledigen — Repo klonen, Setup ausführen, Neustart. Danach muss nur noch der SSH-Key vom Mac kopiert werden.

Da du in Phase 3 **Pre-Config** gewählt hast, wurden Benutzername, Passwort und Systemeinstellungen bereits im SDK Manager konfiguriert. Der Jetson bootet direkt in ein fertig eingerichtetes System.

**Schritt 4.1 — Serielle Konsole verbinden**

Das **gleiche USB-C Kabel** vom Flashen dient als serielle Konsole. Warte **1–3 Minuten** nach dem Flash, bis der Jetson gebootet ist.

```bash
# Serielles Gerät finden
ls /dev/ttyACM*
# Typisch: /dev/ttyACM0 oder /dev/ttyACM1
```

Verbindung herstellen — je nach Host-System:

```bash
# Ubuntu-Laptop: screen ist über apt verfügbar
sudo apt install screen          # einmalig
sudo screen /dev/ttyACM0 115200

# macOS: screen über Homebrew installieren (siehe Voraussetzungen)
brew install screen              # einmalig
sudo screen /dev/ttyACM0 115200

# macOS Alternative: cu ist bereits vorinstalliert (kein Homebrew nötig)
sudo cu -l /dev/ttyACM0 -s 115200
```

> **Beenden:** `screen` mit `Ctrl+A` dann `K` — `cu` mit `~.` (Tilde + Punkt).

**Schritt 4.2 — Einloggen und Netzwerk prüfen**

```bash
login: dein-benutzername
Password: dein-passwort
```

Ethernet-Kabel muss am Jetson stecken (Router/Switch). IP prüfen:

```bash
ip addr show eth0 | grep "inet "
# Ausgabe z.B.: inet 192.168.1.42/24 ...
```

> Notiere dir die **IP-Adresse** — du brauchst sie in Phase 5 für SSH vom Mac.

**Schritt 4.3 — Repo klonen und Setup starten**

```bash
git clone https://github.com/koljaschoepe/jetson-dev-setup.git
cd jetson-dev-setup
sudo ./setup.sh --interactive
```

Das Script fragt alle nötigen Werte ab:

```
Kundenname / Projektname: Firma-XY
Jetson Benutzername: arasul
Hostname [jetson]: jetson
Swap-Größe [32G]: 32G
Tailscale installieren? (true/false) [false]: false
Git Name: Max Mustermann
Git Email: max@firma.de
Claude Code installieren? (true/false) [true]: true
```

> **Alternativ:** Statt `--interactive` kannst du die `.env` manuell bearbeiten:
> ```bash
> cp .env.example .env
> nano .env           # Alle CHANGEME-Werte anpassen
> sudo ./setup.sh
> ```

**Schritt 4.4 — Setup-Fortschritt beobachten**

Das Script durchläuft 7 Schritte:

| Schritt | Was passiert | Dauer |
|---------|-------------|-------|
| 1 | GUI deaktivieren, unnötige Services stoppen, Kernel-Parameter tunen | ~3 Min |
| 2 | Hostname setzen, mDNS (Avahi) aktivieren, optional Tailscale | ~1 Min |
| 3 | SSH auf Key-Only umstellen, fail2ban installieren | ~1 Min |
| 4 | NVMe partitionieren (falls nötig), mounten, 32GB Swap, Verzeichnisse anlegen | ~2 Min |
| 5 | Docker-Datenverzeichnis auf NVMe, NVIDIA Container Runtime konfigurieren | ~2 Min |
| 6 | Node.js 22, Python3, Git, Claude Code CLI, jtop installieren | ~5 Min |
| 7 | tmux-Config, Shell-Aliases, Custom Prompt, MOTD | ~1 Min |

**Gesamt: ~15 Minuten.** Jeder Schritt zeigt Fortschrittsmeldungen.

> **Falls ein Schritt fehlschlägt:** Logs unter `/var/log/jetson-setup/` prüfen. Einzelne Schritte können nachgeholt werden: `sudo ./setup.sh --step 4`

**Schritt 4.5 — Neustart**

```bash
sudo reboot
```

Die serielle Konsole verliert die Verbindung. Der Jetson ist jetzt fertig konfiguriert — du kannst die serielle Konsole beenden und das USB-C Kabel abziehen.

> **Beenden:** `screen` mit `Ctrl+A` dann `K` — `cu` mit `~.` (Tilde + Punkt).

---

### Phase 5: SSH vom Mac einrichten

> **Wann:** Setup abgeschlossen, Jetson startet neu. Ab hier wechselst du auf deinen **Mac** — den Ubuntu-Laptop brauchst du nie wieder.

**Schritt 5.1 — SSH-Key erstellen (falls noch keiner existiert)**

```bash
# Prüfen ob schon ein Key existiert
ls ~/.ssh/id_ed25519.pub

# Falls nicht: neuen Key erstellen
ssh-keygen -t ed25519 -C "dein-name@mac"
# Enter für Standardpfad, optionale Passphrase setzen
```

**Schritt 5.2 — SSH-Key auf den Jetson kopieren**

Der Jetson muss per Ethernet im selben Netzwerk wie dein Mac sein.

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub BENUTZER@IP-ADRESSE
# IP-Adresse aus Schritt 4.2, z.B.: ssh-copy-id -i ~/.ssh/id_ed25519.pub arasul@192.168.1.42
```

Du wirst nach dem **Passwort** gefragt (aus der Pre-Config in Phase 3). Danach ist der Key hinterlegt.

**Schritt 5.3 — SSH-Verbindung testen**

```bash
ssh BENUTZER@IP-ADRESSE
```

Du solltest **ohne Passwort-Abfrage** verbunden werden.

---

### Phase 6: Mac SSH-Config einrichten (Komfort)

> **Wann:** SSH-Verbindung funktioniert (Phase 5 abgeschlossen). Ab jetzt brauchst du nie wieder eine IP-Adresse eintippen.

**Schritt 6.1 — Sockets-Verzeichnis erstellen**

```bash
mkdir -p ~/.ssh/sockets
```

**Schritt 6.2 — SSH-Config bearbeiten**

```bash
nano ~/.ssh/config
```

Füge am Ende hinzu (ersetze `BENUTZER` und `HOSTNAME`):

```
# --- Jetson via LAN (mDNS) ---
Host jetson
    HostName HOSTNAME.local
    User BENUTZER
    IdentityFile ~/.ssh/id_ed25519
    ControlMaster auto
    ControlPersist 600
    ControlPath ~/.ssh/sockets/%r@%h-%p
    ServerAliveInterval 60
    ServerAliveCountMax 3
    LocalForward 3000 localhost:3000
    LocalForward 8080 localhost:8080
    LocalForward 8888 localhost:8888

# --- Jetson via USB-C Direktverbindung ---
Host jetson-usb
    HostName 192.168.55.1
    User BENUTZER
    IdentityFile ~/.ssh/id_ed25519
```

> Beispiel: Wenn `JETSON_HOSTNAME=jetson` und `JETSON_USER=arasul`, dann wird `HostName` zu `jetson.local` und `User` zu `arasul`.

**Schritt 6.3 — Verbindung testen**

```bash
# Über LAN (nach Neustart, mDNS muss sich propagieren ~10 Sek)
ssh jetson

# Oder über USB-C
ssh jetson-usb
```

---

### Phase 7: Alles prüfen

> **Wann:** Du bist per `ssh jetson` verbunden. Der Jetson hat das Setup abgeschlossen.

**Schritt 7.1 — MOTD prüfen**

Beim Login siehst du ein Custom-Banner mit System-Infos (RAM, Disk, Temperatur).

**Schritt 7.2 — Grundfunktionen testen**

```bash
# tmux-Session starten
t

# RAM und Swap prüfen
free -h
# Erwartet: ~6GB RAM frei, ~32GB Swap

# NVMe prüfen
df -h /mnt/nvme
# Erwartet: NVMe gemountet mit viel Speicher

# Projekte-Verzeichnis
ls ~/projects
# Erwartet: Symlink zu /mnt/nvme/projects/

# Docker prüfen
docker run --rm hello-world
# Erwartet: "Hello from Docker!"

# NVIDIA GPU in Docker prüfen
docker run --rm --runtime=nvidia nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi
# Erwartet: GPU-Tabelle mit Orin

# Node.js
node --version
# Erwartet: v22.x.x

# Claude Code (falls installiert)
claude --version
```

**Schritt 7.3 — Jetson-Monitoring**

```bash
# Interaktives Dashboard
jtop

# Oder Einzeiler
sudo tegrastats
```

---

## Täglicher Workflow

```bash
# 1. Vom Mac verbinden
ssh jetson

# 2. tmux starten (oder bestehende Session fortsetzen)
t

# 3. Zum Projekt navigieren
p                           # Alias für: cd ~/projects
cd mein-projekt

# 4. Claude Code starten
claude

# 5. Jetson-Status prüfen
jtop                        # Interaktives Dashboard
```

## Nützliche Aliases

| Alias | Befehl |
|-------|--------|
| `t` | tmux `dev` Session (erstellt oder hängt sich an) |
| `c` | Claude Code starten |
| `p` | `cd ~/projects` |
| `jtop` | Jetson Systemmonitor |
| `dps` | Docker Container (formatiert) |
| `powermode` | NVPower-Mode anzeigen |
| `maxperf` | 25W + Max Clocks |
| `ram` | RAM + Swap |
| `temps` | Temperatur-Sensoren |

## Einzelne Setup-Schritte nachträglich ausführen

```bash
sudo ./setup.sh --step 4    # Nur NVMe-Setup
sudo ./setup.sh --step 6    # Nur Dev-Tools
```

## Was du am Ende hast

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

## Repo-Struktur

```
├── .env.example           # Konfigurations-Vorlage (alle Variablen)
├── .gitignore
├── CLAUDE.md              # Kontext für Claude Code
├── README.md              # Diese Datei
├── SETUP-PLAN.md          # Kompakte Planungsübersicht
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

Kurzfassung für erfahrene Nutzer — jeder Schritt ist oben im Detail erklärt:

```bash
# === AM FLASH-RECHNER (Ubuntu-Laptop oder Mac) ===
# 1. SSD einbauen, Recovery-Modus (Büroklammer auf Pins 9+10 an J14), JetPack auf NVMe flashen (Phase 1–3)

# 2. Über serielle Konsole: Setup komplett ausführen (Phase 4)
sudo screen /dev/ttyACM0 115200
# Login → dann:
git clone https://github.com/koljaschoepe/jetson-dev-setup.git
cd jetson-dev-setup
sudo ./setup.sh --interactive
sudo reboot

# === AM MAC ===
# 3. SSH-Key kopieren (Phase 5)
ssh-copy-id -i ~/.ssh/id_ed25519.pub BENUTZER@IP-ADRESSE

# 4. Mac SSH-Config einrichten (Phase 6)
# 5. SSH-Config an Kunden übergeben
cat config/mac-ssh-config
```

## Troubleshooting

### Flash-Probleme

| Problem | Lösung |
|---------|--------|
| SDK Manager erkennt Jetson nicht | USB-C Kabel prüfen (Daten, nicht nur Laden). Anderen USB-Port direkt am Mainboard probieren. `lsusb \| grep -i nvidia` muss NVIDIA zeigen. |
| NVMe nicht als Flash-Ziel wählbar | SSD physisch korrekt eingebaut? PCIe, nicht SATA-SSD! "Manual Setup" im SDK Manager wählen. |
| Flash bricht ab | Netzwerkverbindung stabil? Genug Speicher auf Host (~30GB frei)? Nochmal versuchen. |
| oem-config erscheint nicht | 60 Sekunden warten. `Enter` drücken. Serielles Gerät korrekt? `ls /dev/ttyACM*` auf dem Ubuntu-Laptop. |

### Boot-Probleme

| Problem | Lösung |
|---------|--------|
| Kein Video-Ausgang nach Setup | Normal — Headless-Modus. Serielle Konsole oder SSH nutzen. |
| Boot hängt | NVMe SSD Kontakt prüfen. Serielle Konsole für Boot-Logs anschließen. |
| Boot von SD statt NVMe | Recovery-Modus via Button Header Pins 9+10 (siehe Phase 2), nochmal auf NVMe flashen. SD-Karte entfernen. |

### SSH-Probleme

| Problem | Lösung |
|---------|--------|
| Connection refused | SSH-Dienst läuft? Via serieller Konsole prüfen: `systemctl status sshd` |
| Permission denied | Key kopiert? `ssh-copy-id` erneut ausführen. |
| Ausgesperrt nach SSH-Härtung | USB-C vom Ubuntu-Laptop anschließen, serielle Konsole öffnen (`sudo screen /dev/ttyACM0 115200`), SSH-Config reparieren. |
| `.local` Hostname geht nicht | mDNS/Avahi auf dem Jetson: `systemctl status avahi-daemon`. Auf dem Mac: Neustart des mDNS: `sudo killall -HUP mDNSResponder` |

### NVMe-Probleme

| Problem | Lösung |
|---------|--------|
| SSD nicht erkannt (`lsblk`) | Richtig eingebaut? Muss PCIe NVMe sein, kein SATA M.2! |
| Langsame Performance | `sudo nvme smart-log /dev/nvme0n1` für Health-Check. Thermal Throttling? `jtop` prüfen. |

### Docker-Probleme

| Problem | Lösung |
|---------|--------|
| Daemon startet nicht | `journalctl -u docker` prüfen. `daemon.json` Syntax korrekt? |
| GPU nicht verfügbar im Container | `nvidia-container-toolkit` installiert? `--runtime=nvidia` Flag gesetzt? |
| Kein Speicher | `docker system prune -af --volumes` zum Aufräumen. |

### RAM-Probleme

| Problem | Lösung |
|---------|--------|
| OOM (Out of Memory) | `free -h` prüfen. Container mit Memory-Limits starten (`--memory=2g`). |
| Nur 4–5GB frei bei 8GB | Normal — GPU reserviert 1–2GB vom geteilten RAM. |

## Wartung

```bash
# System-Updates (manuell — kein Auto-Update auf Edge-Devices!)
sudo apt update && sudo apt upgrade -y

# Docker aufräumen
docker system prune -af --volumes

# NVMe-Health prüfen
sudo nvme smart-log /dev/nvme0n1

# Logs aufräumen
sudo journalctl --vacuum-time=7d

# Swap prüfen
swapon --show
```

## Lizenz

MIT
