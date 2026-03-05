from __future__ import annotations

import json

from arasul_tui.core.constants import CLAUDE_JSON
from arasul_tui.core.shell import run_cmd
from arasul_tui.core.state import TuiState
from arasul_tui.core.types import CommandResult
from arasul_tui.core.ui import (
    print_error,
    print_info,
    print_styled_panel,
    print_success,
)


def _load_claude_json() -> dict:
    """Load ~/.claude.json, returning empty dict on failure."""
    try:
        if CLAUDE_JSON.exists():
            return json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_claude_json(data: dict) -> None:
    """Write ~/.claude.json."""
    CLAUDE_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def cmd_mcp(state: TuiState, args: list[str]) -> CommandResult:
    """MCP server management."""
    sub = args[0] if args else "list"

    if sub == "list":
        data = _load_claude_json()
        servers = data.get("mcpServers", {})
        if not servers:
            print_info("No MCP servers configured.")
            return CommandResult(ok=True, style="silent")

        rows: list[tuple[str, str]] = []
        for name, config in servers.items():
            cmd = config.get("command", "?")
            cmd_args = " ".join(config.get("args", []))
            rows.append((name, f"{cmd} {cmd_args}"))

        print_styled_panel("MCP Servers", rows)
        return CommandResult(ok=True, style="silent")

    if sub == "add":
        if len(args) < 3:
            print_error("Usage: [bold]/mcp add <name> <command> [args...][/bold]")
            return CommandResult(ok=False, style="silent")

        name = args[1]
        command = args[2]
        cmd_args = args[3:] if len(args) > 3 else []

        data = _load_claude_json()
        if "mcpServers" not in data:
            data["mcpServers"] = {}

        data["mcpServers"][name] = {
            "command": command,
            "args": cmd_args,
        }
        _save_claude_json(data)
        print_success(f"MCP server added: [bold]{name}[/bold]")
        return CommandResult(ok=True, style="silent")

    if sub == "test":
        name = args[1] if len(args) > 1 else None
        data = _load_claude_json()
        servers = data.get("mcpServers", {})

        if not servers:
            print_info("No MCP servers configured.")
            return CommandResult(ok=True, style="silent")

        if name and name not in servers:
            print_error(f"MCP server not found: [bold]{name}[/bold]")
            return CommandResult(ok=False, style="silent")

        targets = {name: servers[name]} if name else servers
        rows: list[tuple[str, str]] = []
        for srv_name, config in targets.items():
            cmd = config.get("command", "")
            check = run_cmd(f"command -v {cmd} 2>/dev/null", timeout=3)
            if check and not check.startswith("Error"):
                rows.append((srv_name, f"[green]✓[/green] {cmd} found"))
            else:
                rows.append((srv_name, f"[red]✗[/red] {cmd} not found"))

        print_styled_panel("MCP Server Check", rows)
        return CommandResult(ok=True, style="silent")

    if sub == "remove":
        if len(args) < 2:
            print_error("Usage: [bold]/mcp remove <name>[/bold]")
            return CommandResult(ok=False, style="silent")

        name = args[1]
        data = _load_claude_json()
        servers = data.get("mcpServers", {})
        if name not in servers:
            print_error(f"MCP server not found: [bold]{name}[/bold]")
            return CommandResult(ok=False, style="silent")

        del servers[name]
        _save_claude_json(data)
        print_success(f"MCP server removed: [bold]{name}[/bold]")
        return CommandResult(ok=True, style="silent")

    print_error(f"Unknown subcommand: [bold]{sub}[/bold]")
    print_info("Available: [bold]list[/bold], [bold]add[/bold], [bold]test[/bold], [bold]remove[/bold]")
    return CommandResult(ok=False, style="silent")
