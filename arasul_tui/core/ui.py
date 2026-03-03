from __future__ import annotations

import shlex
import threading
import time
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from arasul_tui.core.state import TuiState
    from arasul_tui.core.types import CommandResult

from arasul_tui.core.shell import run_cmd

console = Console()

try:
    VERSION = f"v{pkg_version('arasul')}"
except PackageNotFoundError:
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


def _github_status() -> str:
    auth = run_cmd("gh auth status 2>&1", timeout=4)
    if "Logged in" not in auth:
        return "[dim]not connected[/dim]"
    for line in auth.splitlines():
        if "account" in line.lower():
            parts = line.strip().split()
            for i, p in enumerate(parts):
                if p == "account" and i + 1 < len(parts):
                    return f"[green]✓[/green] {parts[i + 1]}"
    return "[green]✓[/green]"


def get_default_interface() -> str:
    """Detect primary network interface dynamically."""
    iface = run_cmd("ip route show default 2>/dev/null | awk '/default/{print $5}'")
    return iface or "eth0"


def _system_info() -> list[str]:
    """Compact system info lines."""
    try:
        import psutil

        vm = psutil.virtual_memory()
        ram = f"{vm.used // (1024 * 1024)}M / {vm.total // (1024 * 1024)}M"
    except Exception:
        ram = run_cmd("free -m | awk '/^Mem:/{printf \"%dM / %dM\", $3, $2}'") or "n/a"

    disk = run_cmd("df -h /mnt/nvme 2>/dev/null | awk 'NR==2{print $3\"/\"$2}'")
    if not disk:
        disk = run_cmd("df -h / | awk 'NR==2{print $3\"/\"$2}'") or "n/a"

    temp = run_cmd("cat /sys/devices/virtual/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.0f\", $1/1000}'")
    temp_str = f"{temp}°C" if temp and temp.isdigit() else ""

    power = run_cmd("sudo nvpmodel -q 2>/dev/null | head -1 | sed 's/NV Power Mode: //'") or ""

    power_temp = [p for p in [power, temp_str] if p]

    ip = run_cmd("hostname -I 2>/dev/null | awk '{print $1}'") or "n/a"

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
        return "[dim]local[/dim]"
    quoted = shlex.quote(str(project))
    url = run_cmd(f"git -C {quoted} remote get-url origin 2>/dev/null")
    branch = run_cmd(f"git -C {quoted} symbolic-ref --short HEAD 2>/dev/null") or ""
    if not url:
        parts = ["[dim]local[/dim]"]
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
    quoted = shlex.quote(str(project))
    url = run_cmd(f"git -C {quoted} remote get-url origin 2>/dev/null")
    if not url:
        return "[dim]local[/dim]"
    host = "github" if "github" in url else "git"
    branch = run_cmd(f"git -C {quoted} symbolic-ref --short HEAD 2>/dev/null")
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

    right = ["[bold]Projects[/bold]"]
    projects = project_list()
    for i, name in enumerate(projects, 1):
        detail = _project_detail(name)
        right.append(f" [cyan]{i}[/cyan]  {name}  {detail}")
    if not projects:
        right.append(" [dim]No projects[/dim]")
    right.append("")
    right.append(" [cyan]\\[n][/cyan]  New project")
    right.append(" [cyan]\\[d][/cyan]  Delete project")
    right.append("")
    right.append("[bold]Quick Start[/bold]")
    right.append(" [dim]/open <name>[/dim]  Open project")
    right.append(" [dim]/claude[/dim]       Start Claude")
    right.append(" [dim]/help[/dim]         All commands")

    left_w = (content_w - 3) // 2
    right_w = content_w - 3 - left_w

    max_h = max(len(left), len(right))
    top_pad = (max_h - len(left)) // 2
    left = [""] * top_pad + left + [""] * (max_h - len(left) - top_pad)
    right += [""] * (max_h - len(right))

    return [
        f"{_pad_right(left_col, left_w)} [dim]│[/dim] {_pad_right(right_col, right_w)}"
        for left_col, right_col in zip(left, right, strict=False)
    ]


def print_header(state: TuiState, full: bool = True) -> None:
    if not full:
        pad = content_pad()
        w = _adaptive_width() - 6
        parts: list[str] = []
        if state.active_project:
            name = state.active_project.name
            parts.append(f"[bold]{name}[/bold]")
            gi = _git_info_short(state.active_project)
            if gi:
                parts.append(gi)
        else:
            parts.append("[dim]no project[/dim]")
        title_len = _vis_len(" [dim]·[/dim] ".join(parts)) + 2
        side = max(1, (w - title_len) // 2)
        right_side = max(1, w - title_len - side)
        console.print()
        console.print(
            f"{pad}[dim]{'─' * side}[/dim] {' [dim]·[/dim] '.join(parts)} [dim]{'─' * right_side}[/dim]",
            highlight=False,
        )
        console.print()
        return

    w = _adaptive_width()
    content_w = w - 8
    bar = "═" * (w - 6)
    sep = "─" * content_w

    logo_lines = _build_logo_lines()
    info_lines = _build_info_lines(state, content_w)

    frame: list[str] = []

    frame.append(f"[cyan]╔═╦{bar}╦═╗[/cyan]")
    frame.append(f"[cyan]║ ╚{bar}╝ ║[/cyan]")

    logo_w = max(len(ln) for ln in logo_lines)
    for line in logo_lines:
        left_pad = (content_w - logo_w) // 2
        padded = " " * left_pad + line.ljust(logo_w)
        padded = padded.ljust(content_w)
        frame.append(f"[cyan]║[/cyan]   [bold cyan]{padded}[/bold cyan]   [cyan]║[/cyan]")

    frame.append(f"[cyan]║[/cyan]   [dim]{sep}[/dim]   [cyan]║[/cyan]")

    for line in info_lines:
        frame.append(f"[cyan]║[/cyan]   {_pad_right(line, content_w)}   [cyan]║[/cyan]")

    frame.append(f"[cyan]║ ╔{bar}╗ ║[/cyan]")
    frame.append(f"[cyan]╚═╩{bar}╩═╝[/cyan]")

    console.print()
    for line in frame:
        console.print(line, justify="center", highlight=False)
    console.print()


def print_project_menu(state: TuiState) -> None:
    """Show action menu after selecting a project."""
    pad = content_pad()
    name = state.active_project.name if state.active_project else "?"
    gi = _git_info_short(state.active_project)
    title_parts = [f"[bold]{name}[/bold]"]
    if gi:
        title_parts.append(gi)
    title = " [dim]·[/dim] ".join(title_parts)

    console.print()
    console.print(f"{pad}[dim]{title}[/dim]", highlight=False)
    console.print()
    console.print(f"{pad}[bold cyan]\\[c][/bold cyan]  Start Claude Code", highlight=False)
    console.print(f"{pad}[bold cyan]\\[x][/bold cyan]  Start Codex", highlight=False)
    console.print(f"{pad}[bold cyan]\\[b][/bold cyan]  Back to overview", highlight=False)
    console.print()


def print_result(result: CommandResult) -> None:
    if not result.lines:
        return

    style = getattr(result, "style", None)
    pad = content_pad()

    if style == "silent":
        return

    if style == "success":
        for line in result.lines:
            console.print(f"{pad}[green]{line}[/green]", highlight=False)
    elif style == "error":
        for line in result.lines:
            console.print(f"{pad}[red]{line}[/red]", highlight=False)
    elif style == "panel":
        text = "\n".join(result.lines)
        w = _adaptive_width() - 4
        p = Panel(text, border_style="dim", padding=(0, 2), width=w)
        lpad = " " * _frame_left_pad()
        console.print(f"{lpad}  ", end="", highlight=False)
        console.print(p, highlight=False)
    elif style == "wizard":
        for line in result.lines:
            console.print(f"{pad}{line}", highlight=False)
    else:
        ok = result.ok
        for line in result.lines:
            if not ok and line and not line.startswith(" "):
                console.print(f"{pad}[red]{line}[/red]", highlight=False)
            else:
                console.print(f"{pad}{line}", highlight=False)


def print_step(current: int, total: int, title: str) -> None:
    pad = content_pad()
    w = _adaptive_width() - 6
    title_plain = f" {title} · Step {current}/{total} "
    side = max(1, (w - len(title_plain)) // 2)
    right = max(1, w - len(title_plain) - side)
    console.print()
    console.print(
        f"{pad}[cyan]{'─' * side}[/cyan]"
        f" [bold]{title}[/bold] [dim]· Step {current}/{total}[/dim] "
        f"[cyan]{'─' * right}[/cyan]",
        highlight=False,
    )
    console.print()


def print_success(msg: str) -> None:
    pad = content_pad()
    console.print(f"{pad}[green]✓[/green] {msg}", highlight=False)


def print_error(msg: str) -> None:
    pad = content_pad()
    console.print(f"{pad}[red]✗[/red] {msg}", highlight=False)


def print_info(msg: str) -> None:
    pad = content_pad()
    console.print(f"{pad}[cyan]→[/cyan] {msg}", highlight=False)


def print_warning(msg: str) -> None:
    pad = content_pad()
    console.print(f"{pad}[yellow]![/yellow] {msg}", highlight=False)


def print_kv(data: list[tuple[str, str]], title: str | None = None) -> None:
    w = _adaptive_width() - 4
    lpad = " " * (_frame_left_pad() + 2)
    table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    table.add_column(style="bold", no_wrap=True)
    table.add_column()
    for k, v in data:
        table.add_row(k, v)
    if title:
        p = Panel(table, title=f"[bold]{title}[/bold]", border_style="dim", padding=(0, 1), width=w)
        console.print(f"{lpad}", end="", highlight=False)
        console.print(p, highlight=False)
    else:
        console.print(f"{lpad}", end="", highlight=False)
        console.print(table, highlight=False)


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

    sp = Spinner("dots", text=f"{content_pad()}{msg}", style="cyan")
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


def content_pad() -> str:
    """Left padding to align output with frame interior."""
    return " " * (_frame_left_pad() + 3)


def print_separator() -> None:
    """Print a thin separator line aligned with the frame."""
    w = _adaptive_width()
    pad = " " * _frame_left_pad()
    console.print(f"{pad}{'─' * w}", style="dim", highlight=False)


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
