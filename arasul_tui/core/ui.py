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
    VERSION = "v0.2.0"

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


def _gpu_usage() -> str:
    """Get GPU utilization percentage."""
    gpu = run_cmd("cat /sys/devices/gpu.0/load 2>/dev/null")
    if gpu and gpu.isdigit():
        return f"{int(gpu) // 10}%"
    return ""


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

    gpu = _gpu_usage()

    status_parts = [p for p in [power, temp_str, f"GPU {gpu}" if gpu else ""] if p]

    ip = run_cmd("hostname -I 2>/dev/null | awk '{print $1}'") or "n/a"

    docker_count = run_cmd("docker ps -q 2>/dev/null | wc -l | tr -d ' '") or "0"
    docker_str = f"Docker: {docker_count} running" if docker_count != "0" else ""

    lines = [
        "Jetson Orin Nano Super",
        " [dim]·[/dim] ".join(status_parts) if status_parts else "",
        ip,
        f"RAM {ram} [dim]·[/dim] Disk {disk}",
    ]
    if docker_str:
        lines.append(docker_str)

    return [line for line in lines if line]


def project_list() -> list[str]:
    from arasul_tui.core.state import DEFAULT_PROJECT_ROOT

    try:
        return sorted([p.name for p in DEFAULT_PROJECT_ROOT.iterdir() if p.is_dir()], key=str.lower)
    except Exception:
        return []


def _project_detail(name: str) -> str:
    """Return short git info for a project (branch + dirty + relative time)."""
    from arasul_tui.core.state import DEFAULT_PROJECT_ROOT

    project = DEFAULT_PROJECT_ROOT / name
    if not (project / ".git").exists():
        return "[dim]local[/dim]"
    quoted = shlex.quote(str(project))
    branch = run_cmd(f"git -C {quoted} symbolic-ref --short HEAD 2>/dev/null") or ""
    dirty = run_cmd(f"git -C {quoted} status --porcelain 2>/dev/null")
    is_dirty = bool(dirty and not dirty.startswith("Error"))
    commit_time = run_cmd(f"git -C {quoted} log -1 --format=%cr 2>/dev/null") or ""

    parts: list[str] = []
    if branch:
        branch_str = f"[dim]{branch}[/dim]"
        if is_dirty:
            branch_str += "[yellow]*[/yellow]"
        parts.append(branch_str)
    if commit_time:
        parts.append(f"[dim]{commit_time}[/dim]")

    return "  ".join(parts) if parts else "[dim]local[/dim]"


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
    right.append(" [cyan]\\[n][/cyan]  New   [cyan]\\[d][/cyan]  Delete")
    right.append("")
    right.append(" [dim]/status  /help  /setup[/dim]")

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
    """Show action menu after selecting a project (legacy, used as fallback)."""
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
    console.print(f"{pad}[bold cyan]\\[g][/bold cyan]  Start lazygit", highlight=False)
    console.print(f"{pad}[bold cyan]\\[b][/bold cyan]  Back to overview", highlight=False)
    console.print()


def print_project_screen(state: TuiState) -> None:
    """Show the full project screen with git info and shortcuts."""
    if not state.active_project:
        return

    from arasul_tui.core.git_info import detect_language, get_disk_usage, get_git_info, get_readme_headline

    project = state.active_project
    name = project.name
    git = get_git_info(project)

    w = _adaptive_width()
    content_w = w - 8
    bar = "═" * (w - 6)
    sep = "─" * content_w

    # Build left + right info columns
    left: list[tuple[str, str]] = []
    right: list[tuple[str, str]] = []

    if git:
        branch_str = git.branch or "detached"
        if git.is_dirty:
            branch_str += " [yellow]*[/yellow]"
        left.append(("Branch", branch_str))
        left.append(("Status", "[yellow]modified[/yellow]" if git.is_dirty else "[green]clean[/green]"))
        if git.short_hash:
            msg = git.commit_message[:35] if git.commit_message else ""
            left.append(("Commit", f"{git.short_hash} {msg}"))
        if git.commit_time:
            left.append(("Time", git.commit_time))
    else:
        left.append(("Git", "[dim]not a git repo[/dim]"))

    headline = get_readme_headline(project)
    if headline:
        right.append(("About", headline[:35]))
    disk = get_disk_usage(project)
    if disk:
        right.append(("Disk", disk))
    lang = detect_language(project)
    if lang:
        right.append(("Lang", lang))
    right.append(("Path", f"[dim]{project}[/dim]"))

    # Build frame
    frame: list[str] = []
    frame.append(f"[cyan]╔═╦{bar}╦═╗[/cyan]")
    frame.append(f"[cyan]║ ╚{bar}╝ ║[/cyan]")
    frame.append(f"[cyan]║[/cyan]   {'':>{content_w}}   [cyan]║[/cyan]")
    frame.append(f"[cyan]║[/cyan]   [bold]{_pad_right(name, content_w)}[/bold]   [cyan]║[/cyan]")
    frame.append(f"[cyan]║[/cyan]   [dim]{sep}[/dim]   [cyan]║[/cyan]")

    # Two-column info
    left_w = (content_w - 3) // 2
    right_w = content_w - 3 - left_w
    max_rows = max(len(left), len(right))
    left += [("", "")] * (max_rows - len(left))
    right += [("", "")] * (max_rows - len(right))

    for (lk, lv), (rk, rv) in zip(left, right, strict=False):
        l_str = f"[bold]{lk}[/bold]   {lv}" if lk else ""
        r_str = f"[bold]{rk}[/bold]   {rv}" if rk else ""
        line = f"{_pad_right(l_str, left_w)} [dim]│[/dim] {_pad_right(r_str, right_w)}"
        frame.append(f"[cyan]║[/cyan]   {_pad_right(line, content_w)}   [cyan]║[/cyan]")

    frame.append(f"[cyan]║[/cyan]   [dim]{sep}[/dim]   [cyan]║[/cyan]")

    # Shortcuts
    shortcuts = [
        ("[cyan]\\[c][/cyan]", "Claude Code"),
        ("[cyan]\\[g][/cyan]", "lazygit"),
        ("[cyan]\\[b][/cyan]", "Back to overview"),
    ]
    for key, label in shortcuts:
        line = f"  {key}  {label}"
        frame.append(f"[cyan]║[/cyan]   {_pad_right(line, content_w)}   [cyan]║[/cyan]")

    frame.append(f"[cyan]║[/cyan]   {'':>{content_w}}   [cyan]║[/cyan]")
    frame.append(f"[cyan]║ ╔{bar}╗ ║[/cyan]")
    frame.append(f"[cyan]╚═╩{bar}╩═╝[/cyan]")

    console.print()
    for line in frame:
        console.print(line, justify="center", highlight=False)
    console.print()


def print_styled_panel(title: str, rows: list[tuple[str, str]]) -> None:
    """Print a uniform styled panel with key-value rows."""
    w = _adaptive_width() - 4
    lpad = " " * (_frame_left_pad() + 2)
    table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    table.add_column(style="bold", no_wrap=True)
    table.add_column()
    for k, v in rows:
        table.add_row(k, v)
    p = Panel(table, title=f"[bold]{title}[/bold]", border_style="dim", padding=(0, 1), width=w)
    console.print(f"{lpad}", end="", highlight=False)
    console.print(p, highlight=False)


def print_checklist(title: str, items: list[tuple[str, str, str]]) -> None:
    """Print a color-coded checklist. Items: (label, detail, status: ok/warn/fail)."""
    pad = content_pad()
    console.print()
    console.print(f"{pad}[bold]────── {title} ──────[/bold]", highlight=False)
    console.print()
    for label, detail, status in items:
        if status == "ok":
            icon = "[green]✓[/green]"
        elif status == "warn":
            icon = "[yellow]~[/yellow]"
        else:
            icon = "[red]✗[/red]"
        console.print(f"{pad}   {icon}  [bold]{label}[/bold]       {detail}", highlight=False)
    console.print()


def print_progress(title: str, items: list[tuple[str, bool]]) -> None:
    """Print a progress checklist. Items: (label, done)."""
    pad = content_pad()
    console.print()
    console.print(f"{pad}[bold]{title}[/bold]", highlight=False)
    console.print()
    for label, done in items:
        icon = "[green]✓[/green]" if done else "[dim]○[/dim]"
        style = "" if done else "[dim]"
        end_style = "" if done else "[/dim]"
        console.print(f"{pad}   {icon}  {style}{label}{end_style}", highlight=False)
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
