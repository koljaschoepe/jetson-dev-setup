from __future__ import annotations

import shlex

from arasul_tui.commands import (
    cmd_auth,
    cmd_browser,
    cmd_claude,
    cmd_clone,
    cmd_create,
    cmd_delete,
    cmd_docker,
    cmd_exit,
    cmd_git,
    cmd_health,
    cmd_help,
    cmd_info,
    cmd_keys,
    cmd_logins,
    cmd_mcp,
    cmd_open,
    cmd_repos,
    cmd_security,
    cmd_setup,
    cmd_status,
    cmd_tailscale,
)
from arasul_tui.core.registry import CommandRegistry, CommandSpec
from arasul_tui.core.state import TuiState
from arasul_tui.core.types import CommandResult


def build_registry() -> CommandRegistry:
    reg = CommandRegistry()

    # Projects
    reg.register(CommandSpec("open", cmd_open, "Open project", category="Projects"))
    reg.register(CommandSpec("create", cmd_create, "Create project", category="Projects"))
    reg.register(CommandSpec("clone", cmd_clone, "Clone repo", category="Projects"))
    reg.register(CommandSpec("delete", cmd_delete, "Delete project", category="Projects"))
    reg.register(CommandSpec("info", cmd_info, "Project details", category="Projects"))
    reg.register(CommandSpec("repos", cmd_repos, "All projects", category="Projects"))

    # Claude Code
    reg.register(CommandSpec("claude", cmd_claude, "Start Claude", category="Claude Code"))
    reg.register(CommandSpec("auth", cmd_auth, "Auth & tools", category="Claude Code"))

    # Git
    reg.register(
        CommandSpec(
            "git",
            cmd_git,
            "GitHub setup / git ops",
            category="Git",
            subcommands={
                "pull": "Pull project",
                "push": "Push project",
                "log": "Recent commits",
                "status": "Working tree",
            },
        )
    )

    # System
    reg.register(CommandSpec("status", cmd_status, "System status", category="System"))
    reg.register(CommandSpec("health", cmd_health, "Health diagnostic", category="System"))
    reg.register(CommandSpec("setup", cmd_setup, "Setup wizard", category="System"))
    reg.register(CommandSpec("docker", cmd_docker, "Container status", category="System"))

    # Security
    reg.register(CommandSpec("keys", cmd_keys, "SSH keys", category="Security"))
    reg.register(CommandSpec("logins", cmd_logins, "Recent logins", category="Security"))
    reg.register(CommandSpec("security", cmd_security, "Security audit", category="Security"))

    # Browser
    reg.register(
        CommandSpec(
            "browser",
            cmd_browser,
            "Headless browser",
            category="Browser",
            subcommands={
                "status": "Health check",
                "test": "Connection test",
                "install": "Install/update",
                "mcp": "Configure MCP",
            },
        )
    )

    # MCP
    reg.register(
        CommandSpec(
            "mcp",
            cmd_mcp,
            "MCP servers",
            category="MCP",
            subcommands={
                "list": "List servers",
                "add": "Add server",
                "test": "Test servers",
                "remove": "Remove server",
            },
        )
    )

    # Network
    reg.register(
        CommandSpec(
            "tailscale",
            cmd_tailscale,
            "VPN remote access",
            category="Network",
            subcommands={
                "status": "Connection status",
                "install": "Install Tailscale",
                "up": "Connect",
                "down": "Disconnect",
            },
        )
    )

    # Meta
    reg.register(CommandSpec("help", cmd_help, "Show help", category="Meta"))
    reg.register(CommandSpec("exit", cmd_exit, "Quit", category="Meta"))

    return reg


REGISTRY = build_registry()


def run_command(state: TuiState, raw: str) -> CommandResult:
    text = raw.strip()
    if not text:
        return CommandResult(ok=True, style="silent")

    if not text.startswith("/"):
        from arasul_tui.core.ui import print_warning

        print_warning(f"Unknown: [bold]{text}[/bold] — type [bold]/help[/bold] or select by number.")
        return CommandResult(ok=False, style="silent")

    try:
        parts = shlex.split(text[1:])
    except ValueError as exc:
        from arasul_tui.core.ui import print_error

        print_error(f"Parse error: {exc}")
        return CommandResult(ok=False, style="silent")

    if not parts:
        return CommandResult(ok=True, style="silent")

    cmd, args = parts[0].lower(), parts[1:]

    spec = REGISTRY.get(cmd)
    if not spec:
        from arasul_tui.core.ui import print_error, print_info

        prefixes = [name for name in REGISTRY.names() if name.startswith(cmd)]
        if len(prefixes) == 1:
            print_error(f"Unknown: [bold]/{cmd}[/bold]")
            print_info(f"Did you mean [cyan bold]/{prefixes[0]}[/cyan bold]? [dim](Tab to complete)[/dim]")
        else:
            print_error(f"Unknown: [bold]/{cmd}[/bold]")
            print_info("Type [bold]/help[/bold] for all commands.")
        return CommandResult(ok=False, style="silent")

    return spec.handler(state, args)
