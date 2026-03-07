"""Template engine for GPU-ready project scaffolding.

Manages template registry, conda environment creation, CLAUDE.md generation,
and starter code deployment. Miniforge3 is lazily installed on first use.
"""

from __future__ import annotations

import secrets
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NVME_BASE = Path("/mnt/nvme")
MINIFORGE_DIR = NVME_BASE / "miniforge3"
CONDA_BIN = MINIFORGE_DIR / "bin" / "conda"
ENVS_DIR = NVME_BASE / "envs"
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "config" / "templates"


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------


@dataclass
class TemplateConfig:
    name: str
    label: str
    description: str
    conda_packages: list[str] = field(default_factory=list)
    pip_packages: list[str] = field(default_factory=list)
    pip_extra_index: str | None = None
    python_version: str = "3.10"
    has_docker: bool = False
    has_dotenv: bool = True
    starter_files: list[str] = field(default_factory=list)


TEMPLATES: dict[str, TemplateConfig] = {
    "python-gpu": TemplateConfig(
        name="python-gpu",
        label="Python + GPU",
        description="PyTorch + CUDA for ML training, inference, GPU computing",
        conda_packages=["numpy", "scipy"],
        pip_packages=["torch", "torchvision", "torchaudio"],
        pip_extra_index="https://developer.download.nvidia.com/compute/redist/jp/v61",
        starter_files=["main.py", "requirements.txt"],
    ),
    "vision": TemplateConfig(
        name="vision",
        label="Computer Vision",
        description="OpenCV + YOLO11 + torchvision for object detection and video analysis",
        conda_packages=["numpy"],
        pip_packages=["torch", "torchvision", "opencv-python-headless", "ultralytics"],
        pip_extra_index="https://developer.download.nvidia.com/compute/redist/jp/v61",
        has_docker=True,
        starter_files=["detect.py", "requirements.txt", "docker-compose.yml"],
    ),
    "api": TemplateConfig(
        name="api",
        label="Inference API",
        description="FastAPI + PyTorch for model inference REST endpoints",
        conda_packages=["numpy"],
        pip_packages=["torch", "fastapi", "uvicorn[standard]"],
        pip_extra_index="https://developer.download.nvidia.com/compute/redist/jp/v61",
        has_docker=True,
        starter_files=["app.py", "requirements.txt", "Dockerfile", "docker-compose.yml", "Caddyfile"],
    ),
    "notebook": TemplateConfig(
        name="notebook",
        label="JupyterLab",
        description="JupyterLab + scientific stack for data analysis and research",
        conda_packages=["numpy", "pandas", "matplotlib", "scikit-learn", "seaborn"],
        pip_packages=["jupyterlab"],
        starter_files=["getting_started.ipynb", "requirements.txt"],
    ),
    "webapp": TemplateConfig(
        name="webapp",
        label="Full-Stack Web App",
        description="Next.js + FastAPI + PostgreSQL + Caddy for self-hosted apps",
        conda_packages=[],
        pip_packages=["fastapi", "uvicorn[standard]", "asyncpg", "sqlalchemy[asyncio]", "alembic"],
        has_docker=True,
        starter_files=[
            "docker-compose.yml",
            "Caddyfile",
            "backend/app.py",
            "backend/requirements.txt",
            "backend/Dockerfile",
        ],
    ),
}


def list_templates() -> list[TemplateConfig]:
    return list(TEMPLATES.values())


def get_template(name: str) -> TemplateConfig | None:
    return TEMPLATES.get(name)


# ---------------------------------------------------------------------------
# Miniforge3 management
# ---------------------------------------------------------------------------


def is_miniforge_installed() -> bool:
    return CONDA_BIN.exists() and CONDA_BIN.is_file()


def install_miniforge(on_progress: Any = None) -> tuple[bool, str]:
    """Install Miniforge3. Returns (success, message).

    This calls the setup script which handles download, install, and config.
    """
    script = Path(__file__).parent.parent.parent / "scripts" / "10-miniforge-setup.sh"
    if not script.exists():
        return False, f"Setup script not found: {script}"

    try:
        result = subprocess.run(
            ["sudo", str(script)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return True, "Miniforge3 installed successfully"
        return False, (result.stderr or result.stdout or "Unknown error").strip()
    except subprocess.TimeoutExpired:
        return False, "Installation timed out (5 min)"
    except OSError as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Conda environment management
# ---------------------------------------------------------------------------


def _run_conda(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CONDA_BIN)] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def create_conda_env(
    project_name: str,
    template: TemplateConfig,
    on_progress: Any = None,
) -> tuple[bool, str]:
    """Create an isolated conda env for a project. Returns (success, message)."""
    env_path = ENVS_DIR / project_name

    if env_path.exists():
        return False, f"Environment already exists: {env_path}"

    # Create env with Python
    try:
        result = _run_conda([
            "create",
            "--prefix", str(env_path),
            f"python={template.python_version}",
            "-y",
            "-q",
        ])
        if result.returncode != 0:
            return False, f"conda create failed: {(result.stderr or result.stdout or '').strip()}"
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, f"conda create failed: {exc}"

    # Install conda packages
    if template.conda_packages:
        try:
            result = _run_conda([
                "install",
                "--prefix", str(env_path),
                "-y",
                "-q",
            ] + template.conda_packages)
            if result.returncode != 0:
                return False, f"conda install failed: {(result.stderr or result.stdout or '').strip()}"
        except (subprocess.TimeoutExpired, OSError) as exc:
            return False, f"conda install failed: {exc}"

    # Install pip packages
    if template.pip_packages:
        pip_bin = env_path / "bin" / "pip"
        pip_cmd = [str(pip_bin), "install", "-q"] + template.pip_packages
        if template.pip_extra_index:
            pip_cmd += ["--extra-index-url", template.pip_extra_index]
        try:
            result = subprocess.run(
                pip_cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                return False, f"pip install failed: {(result.stderr or result.stdout or '').strip()}"
        except (subprocess.TimeoutExpired, OSError) as exc:
            return False, f"pip install failed: {exc}"

    return True, str(env_path)


def remove_conda_env(project_name: str) -> tuple[bool, str]:
    """Remove a conda env. Returns (success, message)."""
    env_path = ENVS_DIR / project_name
    if not env_path.exists():
        return True, "Environment does not exist"
    try:
        shutil.rmtree(env_path)
        return True, f"Removed {env_path}"
    except OSError as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# CLAUDE.md generation
# ---------------------------------------------------------------------------

_CLAUDE_MD_HEADER = """\
# {project_name} — Claude Code Context

## Hardware
- **Device:** NVIDIA Jetson Orin Nano Super Developer Kit (8GB shared RAM)
- **GPU:** 1024 CUDA Cores (Ampere), CUDA 12.6
- **Arch:** ARM64 (aarch64)
- **OS:** JetPack 6.2.2 (Ubuntu 22.04)

## Environment
- **Python:** {python_version} (Miniforge3 conda)
- **Env path:** /mnt/nvme/envs/{project_name}/
- **Activate:** `source /mnt/nvme/miniforge3/bin/activate /mnt/nvme/envs/{project_name}`

## Constraints
- 8GB RAM shared between CPU and GPU — monitor memory usage
- ARM64 — not all PyPI wheels available, prefer conda-forge
- Docker images must be linux/arm64 or multi-arch
"""

_TEMPLATE_SECTIONS: dict[str, str] = {
    "python-gpu": """
## Stack
- PyTorch (NVIDIA Jetson wheels) + numpy + scipy
- CUDA 12.6 available at /usr/local/cuda-12.6/
- GPU memory shared with system — ~5.5GB available for training

## PyTorch Notes
- Jetson wheels from NVIDIA index (not PyPI)
- Use `torch.cuda.is_available()` to verify GPU access
- Monitor GPU memory: `torch.cuda.mem_get_info()`
- For large models, use `torch.cuda.amp` for mixed precision
""",
    "vision": """
## Stack
- PyTorch + torchvision + OpenCV + YOLO11 (ultralytics)
- Docker Compose with `--runtime=nvidia` for GPU access
- CUDA 12.6 available at /usr/local/cuda-12.6/

## Vision Notes
- OpenCV headless build (no GUI) — use `cv2.imwrite()` to save results
- YOLO11: `from ultralytics import YOLO; model = YOLO('yolo11n.pt')`
- Camera: `/dev/video0` (USB) or CSI via GStreamer pipeline
- For real-time: target 720p or lower for good FPS on 1024 CUDA cores
""",
    "api": """
## Stack
- FastAPI + Uvicorn + PyTorch
- Caddy reverse proxy with auto-HTTPS
- Docker Compose with `--runtime=nvidia`

## API Notes
- Health endpoint: GET /health
- Prediction endpoint: POST /predict
- Load model once at startup, not per-request
- Uvicorn workers: 1 (shared GPU memory)
- Caddy handles HTTPS termination
""",
    "notebook": """
## Stack
- JupyterLab + numpy + pandas + matplotlib + scikit-learn + seaborn

## Access
- Start: `jupyter lab --no-browser --ip=0.0.0.0 --port=8888`
- SSH tunnel from your machine: `ssh -L 8888:localhost:8888 jetson`
- Then open: http://localhost:8888

## Notes
- ~180MB RAM for JupyterLab server
- GPU available in notebooks via PyTorch (if installed)
- Save large datasets to /mnt/nvme/, not project dir
""",
    "webapp": """
## Stack
- **Frontend:** Next.js 15 (TypeScript) on port 3000
- **Backend:** FastAPI + SQLAlchemy + asyncpg on port 8000
- **Database:** PostgreSQL 16 (Docker)
- **Proxy:** Caddy with auto-HTTPS

## Development
- Start all services: `docker compose up -d`
- Backend API docs: http://localhost:8000/docs
- Frontend dev: `cd frontend && npm run dev`

## Deployment
- Caddy handles HTTPS via Tailscale Funnel
- Use `/expose` in Arasul TUI to start public URL
- Database data persisted in Docker volume

## Environment Variables
- `.env` has auto-generated secrets — do NOT commit
- `DATABASE_URL` connects backend to PostgreSQL
- `SECRET_KEY` for session/JWT signing
""",
}


def generate_claude_md(project_name: str, template: TemplateConfig) -> str:
    """Generate a project-specific CLAUDE.md."""
    content = _CLAUDE_MD_HEADER.format(
        project_name=project_name,
        python_version=template.python_version,
    )
    section = _TEMPLATE_SECTIONS.get(template.name, "")
    if section:
        content += section
    return content


# ---------------------------------------------------------------------------
# .env generation
# ---------------------------------------------------------------------------


def generate_dotenv(project_name: str, template: TemplateConfig) -> str:
    """Generate a .env file with auto-generated secrets."""
    lines = [
        f"# {project_name} environment variables",
        f"PROJECT_NAME={project_name}",
        "",
    ]

    if template.name == "webapp":
        lines += [
            "# Database",
            f"POSTGRES_DB={project_name.replace('-', '_')}",
            "POSTGRES_USER=app",
            f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}",
            f'DATABASE_URL=postgresql+asyncpg://app:${{POSTGRES_PASSWORD}}@db:5432/{project_name.replace("-", "_")}',
            "",
            "# Security",
            f"SECRET_KEY={secrets.token_urlsafe(32)}",
            "",
            "# Ports",
            "BACKEND_PORT=8000",
            "FRONTEND_PORT=3000",
        ]
    elif template.name == "api":
        lines += [
            "# API",
            "API_HOST=0.0.0.0",
            "API_PORT=8000",
            "MODEL_PATH=model.pt",
        ]
    elif template.name == "notebook":
        lines += [
            "# JupyterLab",
            "JUPYTER_PORT=8888",
            f"JUPYTER_TOKEN={secrets.token_urlsafe(16)}",
        ]
    else:
        lines += [
            "# Project",
            "DEVICE=cuda",
        ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Project scaffolding
# ---------------------------------------------------------------------------


def scaffold_project(
    project_dir: Path,
    project_name: str,
    template: TemplateConfig,
) -> tuple[bool, str]:
    """Copy template files and generate config files.

    Assumes project_dir already exists. Does NOT create conda env.
    Returns (success, message).
    """
    template_source = TEMPLATE_DIR / template.name

    # Copy starter files from template directory
    if template_source.exists():
        for rel_file in template.starter_files:
            src = template_source / rel_file
            dst = project_dir / rel_file
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    # Generate CLAUDE.md
    claude_md = generate_claude_md(project_name, template)
    (project_dir / "CLAUDE.md").write_text(claude_md)

    # Generate .env
    if template.has_dotenv:
        dotenv = generate_dotenv(project_name, template)
        (project_dir / ".env").write_text(dotenv)

    # Generate .gitignore
    gitignore_lines = [
        ".env",
        "__pycache__/",
        "*.pyc",
        ".ipynb_checkpoints/",
        "*.pt",
        "*.pth",
        "*.onnx",
        "node_modules/",
        ".next/",
    ]
    (project_dir / ".gitignore").write_text("\n".join(gitignore_lines) + "\n")

    return True, "Project scaffolded"
