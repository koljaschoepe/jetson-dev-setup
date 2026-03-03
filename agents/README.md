# Claude Code Agents for Jetson Development

Useful Claude Code patterns and workflows for working on the Jetson Orin Nano Super.

## Quick Start

```bash
ssh jetson
t                    # tmux session
cd ~/projects/my-app
claude               # Start Claude Code
```

## Useful Claude Code Prompts

### System Health Check
```
claude -p "Check this Jetson: disk space, RAM, GPU temperature, Docker status, NVMe health. Summarize any issues."
```

### Bootstrap New Project
```
claude -p "Create a Python project in ~/projects/PROJECTNAME with: pyproject.toml, src/ layout, Dockerfile optimized for Jetson ARM64 with NVIDIA Runtime, docker-compose.yml, .gitignore and README. Python 3.10."
```

### Docker Compose for Jetson
```
claude -p "Create a docker-compose.yml for DESCRIPTION. Requirements: linux/arm64 images, NVIDIA Runtime, max 2GB RAM per container, /mnt/nvme/docker for volumes, health checks."
```

## Agent Patterns

### 1. Persistent Dev Session
Claude Code in a tmux pane — survives SSH disconnects:
```bash
tmux new -s claude
claude
# Ctrl-a d to detach
# tmux attach -t claude to reattach
```

### 2. Multi-Project Workflow
tmux windows for different projects:
```bash
tmux new -s dev
cd ~/projects/project-a && claude   # Window 1
# Ctrl-a c (new window)
cd ~/projects/project-b && claude   # Window 2
# Ctrl-a n/p to switch
```

### 3. System Administration
```
claude -p "Sysadmin for Jetson Orin Nano Super (8GB RAM, NVMe at /mnt/nvme). Check and optimize: disk usage, Docker cleanup, log rotation, swap, RAM-intensive services."
```

## ARM64 Notes for Claude Code

- **Docker images must be ARM64**: Always specify `platform: linux/arm64`
- **PyTorch needs NVIDIA wheels**: `pip install torch` doesn't work directly
- **8GB shared RAM**: Max 2-3 Docker containers simultaneously
- **NVMe is primary storage**: Projects under `/mnt/nvme/projects/`
- **No GUI**: Everything is terminal-based
- **CUDA 12.6**: GPU in Docker with `--runtime=nvidia`

## CLAUDE.md Template for Projects

```markdown
# Project Name

## What
Brief description.

## Architecture
- Runtime: Docker on Jetson Orin Nano Super (ARM64, 8GB RAM)
- Storage: /mnt/nvme/projects/this-project
- GPU: CUDA 12.6 via NVIDIA Container Runtime

## Commands
- Build: `docker compose build`
- Run: `docker compose up -d`
- Test: `docker compose exec app pytest`
- Logs: `docker compose logs -f`

## Constraints
- Max 2GB RAM per container
- ARM64 images only
- Prefer offline-capable (edge deployment)
```
