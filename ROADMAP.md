# Arasul Roadmap

## v0.4.0 — Smart Project Templates

Turn the Jetson into a ready-to-use AI development platform. `/create` gets an optional `--type` flag that scaffolds complete, GPU-ready projects with isolated environments, Docker configs, and context-aware CLAUDE.md files.

**Existing behavior is unchanged.** `/create my-project` and `/clone <url>` work exactly as before. Templates are purely additive.

---

### Template Types

| Type | Stack | Use Case |
|------|-------|----------|
| `python-gpu` | PyTorch + CUDA 12.6 | ML training, inference, GPU computing |
| `vision` | OpenCV + YOLO11 + torchvision | Object detection, video analysis, camera streams |
| `api` | FastAPI + Uvicorn + Caddy | Model inference API, REST endpoints |
| `notebook` | JupyterLab + scientific stack | Data analysis, research, interactive prototyping |
| `webapp` | Next.js + FastAPI + PostgreSQL + Caddy | Self-hosted web apps, SaaS prototypes |

### Architecture Principles

1. **Lazy Loading** — Miniforge3 installs only on first `--type` usage, not at system setup
2. **Per-Project Isolation** — Each project gets its own conda env on NVMe (`/mnt/nvme/envs/<name>`)
3. **RAM-Conscious** — No pre-loaded services; environments activate only when project is opened
4. **NVIDIA-Aware** — PyTorch Jetson wheels auto-configured, CUDA paths set, ARM64 constraints documented
5. **Backwards Compatible** — `/create` and `/clone` without `--type` behave exactly as before

### What Each Template Creates

**All templates include:**
- Project directory in `/mnt/nvme/projects/<name>/`
- Isolated conda environment (Miniforge3, Python 3.10)
- `.env` template with auto-generated secrets where needed
- `CLAUDE.md` with hardware context (Jetson Orin Nano, 8GB shared RAM, CUDA 12.6, ARM64)
- Registered in Arasul project registry

**python-gpu** adds:
- PyTorch (NVIDIA Jetson wheels) + numpy + scipy
- Starter: `main.py` with GPU detection and tensor benchmark
- `requirements.txt` pinned to Jetson-compatible versions

**vision** adds:
- PyTorch + torchvision + OpenCV + ultralytics (YOLO11)
- Docker Compose with `--runtime=nvidia`
- Starter: `detect.py` (image/webcam object detection demo)
- Sample image for testing

**api** adds:
- FastAPI + Uvicorn + PyTorch
- Docker Compose: FastAPI app + Caddy reverse proxy
- Starter: `app.py` with `/predict` endpoint (accepts image, returns inference)
- `Dockerfile` optimized for ARM64 + CUDA
- Health check endpoint

**notebook** adds:
- JupyterLab + numpy + pandas + matplotlib + scikit-learn + seaborn
- Starter: `getting_started.ipynb` (GPU check, data viz example, model training)
- JupyterLab config for headless access (bind 0.0.0.0:8888)
- SSH tunnel instructions in CLAUDE.md

**webapp** adds:
- Next.js 15 frontend (TypeScript)
- FastAPI backend with PostgreSQL
- Docker Compose: frontend + backend + postgres + Caddy
- Caddy with auto-HTTPS
- Tailscale Funnel integration (`/expose` command)
- `.env` with auto-generated DB password and secrets
- CLAUDE.md with deployment and Tailscale Funnel instructions

---

### Implementation Plan

#### Phase 1: Infrastructure
- [ ] `scripts/10-miniforge-setup.sh` — Lazy Miniforge3 installer (aarch64)
  - Downloads to `/mnt/nvme/miniforge3`
  - Configures conda but does NOT activate globally
  - Only runs when triggered by first template creation
  - Idempotent (skips if already installed)
- [ ] `arasul_tui/core/templates.py` — Template engine
  - Template registry (type -> config mapping)
  - Conda environment creation per project
  - NVIDIA Jetson wheel configuration
  - CLAUDE.md generation with hardware context
  - Starter code copying from template directories

#### Phase 2: Templates
- [ ] `config/templates/python-gpu/` — Files, CLAUDE.md template, requirements
- [ ] `config/templates/vision/` — Files, docker-compose.yml, detect.py
- [ ] `config/templates/api/` — Files, docker-compose.yml, Dockerfile, app.py
- [ ] `config/templates/notebook/` — Files, jupyter config, getting_started.ipynb
- [ ] `config/templates/webapp/` — Files, docker-compose.yml, Caddy config, frontend scaffold

#### Phase 3: TUI Integration
- [ ] Extend `commands/project.py` — Add `--type` parameter to `/create`
  - No type = existing behavior (unchanged)
  - With type = template creation flow
  - Auto-install Miniforge3 on first use
  - Progress display during environment setup
- [ ] New command: `/expose` — Tailscale Funnel management for webapp projects
  - Start/stop public URL for a project
  - Show current Funnel status

#### Phase 4: Testing & Docs
- [ ] Tests for template engine (core/templates.py)
- [ ] Tests for enhanced /create command
- [ ] Tests for /expose command
- [ ] Update README.md with template documentation
- [ ] Update CLAUDE.md with template system details

---

### Example Flows

**First template creation (installs Miniforge3):**
```
arasul> /create my-model --type python-gpu

  Miniforge3 not found. Installing...
  Downloading Miniforge3-Linux-aarch64.sh...
  Installing to /mnt/nvme/miniforge3...
  Done (one-time setup)

  Creating project: my-model
  > Project directory
  > conda env: my-model (Python 3.10)
  > PyTorch 2.5 (NVIDIA Jetson wheels)
  > numpy + scipy
  > CLAUDE.md (GPU + ARM64 context)
  > Starter: main.py
  > .env template
  > Registered in Arasul

  Ready! Type 'c' to open in Claude Code
```

**Subsequent template creation (Miniforge3 already installed):**
```
arasul> /create detector --type vision

  Creating project: detector
  > Project directory
  > conda env: detector (Python 3.10)
  > PyTorch 2.5 + torchvision + OpenCV + YOLO11
  > Docker Compose (CUDA runtime)
  > CLAUDE.md (vision + ARM64 context)
  > Starter: detect.py
  > .env template
  > Registered in Arasul

  Ready! Type 'c' to open in Claude Code
```

**Regular project creation (unchanged):**
```
arasul> /create my-project

  What should the new project be called?
  (same flow as before — no template, no environment)
```

**Clone from GitHub (unchanged):**
```
arasul> /clone https://github.com/user/repo

  (same flow as before)
```

---

### Technical Notes

- Miniforge3 installs to `/mnt/nvme/miniforge3` (NVMe, not SD card)
- Conda envs at `/mnt/nvme/envs/<project-name>/` (shared envs dir on NVMe)
- PyTorch Jetson wheels from `https://developer.download.nvidia.com/compute/redist/jp/`
- CUDA 12.6 paths already in system PATH via JetPack 6.2
- JupyterLab accessed via SSH tunnel: `ssh -L 8888:localhost:8888 jetson`
- Webapp public URL via Tailscale Funnel (requires Tailscale connected)
- Template files stored in `config/templates/` within the repo
- Each CLAUDE.md includes: Jetson hardware specs, available GPU memory, CUDA version, ARM64 constraints, installed libraries, project-specific guidelines

### Resource Budget (8GB shared RAM)

| Component | RAM Usage | Notes |
|-----------|-----------|-------|
| OS + services | ~1.5 GB | Headless, optimized by setup scripts |
| Docker daemon | ~200 MB | Always running |
| Arasul TUI | ~30 MB | Python process |
| conda env (idle) | 0 MB | Not loaded until activated |
| JupyterLab server | ~180 MB | Only when notebook project active |
| PyTorch (loaded) | ~500 MB | Only during inference/training |
| PostgreSQL (Docker) | ~100 MB | Only for webapp/n8n projects |
| **Available for work** | **~5.5 GB** | Sufficient for training small models |
