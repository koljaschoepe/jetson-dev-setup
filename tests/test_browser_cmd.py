from __future__ import annotations

from unittest.mock import patch

from arasul_tui.commands.browser_cmd import cmd_browser
from arasul_tui.core.router import REGISTRY
from arasul_tui.core.state import TuiState


def _state() -> TuiState:
    return TuiState(registry=REGISTRY)


def test_browser_status():
    rows = [("Playwright", "[green]\u2713[/green] installed")]
    with patch("arasul_tui.commands.browser_cmd.browser_health", return_value=rows):
        result = cmd_browser(_state(), ["status"])
    assert result.ok is True
    assert result.style == "silent"


def test_browser_test_ok():
    with patch("arasul_tui.commands.browser_cmd.browser_test", return_value=(True, ["OK"])):
        result = cmd_browser(_state(), ["test"])
    assert result.ok is True


def test_browser_test_fail():
    with patch("arasul_tui.commands.browser_cmd.browser_test", return_value=(False, ["Fail"])):
        result = cmd_browser(_state(), ["test"])
    assert result.ok is False


def test_browser_install_ok():
    with (
        patch("arasul_tui.commands.browser_cmd.install_browser", return_value=(True, ["Done"])),
        patch("arasul_tui.commands.browser_cmd.is_mcp_configured", return_value=True),
    ):
        result = cmd_browser(_state(), ["install"])
    assert result.ok is True


def test_browser_install_auto_mcp():
    with (
        patch("arasul_tui.commands.browser_cmd.install_browser", return_value=(True, ["Done"])),
        patch("arasul_tui.commands.browser_cmd.is_mcp_configured", return_value=False),
        patch("arasul_tui.commands.browser_cmd.configure_mcp", return_value=(True, "MCP OK")),
    ):
        result = cmd_browser(_state(), ["install"])
    assert result.ok is True


def test_browser_mcp_already_configured():
    with patch("arasul_tui.commands.browser_cmd.is_mcp_configured", return_value=True):
        result = cmd_browser(_state(), ["mcp"])
    assert result.ok is True


def test_browser_mcp_configure():
    with (
        patch("arasul_tui.commands.browser_cmd.is_mcp_configured", return_value=False),
        patch("arasul_tui.commands.browser_cmd.configure_mcp", return_value=(True, "Configured")),
    ):
        result = cmd_browser(_state(), ["mcp"])
    assert result.ok is True


def test_browser_unknown_subcommand():
    result = cmd_browser(_state(), ["bogus"])
    assert result.ok is False


def test_browser_default_is_status():
    rows = [("Playwright", "[green]\u2713[/green] installed")]
    with patch("arasul_tui.commands.browser_cmd.browser_health", return_value=rows):
        result = cmd_browser(_state(), [])
    assert result.ok is True
    assert result.style == "silent"
