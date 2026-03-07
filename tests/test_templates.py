"""Tests for the template engine (core/templates.py)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from arasul_tui.core.templates import (
    TEMPLATES,
    TemplateConfig,
    generate_claude_md,
    generate_dotenv,
    get_template,
    is_miniforge_installed,
    list_templates,
    scaffold_project,
)


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------


def test_list_templates():
    templates = list_templates()
    assert len(templates) == 5
    names = [t.name for t in templates]
    assert "python-gpu" in names
    assert "vision" in names
    assert "api" in names
    assert "notebook" in names
    assert "webapp" in names


def test_get_template_existing():
    t = get_template("python-gpu")
    assert t is not None
    assert t.name == "python-gpu"
    assert t.label == "Python + GPU"


def test_get_template_nonexistent():
    assert get_template("nonexistent") is None


def test_template_config_defaults():
    t = TemplateConfig(name="test", label="Test", description="Test template")
    assert t.python_version == "3.10"
    assert t.has_docker is False
    assert t.has_dotenv is True
    assert t.conda_packages == []
    assert t.pip_packages == []
    assert t.starter_files == []


def test_python_gpu_has_nvidia_index():
    t = get_template("python-gpu")
    assert t.pip_extra_index is not None
    assert "nvidia" in t.pip_extra_index


def test_vision_has_docker():
    t = get_template("vision")
    assert t.has_docker is True


def test_api_has_docker():
    t = get_template("api")
    assert t.has_docker is True


def test_webapp_has_docker():
    t = get_template("webapp")
    assert t.has_docker is True


def test_notebook_no_docker():
    t = get_template("notebook")
    assert t.has_docker is False


# ---------------------------------------------------------------------------
# CLAUDE.md generation
# ---------------------------------------------------------------------------


def test_generate_claude_md_python_gpu():
    t = get_template("python-gpu")
    content = generate_claude_md("my-model", t)
    assert "my-model" in content
    assert "Jetson Orin Nano" in content
    assert "CUDA 12.6" in content
    assert "PyTorch" in content
    assert "/mnt/nvme/envs/my-model" in content


def test_generate_claude_md_webapp():
    t = get_template("webapp")
    content = generate_claude_md("my-app", t)
    assert "Next.js" in content
    assert "FastAPI" in content
    assert "PostgreSQL" in content
    assert "/expose" in content


def test_generate_claude_md_notebook():
    t = get_template("notebook")
    content = generate_claude_md("research", t)
    assert "JupyterLab" in content
    assert "ssh -L 8888" in content


def test_generate_claude_md_all_templates():
    for name, tpl in TEMPLATES.items():
        content = generate_claude_md(f"test-{name}", tpl)
        assert f"test-{name}" in content
        assert "ARM64" in content


# ---------------------------------------------------------------------------
# .env generation
# ---------------------------------------------------------------------------


def test_generate_dotenv_webapp():
    t = get_template("webapp")
    content = generate_dotenv("my-app", t)
    assert "POSTGRES_DB=my_app" in content
    assert "POSTGRES_PASSWORD=" in content
    assert "SECRET_KEY=" in content
    assert "DATABASE_URL=" in content


def test_generate_dotenv_api():
    t = get_template("api")
    content = generate_dotenv("my-api", t)
    assert "API_PORT=8000" in content


def test_generate_dotenv_notebook():
    t = get_template("notebook")
    content = generate_dotenv("research", t)
    assert "JUPYTER_PORT=8888" in content
    assert "JUPYTER_TOKEN=" in content


def test_generate_dotenv_python_gpu():
    t = get_template("python-gpu")
    content = generate_dotenv("trainer", t)
    assert "DEVICE=cuda" in content


def test_generate_dotenv_unique_secrets():
    t = get_template("webapp")
    env1 = generate_dotenv("app1", t)
    env2 = generate_dotenv("app2", t)
    # Secrets should be different each time
    pw1 = [l for l in env1.splitlines() if "POSTGRES_PASSWORD=" in l][0]
    pw2 = [l for l in env2.splitlines() if "POSTGRES_PASSWORD=" in l][0]
    assert pw1 != pw2


# ---------------------------------------------------------------------------
# Miniforge check
# ---------------------------------------------------------------------------


def test_is_miniforge_installed_false():
    with patch("arasul_tui.core.templates.CONDA_BIN", Path("/nonexistent/conda")):
        assert is_miniforge_installed() is False


def test_is_miniforge_installed_true(tmp_path: Path):
    conda = tmp_path / "conda"
    conda.write_text("#!/bin/sh\n")
    with patch("arasul_tui.core.templates.CONDA_BIN", conda):
        assert is_miniforge_installed() is True


# ---------------------------------------------------------------------------
# Project scaffolding
# ---------------------------------------------------------------------------


def test_scaffold_creates_claude_md(tmp_path: Path):
    t = get_template("python-gpu")
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()

    ok, msg = scaffold_project(project_dir, "my-project", t)
    assert ok is True
    assert (project_dir / "CLAUDE.md").exists()

    content = (project_dir / "CLAUDE.md").read_text()
    assert "my-project" in content


def test_scaffold_creates_dotenv(tmp_path: Path):
    t = get_template("api")
    project_dir = tmp_path / "my-api"
    project_dir.mkdir()

    scaffold_project(project_dir, "my-api", t)
    assert (project_dir / ".env").exists()

    content = (project_dir / ".env").read_text()
    assert "API_PORT" in content


def test_scaffold_creates_gitignore(tmp_path: Path):
    t = get_template("python-gpu")
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    scaffold_project(project_dir, "proj", t)
    assert (project_dir / ".gitignore").exists()

    content = (project_dir / ".gitignore").read_text()
    assert ".env" in content
    assert "__pycache__/" in content


def test_scaffold_copies_starter_files(tmp_path: Path):
    # Create a fake template source
    t = TemplateConfig(
        name="test-tpl",
        label="Test",
        description="test",
        starter_files=["hello.py"],
    )

    # Create template source dir with the file
    tpl_dir = tmp_path / "templates" / "test-tpl"
    tpl_dir.mkdir(parents=True)
    (tpl_dir / "hello.py").write_text("print('hello')\n")

    project_dir = tmp_path / "my-proj"
    project_dir.mkdir()

    with patch("arasul_tui.core.templates.TEMPLATE_DIR", tmp_path / "templates"):
        ok, msg = scaffold_project(project_dir, "my-proj", t)

    assert ok is True
    assert (project_dir / "hello.py").exists()
    assert (project_dir / "hello.py").read_text() == "print('hello')\n"


def test_scaffold_creates_nested_dirs(tmp_path: Path):
    """Webapp template has backend/ subdirectory files."""
    t = TemplateConfig(
        name="nested-tpl",
        label="Nested",
        description="test",
        starter_files=["sub/file.py"],
    )

    tpl_dir = tmp_path / "templates" / "nested-tpl" / "sub"
    tpl_dir.mkdir(parents=True)
    (tpl_dir / "file.py").write_text("# nested\n")

    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    with patch("arasul_tui.core.templates.TEMPLATE_DIR", tmp_path / "templates"):
        ok, _ = scaffold_project(project_dir, "proj", t)

    assert ok
    assert (project_dir / "sub" / "file.py").exists()
