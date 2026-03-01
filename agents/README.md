# Claude Code Agents für Jetson-Entwicklung

Nützliche Claude Code Patterns und Workflows für die Arbeit auf dem Jetson Orin Nano Super.

## Quick Start

```bash
ssh jetson
t                    # tmux Session
cd ~/projects/mein-app
claude               # Claude Code starten
```

## Nützliche Claude Code Befehle

### System Health Check
```
claude -p "Prüfe diesen Jetson: Disk-Space, RAM, GPU-Temperatur, Docker-Status, NVMe-Health. Fasse Probleme zusammen."
```

### Neues Projekt bootstrappen
```
claude -p "Erstelle ein Python-Projekt in ~/projects/PROJEKTNAME mit: pyproject.toml, src/-Layout, Dockerfile optimiert für Jetson ARM64 mit NVIDIA Runtime, docker-compose.yml, .gitignore und README. Python 3.10."
```

### Docker Compose für Jetson
```
claude -p "Erstelle eine docker-compose.yml für BESCHREIBUNG. Anforderungen: linux/arm64 Images, NVIDIA Runtime, max 2GB RAM pro Container, /mnt/nvme/docker für Volumes, Health Checks."
```

## Agent-Patterns

### 1. Persistente Dev-Session
Claude Code in einem tmux-Pane — überlebt SSH-Disconnects:
```bash
tmux new -s claude
claude
# Ctrl-a d zum Detachen
# tmux attach -t claude zum Reattachen
```

### 2. Multi-Projekt Workflow
tmux-Fenster für verschiedene Projekte:
```bash
tmux new -s dev
cd ~/projects/projekt-a && claude   # Fenster 1
# Ctrl-a c (neues Fenster)
cd ~/projects/projekt-b && claude   # Fenster 2
# Ctrl-a n/p zum Wechseln
```

### 3. System-Administration
```
claude -p "Sysadmin für Jetson Orin Nano Super (8GB RAM, NVMe auf /mnt/nvme). Prüfe und optimiere: Disk Usage, Docker Cleanup, Log Rotation, Swap, RAM-intensive Services."
```

## ARM64-Hinweise für Claude Code

- **Docker-Images müssen ARM64 sein**: Immer `platform: linux/arm64` angeben
- **PyTorch braucht NVIDIA-Wheels**: `pip install torch` funktioniert nicht direkt
- **8GB geteilter RAM**: Max 2-3 Docker-Container gleichzeitig
- **NVMe ist Primärspeicher**: Projekte unter `/mnt/nvme/projects/`
- **Kein GUI**: Alles terminal-basiert
- **CUDA 12.6**: GPU in Docker mit `--runtime=nvidia`

## CLAUDE.md Template für Projekte

```markdown
# Projektname

## Was
Kurze Beschreibung.

## Architektur
- Runtime: Docker auf Jetson Orin Nano Super (ARM64, 8GB RAM)
- Speicher: /mnt/nvme/projects/dieses-projekt
- GPU: CUDA 12.6 via NVIDIA Container Runtime

## Befehle
- Build: `docker compose build`
- Run: `docker compose up -d`
- Test: `docker compose exec app pytest`
- Logs: `docker compose logs -f`

## Einschränkungen
- Max 2GB RAM pro Container
- Nur ARM64-Images
- Offline-fähig bevorzugt (Edge Deployment)
```
