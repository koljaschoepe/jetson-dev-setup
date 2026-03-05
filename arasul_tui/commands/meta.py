from __future__ import annotations

from arasul_tui.core.state import Screen, TuiState
from arasul_tui.core.theme import DIM, PRIMARY
from arasul_tui.core.types import CommandResult
from arasul_tui.core.ui import console, content_pad


def _get_registry():
    """Lazy import to avoid circular dependency."""
    from arasul_tui.core.router import REGISTRY

    return REGISTRY

# Box characters
_CORNER_TL = "\u256d"  # ╭
_CORNER_TR = "\u256e"  # ╮
_CORNER_BL = "\u2570"  # ╰
_CORNER_BR = "\u256f"  # ╯
_VLINE = "\u2502"      # │
_HLINE = "\u2500"      # ─
_DOT = "\u00b7"        # ·


def _box(title: str, rows: list[str], pad: str, width: int = 44) -> None:
    """Print a rounded box section with title and content rows."""
    inner_w = width - 2
    title_seg = f" {title} "
    left_bar = _HLINE * 2
    right_bar = _HLINE * max(1, inner_w - len(title_seg) - 2)
    console.print(
        f"{pad}[{DIM}]{_CORNER_TL}{left_bar}[/{DIM}]"
        f" [{PRIMARY}]{title}[/{PRIMARY}] "
        f"[{DIM}]{right_bar}{_CORNER_TR}[/{DIM}]",
        highlight=False,
    )
    for row in rows:
        console.print(f"{pad}[{DIM}]{_VLINE}[/{DIM}]  {row}", highlight=False)
    console.print(f"{pad}[{DIM}]{_CORNER_BL}{_HLINE * inner_w}{_CORNER_BR}[/{DIM}]", highlight=False)


# ---------------------------------------------------------------------------
# /help (contextual, visual)
# ---------------------------------------------------------------------------


def _cmd_detail(name: str, pad: str) -> bool:
    """Show detailed help for a single command. Returns True if found."""
    reg = _get_registry()
    spec = reg.get(name.lower())
    if not spec:
        # Try alias
        for s in reg.specs():
            if name.lower() in [a.lower() for a in s.aliases]:
                spec = s
                break
    if not spec:
        return False

    console.print()
    console.print(f"{pad}[bold {PRIMARY}]{spec.name}[/bold {PRIMARY}]  [{DIM}]{spec.help_text}[/{DIM}]", highlight=False)
    console.print()

    if spec.aliases:
        aliases = ", ".join(spec.aliases)
        console.print(f"{pad}  [{DIM}]Aliases:[/{DIM}]  {aliases}", highlight=False)

    if spec.subcommands:
        console.print(f"{pad}  [{DIM}]Subcommands:[/{DIM}]", highlight=False)
        for sub, desc in spec.subcommands.items():
            console.print(f"{pad}    [{PRIMARY}]{spec.name} {sub}[/{PRIMARY}]  [{DIM}]{desc}[/{DIM}]", highlight=False)

    console.print(f"{pad}  [{DIM}]Slash:[/{DIM}]  /{spec.name}", highlight=False)
    console.print()
    return True


def _help_main(pad: str) -> None:
    """Full help for main screen."""
    console.print()

    # Quick start
    rows = [
        "Just type what you want. No slash needed.",
        f"[{DIM}]Examples: status, new, health, clone, docker[/{DIM}]",
        f"[{DIM}]Tab for autocomplete. Type a project name to open it.[/{DIM}]",
    ]
    _box("Quick Start", rows, pad)
    console.print()

    # Shortcuts
    rows = [
        f"[{PRIMARY}]1-9[/{PRIMARY}]  Select project    [{PRIMARY}]n[/{PRIMARY}]  New project",
        f"[{PRIMARY}]d[/{PRIMARY}]    Delete project    [{PRIMARY}]b[/{PRIMARY}]  Back to overview",
    ]
    _box("Shortcuts", rows, pad)
    console.print()

    # Commands by category
    cats = _get_registry().categories()
    # Define display order
    order = ["Projects", "Claude Code", "Git", "System", "Security", "Browser", "MCP", "Network", "Meta"]
    for cat in order:
        specs = cats.get(cat, [])
        if not specs:
            continue
        rows = []
        for spec in specs:
            alias_hint = ""
            if spec.aliases:
                top = spec.aliases[0]
                alias_hint = f"  [{DIM}]({top})[/{DIM}]"
            rows.append(f"[{PRIMARY}]{spec.name:<10}[/{PRIMARY}]{spec.help_text}{alias_hint}")
        _box(cat, rows, pad)
        console.print()

    console.print(f"{pad}[{DIM}]Slash commands (/status, /help) also work.[/{DIM}]", highlight=False)
    console.print(f"{pad}[{DIM}]Try: help <command> for details.[/{DIM}]", highlight=False)
    console.print()


def _help_project(pad: str) -> None:
    """Context-aware help when a project is open."""
    console.print()

    # Project shortcuts first
    rows = [
        f"[{PRIMARY}]c[/{PRIMARY}]  Start Claude Code in this project",
        f"[{PRIMARY}]g[/{PRIMARY}]  Open lazygit for this project",
        f"[{PRIMARY}]b[/{PRIMARY}]  Back to project overview",
    ]
    _box("Project Shortcuts", rows, pad)
    console.print()

    # Project commands
    rows = [
        f"[{PRIMARY}]info[/{PRIMARY}]     Project details",
        f"[{PRIMARY}]pull[/{PRIMARY}]     Pull latest changes",
        f"[{PRIMARY}]push[/{PRIMARY}]     Push changes",
        f"[{PRIMARY}]git log[/{PRIMARY}]  Recent commits",
        f"[{PRIMARY}]delete[/{PRIMARY}]   Delete this project",
    ]
    _box("Project Commands", rows, pad)
    console.print()

    # Other commands (compact)
    rows = [
        f"[{PRIMARY}]status[/{PRIMARY}]  System  {_DOT}  [{PRIMARY}]health[/{PRIMARY}]  Diagnostics  {_DOT}  [{PRIMARY}]docker[/{PRIMARY}]  Containers",
        f"[{PRIMARY}]repos[/{PRIMARY}]   All projects  {_DOT}  [{PRIMARY}]help[/{PRIMARY}]  Full help",
    ]
    _box("Also Available", rows, pad)
    console.print()

    console.print(f"{pad}[{DIM}]Type any command or 'b' to go back.[/{DIM}]", highlight=False)
    console.print()


def cmd_help(state: TuiState, args: list[str]) -> CommandResult:
    pad = content_pad()

    # help <command> — show single command detail
    if args:
        found = _cmd_detail(args[0], pad)
        if not found:
            console.print(f"{pad}[{DIM}]Unknown command: {args[0]}. Try 'help' for all commands.[/{DIM}]", highlight=False)
        return CommandResult(ok=True, style="silent")

    # Context-aware help
    if state.screen == Screen.PROJECT or state.active_project:
        _help_project(pad)
    else:
        _help_main(pad)

    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /exit
# ---------------------------------------------------------------------------


def cmd_exit(_: TuiState, __: list[str]) -> CommandResult:
    pad = content_pad()
    console.print(f"{pad}[{DIM}]See you later. System standing by.[/{DIM}]", highlight=False)
    return CommandResult(ok=True, quit_app=True, style="silent")
