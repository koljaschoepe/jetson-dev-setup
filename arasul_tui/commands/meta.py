from __future__ import annotations

from arasul_tui.core.state import TuiState
from arasul_tui.core.types import CommandResult
from arasul_tui.core.ui import console, content_pad

# ---------------------------------------------------------------------------
# /help (categorized, clean)
# ---------------------------------------------------------------------------


def cmd_help(_: TuiState, __: list[str]) -> CommandResult:
    pad = content_pad()
    console.print()

    console.print(f"{pad}[bold]Shortcuts[/bold]", highlight=False)
    console.print(f"{pad}  [cyan]1-9[/cyan]  Select project", highlight=False)
    console.print(f"{pad}  [cyan]n[/cyan]    New project", highlight=False)
    console.print(f"{pad}  [cyan]d[/cyan]    Delete project", highlight=False)
    console.print(f"{pad}  [cyan]c[/cyan]    Start Claude Code", highlight=False)
    console.print(f"{pad}  [cyan]g[/cyan]    Start lazygit", highlight=False)
    console.print(f"{pad}  [cyan]b[/cyan]    Back to overview", highlight=False)
    console.print()

    console.print(f"{pad}[bold]Projects[/bold]", highlight=False)
    console.print(f"{pad}  [cyan]/open <name>[/cyan]   Open project", highlight=False)
    console.print(f"{pad}  [cyan]/create[/cyan]        Create new project", highlight=False)
    console.print(f"{pad}  [cyan]/clone[/cyan]         Clone GitHub repo", highlight=False)
    console.print(f"{pad}  [cyan]/delete[/cyan]        Delete project", highlight=False)
    console.print(f"{pad}  [cyan]/info[/cyan]          Project details", highlight=False)
    console.print(f"{pad}  [cyan]/repos[/cyan]         All projects", highlight=False)
    console.print()

    console.print(f"{pad}[bold]Claude Code[/bold]", highlight=False)
    console.print(f"{pad}  [cyan]/claude[/cyan]        Start Claude Code", highlight=False)
    console.print(f"{pad}  [cyan]/auth[/cyan]          Auth & tools status", highlight=False)
    console.print()

    console.print(f"{pad}[bold]Git[/bold]", highlight=False)
    console.print(f"{pad}  [cyan]/git[/cyan]           GitHub setup", highlight=False)
    console.print(f"{pad}  [cyan]/git pull[/cyan]      Pull current project", highlight=False)
    console.print(f"{pad}  [cyan]/git push[/cyan]      Push current project", highlight=False)
    console.print(f"{pad}  [cyan]/git log[/cyan]       Last 10 commits", highlight=False)
    console.print()

    console.print(f"{pad}[bold]System[/bold]", highlight=False)
    console.print(f"{pad}  [cyan]/status[/cyan]        System status", highlight=False)
    console.print(f"{pad}  [cyan]/health[/cyan]        Health diagnostic", highlight=False)
    console.print(f"{pad}  [cyan]/setup[/cyan]         Setup wizard", highlight=False)
    console.print(f"{pad}  [cyan]/docker[/cyan]        Container status", highlight=False)
    console.print()

    console.print(f"{pad}[bold]Security[/bold]", highlight=False)
    console.print(f"{pad}  [cyan]/keys[/cyan]          SSH keys", highlight=False)
    console.print(f"{pad}  [cyan]/logins[/cyan]        Recent SSH logins", highlight=False)
    console.print(f"{pad}  [cyan]/security[/cyan]      Security audit", highlight=False)
    console.print()

    console.print(f"{pad}[bold]Browser & MCP[/bold]", highlight=False)
    console.print(f"{pad}  [cyan]/browser[/cyan]       Browser management", highlight=False)
    console.print(f"{pad}  [cyan]/mcp[/cyan]           MCP servers", highlight=False)
    console.print()

    console.print(f"{pad}  [cyan]/help[/cyan]          This help", highlight=False)
    console.print(f"{pad}  [cyan]/exit[/cyan]          Quit", highlight=False)
    console.print()
    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /exit
# ---------------------------------------------------------------------------


def cmd_exit(_: TuiState, __: list[str]) -> CommandResult:
    pad = content_pad()
    console.print(f"{pad}[dim]Goodbye.[/dim]", highlight=False)
    return CommandResult(ok=True, quit_app=True, style="silent")
