"""Tests for /create --type template integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arasul_tui.commands.project import cmd_create
from arasul_tui.core.state import TuiState


@pytest.fixture
def state(tmp_path: Path) -> TuiState:
    s = TuiState()
    s.project_root = tmp_path
    return s


def test_create_without_type_unchanged(state: TuiState):
    """Regular /create still works as before."""
    result = cmd_create(state, ["my-project"])
    assert result.ok is True
    assert (state.project_root / "my-project").exists()


def test_create_without_type_prompts(state: TuiState):
    """No args = prompt for name (unchanged)."""
    result = cmd_create(state, [])
    assert result.pending_handler is not None
    assert result.prompt == "Name"


def test_create_with_unknown_type(state: TuiState):
    """Unknown template type gives error."""
    with patch("arasul_tui.commands.project.is_miniforge_installed", return_value=True):
        result = cmd_create(state, ["proj", "--type", "nonexistent"])
    assert result.ok is False


@patch("arasul_tui.commands.project.is_miniforge_installed", return_value=True)
@patch("arasul_tui.commands.project.create_conda_env", return_value=(True, "/mnt/nvme/envs/ml-proj"))
@patch("arasul_tui.commands.project.spinner_run")
def test_create_with_template(mock_spinner, mock_env, mock_mf, state: TuiState, tmp_path: Path):
    """Full template creation flow."""
    # spinner_run should call the function and return its result
    mock_spinner.side_effect = lambda msg, fn: fn()

    with patch("arasul_tui.commands.project.register_project"):
        result = cmd_create(state, ["ml-proj", "--type", "python-gpu"])

    assert result.ok is True
    assert result.refresh is True
    assert (tmp_path / "ml-proj").exists()
    assert (tmp_path / "ml-proj" / "CLAUDE.md").exists()
    assert (tmp_path / "ml-proj" / ".env").exists()
    assert (tmp_path / "ml-proj" / ".gitignore").exists()


@patch("arasul_tui.commands.project.is_miniforge_installed", return_value=False)
@patch("arasul_tui.commands.project.install_miniforge", return_value=(True, "ok"))
@patch("arasul_tui.commands.project.create_conda_env", return_value=(True, "/mnt/nvme/envs/proj"))
@patch("arasul_tui.commands.project.spinner_run")
def test_create_installs_miniforge_on_first_use(
    mock_spinner, mock_env, mock_install, mock_check, state: TuiState
):
    """Miniforge3 should be installed on first template use."""
    mock_spinner.side_effect = lambda msg, fn: fn()

    with patch("arasul_tui.commands.project.register_project"):
        result = cmd_create(state, ["first-proj", "--type", "python-gpu"])

    assert result.ok is True
    mock_install.assert_called_once()


@patch("arasul_tui.commands.project.is_miniforge_installed", return_value=True)
@patch("arasul_tui.commands.project.create_conda_env", return_value=(True, "/mnt/nvme/envs/proj"))
@patch("arasul_tui.commands.project.spinner_run")
def test_create_type_only_prompts_name(mock_spinner, mock_env, mock_mf, state: TuiState):
    """/create --type python-gpu without name prompts for name."""
    result = cmd_create(state, ["--type", "python-gpu"])
    assert result.pending_handler is not None
    assert result.prompt == "Name"


def test_create_existing_project_with_type(state: TuiState):
    """Should fail if project directory already exists."""
    (state.project_root / "existing").mkdir()

    with patch("arasul_tui.commands.project.is_miniforge_installed", return_value=True):
        result = cmd_create(state, ["existing", "--type", "python-gpu"])
    assert result.ok is False


def test_create_invalid_name_with_type(state: TuiState):
    """Invalid project name should fail."""
    result = cmd_create(state, ["../evil", "--type", "python-gpu"])
    assert result.ok is False
