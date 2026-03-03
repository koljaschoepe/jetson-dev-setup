from __future__ import annotations

import subprocess
import socket
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Any

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner

if TYPE_CHECKING:
    from arasul_tui.core.state import TuiState
    from arasul_tui.core.types import CommandResult

console = Console()

VERSION = "v0.1.0"
MAX_WIDTH = 84
MIN_WIDTH = 72

ARASUL_TEXT = [
    " ████  █████   ████   ████  ██  ██ ██",
    "██  ██ ██  ██ ██  ██ ██  ██ ██  ██ ██",
    "██  ██ ██  ██ ██  ██ ██     ██  ██ ██",
    "██████ █████  ██████  ████  ██  ██ ██",
    "██  ██ ██ ██  ██  ██     ██ ██  ██ ██",
    "██  ██ ██  ██ ██  ██ ██  ██ ██  ██ ██",
    "██  ██ ██  ██ ██  ██  ████   ████  ██████",
]


def _quick_run(cmd: str, timeout: int = 3) -> str:
    try:
        r = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or r.stderr or "").strip()
    except Exception:
        return ""


def _github_status() -> str:
    auth = _quick_run("gh auth status 2>&1", timeout=4)
    if "Logged in" not in auth:
        return "[dim]nicht verbunden[/dim]"
    for line in auth.splitlines():
        if "account" in line.lower():
            parts = line.strip().split()
            for i, p in enumerate(parts):
                if p == "account" and i + 1 < len(parts):
                    return f"[green]✓[/green] {parts[i + 1]}"
    return "[green]✓[/green]"


def _system_info() -> list[str]:
    """Compact system info lines."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        ram = f"{vm.used // (1024*1024)}M / {vm.total // (1024*1024)}M"
    except Exception:
        ram = _quick_run("free -m | awk '/^Mem:/{printf \"%dM / %dM\", $3, $2}'") or "n/a"

    disk = _quick_run("df -h /mnt/nvme 2>/dev/null | awk 'NR==2{print $3\"/\"$2}'")
    if not disk:
        disk = _quick_run("df -h / | awk 'NR==2{print $3\"/\"$2}'") or "n/a"

    temp = _quick_run("cat /sys/devices/virtual/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.0f\", $1/1000}'")
    temp_str = f"{temp}°C" if temp and temp.isdigit() else ""

    power = _quick_run("sudo nvpmodel -q 2>/dev/null | head -1 | sed 's/NV Power Mode: //'") or ""

    power_temp = [p for p in [power, temp_str] if p]

    ip = _quick_run("hostname -I 2>/dev/null | awk '{print $1}'") or "n/a"

    return [
        "Jetson Orin Nano Super",
        " [dim]·[/dim] ".join(power_temp) if power_temp else "",
        ip,
        f"RAM {ram} [dim]·[/dim] Disk {disk}",
    ]


def project_list() -> list[str]:
    from arasul_tui.core.state import DEFAULT_PROJECT_ROOT
    try:
        return sorted([p.name for p in DEFAULT_PROJECT_ROOT.iterdir() if p.is_dir()], key=str.lower)
    except Exception:
        return []


def _project_detail(name: str) -> str:
    """Return short git info for a project (remote + branch)."""
    from arasul_tui.core.state import DEFAULT_PROJECT_ROOT
    project = DEFAULT_PROJECT_ROOT / name
    if not (project / ".git").exists():
        return "[dim]lokal[/dim]"
    url = _quick_run(f"git -C {project} remote get-url origin 2>/dev/null")
    branch = _quick_run(f"git -C {project} symbolic-ref --short HEAD 2>/dev/null") or ""
    if not url:
        parts = ["[dim]lokal[/dim]"]
    elif "github" in url:
        parts = ["github"]
    else:
        parts = ["git"]
    if branch:
        parts.append(f"[dim]{branch}[/dim]")
    return " [dim]·[/dim] ".join(parts)


def _git_info_short(project: Path | None) -> str:
    if not project or not (project / ".git").exists():
        return ""
    url = _quick_run(f"git -C {project} remote get-url origin 2>/dev/null")
    if not url:
        return "[dim]lokal[/dim]"
    host = "github" if "github" in url else "git"
    branch = _quick_run(f"git -C {project} symbolic-ref --short HEAD 2>/dev/null")
    if branch:
        return f"[dim]{host} · {branch}[/dim]"
    return f"[dim]{host}[/dim]"


def _adaptive_width() -> int:
    """Calculate optimal panel width based on terminal size with margins."""
    return max(MIN_WIDTH, min(console.width - 4, MAX_WIDTH))


def _vis_len(s: str) -> int:
    """Visible cell width of a string that may contain Rich markup."""
    return Text.from_markup(s).cell_len


def _pad_right(s: str, target: int) -> str:
    """Pad a Rich markup string to target visible width with trailing spaces."""
    diff = target - _vis_len(s)
    return s + " " * diff if diff > 0 else s


def _build_logo_lines() -> list[str]:
    """Build centered ARASUL text block with version."""
    lines = list(ARASUL_TEXT)
    text_w = max(len(line) for line in ARASUL_TEXT)
    lines.append(f"{VERSION:>{text_w}}")
    return lines


def _build_info_lines(state: TuiState, content_w: int) -> list[str]:
    """Build two-column layout: system info (left) + projects (right)."""
    left = list(_system_info())
    left.append(f"GitHub: {_github_status()}")

    right = ["[bold]Projekte[/bold]"]
    projects = project_list()
    for i, name in enumerate(projects, 1):
        detail = _project_detail(name)
        right.append(f" [cyan]{i}[/cyan]  {name}  {detail}")
    if not projects:
        right.append(" [dim]Keine Projekte[/dim]")
    right.append(f" [cyan]\\[n][/cyan]  Neues Projekt")
    right.append("")
    right.append("[bold]Quick Start[/bold]")
    right.append(" [dim]/open <name>[/dim]  Projekt oeffnen")
    right.append(" [dim]/claude[/dim]       Claude starten")
    right.append(" [dim]/help[/dim]         Alle Befehle")

    left_w = (content_w - 3) // 2
    right_w = content_w - 3 - left_w

    max_h = max(len(left), len(right))
    left += [""] * (max_h - len(left))
    right += [""] * (max_h - len(right))

    return [
        f"{_pad_right(l, left_w)} [dim]│[/dim] {_pad_right(r, right_w)}"
        for l, r in zip(left, right)
    ]


def print_header(state: TuiState, full: bool = True) -> None:
    if not full:
        parts: list[str] = []
        if state.active_project:
            name = state.active_project.name
            parts.append(f"[bold]{name}[/bold]")
            gi = _git_info_short(state.active_project)
            if gi:
                parts.append(gi)
        else:
            parts.append("[dim]kein Projekt[/dim]")
        title = " [dim]·[/dim] ".join(parts)
        console.print()
        console.print(Rule(title, style="dim"))
        console.print()
        return

    w = _adaptive_width()
    content_w = w - 6
    bar = "═" * (w - 6)
    sep = "─" * content_w

    logo_lines = _build_logo_lines()
    info_lines = _build_info_lines(state, content_w)

    frame: list[str] = []
    empty = " " * content_w

    frame.append(f"[cyan]╔═╦{bar}╦═╗[/cyan]")
    frame.append(f"[cyan]║ ╚{bar}╝ ║[/cyan]")

    logo_w = max(len(l) for l in logo_lines)
    for line in logo_lines:
        left_pad = (content_w - logo_w) // 2
        padded = " " * left_pad + line.ljust(logo_w)
        padded = padded.ljust(content_w)
        frame.append(f"[cyan]║[/cyan]  [bold cyan]{padded}[/bold cyan]  [cyan]║[/cyan]")

    frame.append(f"[cyan]║[/cyan]  [dim]{sep}[/dim]  [cyan]║[/cyan]")

    for line in info_lines:
        frame.append(f"[cyan]║[/cyan]  {_pad_right(line, content_w)}  [cyan]║[/cyan]")

    frame.append(f"[cyan]║ ╔{bar}╗ ║[/cyan]")
    frame.append(f"[cyan]╚═╩{bar}╩═╝[/cyan]")

    console.print()
    for line in frame:
        console.print(line, justify="center", highlight=False)
    console.print()


def print_project_menu(state: TuiState) -> None:
    """Show action menu after selecting a project."""
    name = state.active_project.name if state.active_project else "?"
    gi = _git_info_short(state.active_project)
    title_parts = [f"[bold]{name}[/bold]"]
    if gi:
        title_parts.append(gi)
    title = " [dim]·[/dim] ".join(title_parts)

    console.print()
    console.print(Rule(title, style="dim"))
    console.print()
    console.print("  [dim]Was moechtest du tun?[/dim]", highlight=False)
    console.print()
    console.print("  [bold cyan]\\[c][/bold cyan]  Claude Code starten", highlight=False)
    console.print("  [bold cyan]\\[x][/bold cyan]  Codex starten", highlight=False)
    console.print("  [bold cyan]\\[b][/bold cyan]  Zurueck zur Uebersicht", highlight=False)
    console.print()


def print_result(result: CommandResult) -> None:
    if not result.lines:
        return

    style = getattr(result, "style", None)

    if style == "silent":
        return

    if style == "success":
        for line in result.lines:
            console.print(f"  [green]{line}[/green]", highlight=False)
    elif style == "error":
        for line in result.lines:
            console.print(f"  [red]{line}[/red]", highlight=False)
    elif style == "panel":
        text = "\n".join(result.lines)
        console.print(Panel(text, border_style="dim", padding=(0, 2)))
    elif style == "wizard":
        for line in result.lines:
            console.print(f"  {line}", highlight=False)
    else:
        ok = result.ok
        for line in result.lines:
            if not ok and line and not line.startswith(" "):
                console.print(f"  [red]{line}[/red]", highlight=False)
            else:
                console.print(f"  {line}", highlight=False)


def print_step(current: int, total: int, title: str) -> None:
    label = f"[bold]{title}[/bold] [dim]· Schritt {current}/{total}[/dim]"
    console.print()
    console.print(Rule(label, style="cyan"))
    console.print()


def print_success(msg: str) -> None:
    console.print(f"  [green]✓[/green] {msg}", highlight=False)


def print_error(msg: str) -> None:
    console.print(f"  [red]✗[/red] {msg}", highlight=False)


def print_info(msg: str) -> None:
    console.print(f"  [cyan]→[/cyan] {msg}", highlight=False)


def print_warning(msg: str) -> None:
    console.print(f"  [yellow]![/yellow] {msg}", highlight=False)


def print_kv(data: list[tuple[str, str]], title: str | None = None) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    table.add_column(style="bold", no_wrap=True)
    table.add_column()
    for k, v in data:
        table.add_row(k, v)
    if title:
        console.print(Panel(table, title=f"[bold]{title}[/bold]", border_style="dim", padding=(0, 1)))
    else:
        console.print(table)


def print_table(rows: list[tuple[str, str]], title: str | None = None) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    table.add_column(style="cyan bold", no_wrap=True)
    table.add_column(style="dim")
    for cmd, desc in rows:
        table.add_row(cmd, desc)
    if title:
        console.print(Panel(table, title=f"[bold]{title}[/bold]", border_style="dim", padding=(0, 1)))
    else:
        console.print(table)


def spinner_run(msg: str, func: Callable[[], Any]) -> Any:
    result = None
    error = None

    def _worker() -> None:
        nonlocal result, error
        try:
            result = func()
        except Exception as exc:
            error = exc

    t = threading.Thread(target=_worker)
    t.start()

    sp = Spinner("dots", text=f"  {msg}", style="cyan")
    with Live(sp, console=console, refresh_per_second=10, transient=True):
        while t.is_alive():
            time.sleep(0.1)

    if error:
        raise error
    return result


def _frame_left_pad() -> int:
    """Left padding to align content with the centered frame."""
    w = _adaptive_width()
    return max(0, (console.width - w) // 2)


def print_separator() -> None:
    """Print a thin separator line aligned with the frame."""
    w = _adaptive_width()
    pad = " " * _frame_left_pad()
    console.print(f"{pad}{'─' * (w - 2)}", style="dim", highlight=False)


def build_prompt(state: TuiState, wizard_step: tuple[int, int, str] | None = None) -> str:
    """Returns prompt_toolkit HTML markup (not Rich markup)."""
    pad = " " * (_frame_left_pad() + 2)

    if wizard_step:
        cur, total, label = wizard_step
        return f"{pad}<style fg='yellow'>[{cur}/{total}]</style> {label} &gt; "

    if state.active_project:
        name = state.active_project.name
        return f"{pad}<b><style fg='ansicyan'>{name}</style></b> &gt; "

    return f"{pad}<b>&gt;</b> "
