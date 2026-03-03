from __future__ import annotations

import shlex

from arasul_tui.core.registry import CommandRegistry, CommandSpec
from arasul_tui.core.state import TuiState
from arasul_tui.core.types import CommandResult
from arasul_tui import commands


def build_registry() -> CommandRegistry:
    reg = CommandRegistry()
    reg.register(CommandSpec("help", commands.cmd_help, "Hilfe"))
    reg.register(CommandSpec("open", commands.cmd_open, "Projekt oeffnen"))
    reg.register(CommandSpec("create", commands.cmd_create, "Projekt erstellen"))
    reg.register(CommandSpec("clone", commands.cmd_clone, "Repo klonen"))
    reg.register(CommandSpec("status", commands.cmd_status, "Systemstatus"))
    reg.register(CommandSpec("claude", commands.cmd_claude, "Claude starten"))
    reg.register(CommandSpec("codex", commands.cmd_codex, "Codex starten"))
    reg.register(CommandSpec("git", commands.cmd_git, "GitHub Setup"))
    reg.register(CommandSpec("browser", commands.cmd_browser, "Headless Browser"))
    reg.register(CommandSpec("exit", commands.cmd_exit, "TUI beenden"))
    return reg


REGISTRY = build_registry()


def run_command(state: TuiState, raw: str) -> CommandResult:
    text = raw.strip()
    if not text:
        return CommandResult(ok=True, style="silent")

    if not text.startswith("/"):
        from arasul_tui.core.ui import print_warning
        print_warning("Tippe [bold]/help[/bold] fuer Befehle oder waehle ein Projekt per Nummer.")
        return CommandResult(ok=False, style="silent")

    try:
        parts = shlex.split(text[1:])
    except ValueError as exc:
        from arasul_tui.core.ui import print_error
        print_error(f"Parser-Fehler: {exc}")
        return CommandResult(ok=False, style="silent")

    if not parts:
        return CommandResult(ok=True, style="silent")

    cmd, args = parts[0].lower(), parts[1:]

    spec = REGISTRY.get(cmd)
    if not spec:
        from arasul_tui.core.ui import print_error, print_info
        prefixes = [name for name in REGISTRY.names() if name.startswith(cmd)]
        if len(prefixes) == 1:
            print_error(f"Unbekannt: [bold]/{cmd}[/bold]")
            print_info(f"Meintest du [cyan bold]/{prefixes[0]}[/cyan bold]? [dim](Tab zum Uebernehmen)[/dim]")
        else:
            print_error(f"Unbekannt: [bold]/{cmd}[/bold]")
            print_info("Tippe [bold]/help[/bold] fuer alle Commands.")
        return CommandResult(ok=False, style="silent")

    return spec.handler(state, args)


def complete_command(line: str) -> list[str]:
    return REGISTRY.complete(line)
