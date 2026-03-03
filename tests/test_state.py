from __future__ import annotations

from pathlib import Path

from arasul_tui.core.state import DEFAULT_PROJECT_ROOT, TuiState


def test_default_state():
    state = TuiState()
    assert state.active_project is None
    assert state.active_provider is None
    assert state.project_root == DEFAULT_PROJECT_ROOT
    assert state.first_run is True


def test_state_custom_root(tmp_path: Path):
    state = TuiState(project_root=tmp_path)
    assert state.project_root == tmp_path


def test_state_active_project(tmp_path: Path):
    state = TuiState()
    project = tmp_path / "my-project"
    project.mkdir()
    state.active_project = project
    assert state.active_project == project
    assert state.active_project.name == "my-project"
