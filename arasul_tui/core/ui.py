from __future__ import annotations

import shlex
import threading
import time
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from arasul_tui.core.cache import cached_cmd, parallel_cmds
from arasul_tui.core.shell import run_cmd

if TYPE_CHECKING:
    from arasul_tui.core.state import TuiState
    from arasul_tui.core.types import CommandResult

console = Console()

try:
    VERSION = f"v{pkg_version('arasul')}"
except PackageNotFoundError:
    VERSION = "v0.3.0"

MAX_WIDTH = 84
MIN_WIDTH = 50

TIER_FULL = 80
TIER_MEDIUM = 60

_LOGO_COLORS = [
    "#00d4ff",
    "#10c0ff",
    "#20acff",
    "#3098ff",
    "#4088ff",
    "#4c7cff",
    "#5870ff",
]

LOGO_LARGE = [
    " ████  █████   ████   ████  ██  ██ ██",
    "██  ██ ██  ██ ██  ██ ██  ██ ██  ██ ██",
    "██  ██ ██  ██ ██  ██ ██     ██  ██ ██",
    "██████ █████  ██████  ████  ██  ██ ██",
    "██  ██ ██ ██  ██  ██     ██ ██  ██ ██",
    "██  ██ ██  ██ ██  ██ ██  ██ ██  ██ ██",
    "██  ██ ██  ██ ██  ██  ████   ████  ██████",
]


def _github_status() -> str:
    auth = cached_cmd("gh auth status 2>&1", timeout=4, ttl=120)
    if "Logged in" not in auth:
        return "[dim]not connected[/dim]"
    for line in auth.splitlines():
        if "account" in line.lower():
            parts = line.strip().split()
            for i, p in enumerate(parts):
                if p == "account" and i + 1 < len(parts):
                    return f"[cyan]✓[/cyan] {parts[i + 1]}"
    return "[cyan]✓[/cyan]"


def get_default_interface() -> str:
    """Detect primary network interface dynamically."""
    iface = cached_cmd("ip route show default 2>/dev/null | awk '/default/{print $5}'")
    return iface or "eth0"


def _gpu_usage() -> str:
    """Get GPU utilization percentage."""
    gpu = cached_cmd("cat /sys/devices/gpu.0/load 2>/dev/null", ttl=10)
    if gpu and gpu.isdigit():
        return f"{int(gpu) // 10}%"
    return ""


def _system_info() -> dict[str, str]:
    """Gather system info in parallel. Returns dict of named values."""
    try:
        import psutil

        vm = psutil.virtual_memory()
        ram = f"{vm.used // (1024 * 1024)}M / {vm.total // (1024 * 1024)}M"
        ram_pct = vm.percent
    except Exception:
        ram = cached_cmd("free -m | awk '/^Mem:/{printf \"%dM / %dM\", $3, $2}'") or "n/a"
        ram_pct = 0

    # Run all shell commands in parallel
    cmds = {
        "disk": ("df -h /mnt/nvme 2>/dev/null | awk 'NR==2{print $3\"/\"$2}'", 4),
        "disk_pct": ("df /mnt/nvme 2>/dev/null | awk 'NR==2{print $5}' | tr -d '%'", 4),
        "temp": ("cat /sys/devices/virtual/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.0f\", $1/1000}'", 4),
        "power": ("sudo nvpmodel -q 2>/dev/null | head -1 | sed 's/NV Power Mode: //'", 4),
        "gpu": ("cat /sys/devices/gpu.0/load 2>/dev/null", 4),
        "ip": ("hostname -I 2>/dev/null | awk '{print $1}'", 4),
        "docker": ("docker ps -q 2>/dev/null | wc -l | tr -d ' '", 5),
    }
    r = parallel_cmds(cmds)

    # Fallback for disk
    disk = r.get("disk", "")
    if not disk or disk.startswith("Error"):
        disk = cached_cmd("df -h / | awk 'NR==2{print $3\"/\"$2}'") or "n/a"

    disk_pct_str = r.get("disk_pct", "0")
    disk_pct = int(disk_pct_str) if disk_pct_str.isdigit() else 0

    temp = r.get("temp", "")
    temp_val = int(temp) if temp and temp.isdigit() else 0

    gpu = r.get("gpu", "")
    gpu_pct = int(gpu) // 10 if gpu and gpu.isdigit() else 0

    return {
        "ram": ram,
        "ram_pct": ram_pct,
        "disk": disk,
        "disk_pct": disk_pct,
        "temp": temp_val,
        "gpu_pct": gpu_pct,
        "power": r.get("power", ""),
        "ip": r.get("ip", "n/a"),
        "docker": r.get("docker", "0"),
    }


def project_list() -> list[str]:
    from arasul_tui.core.state import DEFAULT_PROJECT_ROOT

    try:
        return sorted([p.name for p in DEFAULT_PROJECT_ROOT.iterdir() if p.is_dir()], key=str.lower)
    except Exception:
        return []


def _project_detail(name: str) -> tuple[str, str, bool]:
    """Return (branch, commit_time, is_dirty) for a project."""
    from arasul_tui.core.state import DEFAULT_PROJECT_ROOT

    project = DEFAULT_PROJECT_ROOT / name
    if not (project / ".git").exists():
        return ("", "", False)
    quoted = shlex.quote(str(project))

    r = parallel_cmds({
        "branch": (f"git -C {quoted} symbolic-ref --short HEAD 2>/dev/null", 4),
        "dirty": (f"git -C {quoted} status --porcelain 2>/dev/null", 4),
        "time": (f"git -C {quoted} log -1 --format=%cr 2>/dev/null", 4),
    })

    branch = r.get("branch", "")
    dirty_out = r.get("dirty", "")
    is_dirty = bool(dirty_out and not dirty_out.startswith("Error"))
    commit_time = r.get("time", "")

    return (branch, commit_time, is_dirty)


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
    return max(MIN_WIDTH, min(console.width - 2, MAX_WIDTH))


def _vis_len(s: str) -> int:
    """Visible cell width of a string that may contain Rich markup."""
    return Text.from_markup(s).cell_len


def _pad_right(s: str, target: int) -> str:
    """Pad a Rich markup string to target visible width with trailing spaces."""
    diff = target - _vis_len(s)
    return s + " " * diff if diff > 0 else s


def _bar(pct: float, width: int = 10) -> str:
    """Render a thin data bar like [━━━─────] with color based on percentage."""
    filled = int(round(pct / 100 * width))
    empty = width - filled
    if pct >= 90:
        color = "red"
    elif pct >= 70:
        color = "yellow"
    else:
        color = "cyan"
    bar_filled = f"[{color}]{'━' * filled}[/{color}]"
    bar_empty = f"[dim]{'─' * empty}[/dim]"
    return f"[dim][[/dim]{bar_filled}{bar_empty}[dim]][/dim]"


def _status_line() -> str:
    """Build the status line: version · power · ip · GitHub."""
    parts = [f"[dim]{VERSION}[/dim]"]
    info = _system_info()
    power = info.get("power", "")
    if power:
        parts.append(f"[dim]{power}[/dim]")
    ip = info.get("ip", "")
    if ip and ip != "n/a":
        parts.append(f"[dim]{ip}[/dim]")
    docker = info.get("docker", "0")
    if docker and docker != "0":
        parts.append(f"[dim]Docker: {docker}[/dim]")
    gh = _github_status()
    parts.append(f"GitHub: {gh}")
    return "  " + "  [dim]·[/dim]  ".join(parts)


def _build_dashboard(state: TuiState, content_w: int) -> list[str]:
    """Build the dashboard content: system bars + projects."""
    info = _system_info()
    lines: list[str] = []

    # --- System metrics with data bars ---
    bar_w = max(8, min(12, content_w // 6))
    label_w = 6

    ram_raw = info.get("ram_pct", 0)
    ram_pct = float(ram_raw) if isinstance(ram_raw, (int, float)) else 0.0
    lines.append(f"  {'RAM':<{label_w}}{_bar(ram_pct, bar_w)}  [dim]{info['ram']}[/dim]")

    disk_raw = info.get("disk_pct", 0)
    disk_pct = float(disk_raw) if isinstance(disk_raw, (int, float)) else 0.0
    lines.append(f"  {'Disk':<{label_w}}{_bar(disk_pct, bar_w)}  [dim]{info['disk']}[/dim]")

    temp = info.get("temp", 0)
    temp_pct = min(100, max(0, (temp - 20) * 100 // 80)) if temp else 0
    if temp:
        lines.append(f"  {'Temp':<{label_w}}{_bar(temp_pct, bar_w)}  [dim]{temp}°C[/dim]")

    gpu_pct = info.get("gpu_pct", 0)
    lines.append(f"  {'GPU':<{label_w}}{_bar(gpu_pct, bar_w)}  [dim]{'idle' if gpu_pct == 0 else f'{gpu_pct}%'}[/dim]")

    # --- Projects ---
    lines.append("")
    lines.append("  [bold]Projects[/bold]")

    projects = project_list()
    for i, name in enumerate(projects, 1):
        branch, commit_time, is_dirty = _project_detail(name)
        parts: list[str] = []
        if branch:
            branch_str = f"[dim]{branch}[/dim]"
            if is_dirty:
                parts.append(f"{branch_str} [yellow]*[/yellow]")
            else:
                parts.append(f"{branch_str} [cyan]✓[/cyan]")
        if commit_time:
            parts.append(f"[dim]{commit_time}[/dim]")
        detail = "  ".join(parts) if parts else "[dim]local[/dim]"
        lines.append(f"  [cyan]{i}[/cyan]  {name}  {detail}")

    if not projects:
        lines.append("  [dim]No projects yet[/dim]")

    lines.append("")
    lines.append("  [dim]/help · /create · /status · /setup[/dim]")

    return lines


def _print_header_full(state: TuiState) -> None:
    """Full dashboard: frameless layout with gradient logo."""
    w = _adaptive_width()
    content_w = w - 6
    pad = content_pad()
    sep = f"[dim]{'─' * content_w}[/dim]"

    logo_lines = list(LOGO_LARGE)
    logo_w = max(len(ln) for ln in logo_lines)

    console.print()

    # Logo with blue gradient
    for i, line in enumerate(logo_lines):
        left_pad = (content_w - logo_w) // 2
        padded = " " * left_pad + line
        color = _LOGO_COLORS[i % len(_LOGO_COLORS)]
        console.print(f"{pad}[bold {color}]{padded}[/bold {color}]", highlight=False)

    # Separator
    console.print(f"{pad}{sep}", highlight=False)

    # Status line (version · power · ip · GitHub)
    console.print(f"{pad}{_status_line()}", highlight=False)
    console.print()

    # Dashboard content (metrics + projects)
    dashboard = _build_dashboard(state, content_w)
    for line in dashboard:
        console.print(f"{pad}{line}", highlight=False)
    console.print()


def _print_header_medium(state: TuiState) -> None:
    """Medium header: frameless, compact dashboard, no logo."""
    pad = content_pad()
    w = min(console.width - 6, 56)
    sep = f"[dim]{'─' * w}[/dim]"

    console.print()
    console.print(f"{pad}[bold cyan]ARASUL[/bold cyan] [dim]{VERSION}[/dim]", highlight=False)
    console.print(f"{pad}{sep}", highlight=False)
    console.print()

    info = _system_info()
    bar_w = 8
    ram_pct = float(info.get("ram_pct", 0))
    disk_pct = float(info.get("disk_pct", 0))
    console.print(f"{pad}  RAM {_bar(ram_pct, bar_w)} [dim]{info['ram']}[/dim]", highlight=False)
    console.print(f"{pad}  Disk {_bar(disk_pct, bar_w)} [dim]{info['disk']}[/dim]", highlight=False)
    console.print()
    console.print()

    console.print(f"{pad}  [bold]Projects[/bold]", highlight=False)
    console.print()
    projects = project_list()
    for i, name in enumerate(projects, 1):
        branch, commit_time, is_dirty = _project_detail(name)
        detail_parts: list[str] = []
        if branch:
            b = f"[dim]{branch}[/dim]"
            if is_dirty:
                b += "[yellow]*[/yellow]"
            detail_parts.append(b)
        if commit_time:
            detail_parts.append(f"[dim]{commit_time}[/dim]")
        detail = "  ".join(detail_parts) if detail_parts else "[dim]local[/dim]"
        console.print(f"{pad}  [cyan]{i}[/cyan]  {name}  {detail}", highlight=False)
    if not projects:
        console.print(f"{pad}  [dim]No projects yet[/dim]", highlight=False)
    console.print()


def _print_header_compact(state: TuiState) -> None:
    """Compact header: text-only with mini bars."""
    pad = " " * _frame_left_pad()
    console.print()
    console.print(f"{pad}[bold cyan]ARASUL[/bold cyan] [dim]{VERSION}[/dim]", highlight=False)
    w = min(console.width - 2, 40)
    console.print(f"{pad}[dim]{'─' * w}[/dim]", highlight=False)
    info = _system_info()
    ram_pct = float(info.get("ram_pct", 0))
    disk_pct = float(info.get("disk_pct", 0))
    console.print(f"{pad}RAM {_bar(ram_pct, 6)} [dim]{info['ram']}[/dim]", highlight=False)
    console.print(f"{pad}Disk {_bar(disk_pct, 6)} [dim]{info['disk']}[/dim]", highlight=False)
    projects = project_list()
    if projects:
        console.print(f"{pad}Projects: {len(projects)}", highlight=False)
    console.print()


def print_header(state: TuiState, full: bool = True) -> None:
    """Print header. full=True for startup dashboard, full=False for inline context."""
    if not full:
        # Compact inline context indicator (used in chat-flow)
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
            parts.append("[dim]main[/dim]")
        title_len = _vis_len(" [dim]·[/dim] ".join(parts)) + 2
        side = max(1, (w - title_len) // 2)
        right_side = max(1, w - title_len - side)
        console.print(
            f"{pad}[dim]{'─' * side}[/dim] {' [dim]·[/dim] '.join(parts)} [dim]{'─' * right_side}[/dim]",
            highlight=False,
        )
        return

    if console.width >= TIER_FULL:
        _print_header_full(state)
    elif console.width >= TIER_MEDIUM:
        _print_header_medium(state)
    else:
        _print_header_compact(state)


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


def _project_info_rows(project: Path, git: Any) -> list[tuple[str, str]]:
    """Build key-value rows for project info."""
    from arasul_tui.core.git_info import detect_language, get_disk_usage, get_readme_headline

    rows: list[tuple[str, str]] = []
    if git:
        branch_str = git.branch or "detached"
        if git.is_dirty:
            branch_str += " [yellow]*[/yellow]"
        rows.append(("Branch", branch_str))
        rows.append(("Status", "[yellow]modified[/yellow]" if git.is_dirty else "[cyan]clean[/cyan]"))
        if git.short_hash:
            msg = git.commit_message[:35] if git.commit_message else ""
            rows.append(("Commit", f"{git.short_hash} {msg}"))
        if git.commit_time:
            rows.append(("Time", git.commit_time))
    else:
        rows.append(("Git", "[dim]not a git repo[/dim]"))

    headline = get_readme_headline(project)
    if headline:
        rows.append(("About", headline[:35]))
    disk = get_disk_usage(project)
    if disk:
        rows.append(("Disk", disk))
    lang = detect_language(project)
    if lang:
        rows.append(("Lang", lang))
    rows.append(("Path", f"[dim]{project}[/dim]"))
    return rows


def _print_project_full(state: TuiState) -> None:
    """Full project screen: frameless with project info."""
    from arasul_tui.core.git_info import get_git_info

    project = state.active_project
    name = project.name
    git = get_git_info(project)

    pad = content_pad()
    w = _adaptive_width() - 6
    sep = f"[dim]{'─' * w}[/dim]"

    console.print()
    console.print(f"{pad}[bold]{name}[/bold]", highlight=False)
    console.print(f"{pad}{sep}", highlight=False)
    console.print()

    for k, v in _project_info_rows(project, git):
        if k:
            console.print(f"{pad}  [bold]{k:<8}[/bold] {v}", highlight=False)

    console.print()
    console.print(f"{pad}{sep}", highlight=False)
    console.print(f"{pad}  [cyan]\\[c][/cyan] Claude  [cyan]\\[g][/cyan] lazygit  [cyan]\\[b][/cyan] Back", highlight=False)
    console.print()


def _print_project_medium(state: TuiState) -> None:
    """Medium project screen: frameless, compact."""
    from arasul_tui.core.git_info import get_git_info

    project = state.active_project
    name = project.name
    git = get_git_info(project)

    pad = content_pad()
    w = min(console.width - 6, 56)
    sep = f"[dim]{'─' * w}[/dim]"

    console.print()
    console.print(f"{pad}[bold]{name}[/bold]", highlight=False)
    console.print(f"{pad}{sep}", highlight=False)
    console.print()

    for k, v in _project_info_rows(project, git):
        if k:
            console.print(f"{pad}  [bold]{k}[/bold]  {v}", highlight=False)

    console.print()
    console.print(f"{pad}{sep}", highlight=False)
    console.print(f"{pad}  [cyan]\\[c][/cyan] Claude  [cyan]\\[g][/cyan] lazygit  [cyan]\\[b][/cyan] Back", highlight=False)
    console.print()


def _print_project_compact(state: TuiState) -> None:
    """Compact project screen: minimal."""
    from arasul_tui.core.git_info import get_git_info

    project = state.active_project
    name = project.name
    git = get_git_info(project)

    pad = " " * _frame_left_pad()
    console.print()
    console.print(f"{pad}[bold]{name}[/bold]", highlight=False)
    w = min(console.width - 2, 40)
    console.print(f"{pad}[dim]{'─' * w}[/dim]", highlight=False)
    if git:
        branch_str = git.branch or "detached"
        if git.is_dirty:
            branch_str += " [yellow]*[/yellow]"
        console.print(f"{pad}Branch: {branch_str}", highlight=False)
    console.print(f"{pad}[cyan]\\[c][/cyan] Claude  [cyan]\\[g][/cyan] lazygit  [cyan]\\[b][/cyan] Back", highlight=False)
    console.print()


def print_project_screen(state: TuiState) -> None:
    """Show the project screen with git info and shortcuts (three-tier responsive)."""
    if not state.active_project:
        return

    if console.width >= TIER_FULL:
        _print_project_full(state)
    elif console.width >= TIER_MEDIUM:
        _print_project_medium(state)
    else:
        _print_project_compact(state)


def print_styled_panel(title: str, rows: list[tuple[str, str]]) -> None:
    """Print a uniform styled panel with key-value rows."""
    w = _adaptive_width() - 4
    lpad = " " * (_frame_left_pad() + 2)
    table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    table.add_column(style="bold", no_wrap=True)
    table.add_column()
    for k, v in rows:
        table.add_row(k, v)
    p = Panel(table, title=f"[bold]{title}[/bold]", border_style="dim", box=box.ROUNDED, padding=(0, 1), width=w)
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
        p = Panel(text, border_style="dim", box=box.ROUNDED, padding=(0, 2), width=w)
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
        p = Panel(table, title=f"[bold]{title}[/bold]", border_style="dim", box=box.ROUNDED, padding=(0, 1), width=w)
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
    """Fixed left margin for left-aligned layout."""
    return 1


def content_pad() -> str:
    """Left padding to align output with frame interior."""
    return " " * (_frame_left_pad() + 3)


def print_separator() -> None:
    """Print a thin separator line."""
    w = min(console.width - 4, MAX_WIDTH)
    pad = " " * _frame_left_pad()
    console.print(f"{pad}[dim]{'─' * w}[/dim]", highlight=False)


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
