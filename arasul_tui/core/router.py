from __future__ import annotations

import shlex

from arasul_tui import commands
from arasul_tui.core.registry import CommandRegistry, CommandSpec
from arasul_tui.core.state import TuiState
from arasul_tui.core.types import CommandResult


def build_registry() -> CommandRegistry:
    reg = CommandRegistry()
    reg.register(CommandSpec("help", commands.cmd_help, "Show help"))
    reg.register(CommandSpec("open", commands.cmd_open, "Open project"))
    reg.register(CommandSpec("create", commands.cmd_create, "Create project"))
    reg.register(CommandSpec("clone", commands.cmd_clone, "Clone repo"))
    reg.register(CommandSpec("status", commands.cmd_status, "System status"))
    reg.register(CommandSpec("claude", commands.cmd_claude, "Start Claude"))
    reg.register(CommandSpec("codex", commands.cmd_codex, "Start Codex"))
    reg.register(CommandSpec("git", commands.cmd_git, "GitHub setup"))
    reg.register(CommandSpec("browser", commands.cmd_browser, "Headless browser"))
    reg.register(CommandSpec("delete", commands.cmd_delete, "Delete project"))
    reg.register(CommandSpec("exit", commands.cmd_exit, "Quit"))
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
            print_info(f"Did you mean [cyan bold]/{prefixes[0]}[/cyan bold]? [dim](Tab to accept)[/dim]")
        else:
            print_error(f"Unknown: [bold]/{cmd}[/bold]")
            print_info("Type [bold]/help[/bold] for all commands.")
        return CommandResult(ok=False, style="silent")

    return spec.handler(state, args)


def complete_command(line: str) -> list[str]:
    return REGISTRY.complete(line)
