from __future__ import annotations

from pathlib import Path

from arasul_tui.commands import cmd_create, cmd_delete, cmd_open
from arasul_tui.core.state import TuiState


def test_open_no_args(state_with_projects: TuiState):
    result = cmd_open(state_with_projects, [])
    assert result.ok is False


def test_open_existing_project(state_with_projects: TuiState):
    result = cmd_open(state_with_projects, ["alpha"])
    assert result.ok is True
    assert state_with_projects.active_project is not None
    assert state_with_projects.active_project.name == "alpha"


def test_open_nonexistent_project(state_with_projects: TuiState):
    result = cmd_open(state_with_projects, ["nonexistent"])
    assert result.ok is False


def test_open_root_not_found(state: TuiState):
    state.project_root = Path("/nonexistent/path")
    result = cmd_open(state, ["test"])
    assert result.ok is False


def test_create_with_name(state: TuiState):
    result = cmd_create(state, ["new-project"])
    assert result.ok is True
    assert (state.project_root / "new-project").exists()
    assert state.active_project is not None


def test_create_duplicate(state_with_projects: TuiState):
    result = cmd_create(state_with_projects, ["alpha"])
    assert result.ok is False


def test_create_wizard(state: TuiState):
    result = cmd_create(state, [])
    assert result.ok is True
    assert result.pending_handler is not None
    assert result.wizard_step is not None


def test_delete_no_projects(state: TuiState):
    result = cmd_delete(state, [])
    assert result.ok is False
