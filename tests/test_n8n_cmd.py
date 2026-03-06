from __future__ import annotations

from unittest.mock import patch

from arasul_tui.commands.n8n_cmd import cmd_n8n
from arasul_tui.core.state import TuiState


def test_n8n_no_args_shows_status(state: TuiState):
    with patch("arasul_tui.commands.n8n_cmd.n8n_is_installed", return_value=False):
        result = cmd_n8n(state, [])
    assert result.ok is True
    assert result.style == "silent"


def test_n8n_status_subcommand(state: TuiState):
    with patch("arasul_tui.commands.n8n_cmd.n8n_is_installed", return_value=False):
        result = cmd_n8n(state, ["status"])
    assert result.ok is True


def test_n8n_unknown_subcommand(state: TuiState):
    result = cmd_n8n(state, ["foobar"])
    assert result.ok is False


def test_n8n_start_not_installed(state: TuiState):
    with patch("arasul_tui.commands.n8n_cmd.n8n_is_installed", return_value=False):
        result = cmd_n8n(state, ["start"])
    assert result.ok is False


def test_n8n_stop_not_installed(state: TuiState):
    with patch("arasul_tui.commands.n8n_cmd.n8n_is_installed", return_value=False):
        result = cmd_n8n(state, ["stop"])
    assert result.ok is False


def test_n8n_start_already_running(state: TuiState):
    with (
        patch("arasul_tui.commands.n8n_cmd.n8n_is_installed", return_value=True),
        patch("arasul_tui.commands.n8n_cmd.n8n_is_running", return_value=True),
    ):
        result = cmd_n8n(state, ["start"])
    assert result.ok is True


def test_n8n_stop_not_running(state: TuiState):
    with (
        patch("arasul_tui.commands.n8n_cmd.n8n_is_installed", return_value=True),
        patch("arasul_tui.commands.n8n_cmd.n8n_is_running", return_value=False),
    ):
        result = cmd_n8n(state, ["stop"])
    assert result.ok is True


def test_n8n_logs_not_installed(state: TuiState):
    with patch("arasul_tui.commands.n8n_cmd.n8n_is_installed", return_value=False):
        result = cmd_n8n(state, ["logs"])
    assert result.ok is False


def test_n8n_workflows_not_running(state: TuiState):
    with patch("arasul_tui.commands.n8n_cmd.n8n_is_running", return_value=False):
        result = cmd_n8n(state, ["workflows"])
    assert result.ok is False


def test_n8n_open(state: TuiState):
    with patch("arasul_tui.commands.n8n_cmd.n8n_is_running", return_value=True):
        result = cmd_n8n(state, ["open"])
    assert result.ok is True


def test_n8n_api_key_wizard(state: TuiState):
    with patch("arasul_tui.commands.n8n_cmd.n8n_get_api_key", return_value=None):
        result = cmd_n8n(state, ["api-key"])
    assert result.ok is True
    assert result.pending_handler is not None
    assert result.wizard_step is not None


def test_n8n_api_key_aliases(state: TuiState):
    for alias in ["apikey", "key"]:
        with patch("arasul_tui.commands.n8n_cmd.n8n_get_api_key", return_value=None):
            result = cmd_n8n(state, [alias])
        assert result.ok is True
        assert result.pending_handler is not None


def test_n8n_mcp_no_api_key(state: TuiState):
    with (
        patch("arasul_tui.commands.n8n_cmd.is_n8n_mcp_configured", return_value=False),
        patch("arasul_tui.commands.n8n_cmd.n8n_get_api_key", return_value=None),
    ):
        result = cmd_n8n(state, ["mcp"])
    assert result.ok is False


def test_n8n_mcp_already_configured(state: TuiState):
    with patch("arasul_tui.commands.n8n_cmd.is_n8n_mcp_configured", return_value=True):
        result = cmd_n8n(state, ["mcp"])
    assert result.ok is True


def test_n8n_mcp_configure_success(state: TuiState):
    with (
        patch("arasul_tui.commands.n8n_cmd.is_n8n_mcp_configured", return_value=False),
        patch("arasul_tui.commands.n8n_cmd.n8n_get_api_key", return_value="test-key"),
        patch("arasul_tui.commands.n8n_cmd.configure_n8n_mcp", return_value=(True, "done")),
    ):
        result = cmd_n8n(state, ["mcp"])
    assert result.ok is True


def test_n8n_mcp_remove(state: TuiState):
    with patch("arasul_tui.commands.n8n_cmd.remove_n8n_mcp", return_value=(True, "removed")):
        result = cmd_n8n(state, ["mcp", "remove"])
    assert result.ok is True


def test_n8n_backup_not_installed(state: TuiState):
    with patch("arasul_tui.commands.n8n_cmd.n8n_is_installed", return_value=False):
        result = cmd_n8n(state, ["backup"])
    assert result.ok is False


def test_n8n_backup_not_running(state: TuiState):
    with (
        patch("arasul_tui.commands.n8n_cmd.n8n_is_installed", return_value=True),
        patch("arasul_tui.commands.n8n_cmd.n8n_is_running", return_value=False),
    ):
        result = cmd_n8n(state, ["backup"])
    assert result.ok is False
