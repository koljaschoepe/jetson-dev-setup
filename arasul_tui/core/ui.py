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
from arasul_tui.core.theme import (
    BAR_EMPTY,
    BAR_FILLED,
    DIM,
    ERROR,
    ICON_ARROW,
    ICON_DOT_OFF,
    ICON_FAIL,
    ICON_OK,
    ICON_WARN,
    LOGO_GRADIENT,
    PRIMARY,
    SUCCESS,
    WARNING,
)

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

TIER_FULL = 78
TIER_MEDIUM = 60

# Box-drawing and separator characters (pre-built to avoid backslashes in f-strings)
_HLINE = "\u2500"  # ─
_DOT = "\u00b7"    # ·
_DEG = "\u00b0"    # °
_CHECK = "\u2713"  # ✓

LOGO_LARGE = [
    "  \u2584\u2580\u2588 \u2588\u2580\u2588 \u2584\u2580\u2588 \u2588\u2580\u2580 \u2588 \u2588 \u2588  ",
    "  \u2588\u2580\u2588 \u2588\u2580\u2584 \u2588\u2580\u2588 \u2584\u2588 \u2588\u2584\u2588 \u2588\u2584\u2584",
]

LOGO_COMPACT = [
    "  \u2584\u2580\u2588 \u2588\u2580\u2588 \u2584\u2580\u2588 \u2588\u2580\u2580 \u2588 \u2588 \u2588  ",
    "  \u2588\u2580\u2588 \u2588\u2580\u2584 \u2588\u2580\u2588 \u2584\u2588 \u2588\u2584\u2588 \u2588\u2584\u2584",
]


def _hline(n: int) -> str:
    """Return n horizontal line characters."""
    return _HLINE * n


def _dim_hline(n: int) -> str:
    """Return n dim horizontal line characters with Rich markup."""
    return f"[{DIM}]{_hline(n)}[/{DIM}]"


def _greeting(user: str) -> str:
    """Time-aware greeting for the user."""
    import datetime

    hour = datetime.datetime.now().hour
    name = user.capitalize()
    if hour < 6:
        return f"Still up, {name}?"
    if hour < 12:
        return f"Good morning, {name}."
    if hour < 17:
        return f"Good afternoon, {name}."
    if hour < 22:
        return f"Good evening, {name}."
    return f"Late session, {name}."


def _github_status() -> str:
    auth = cached_cmd("gh auth status 2>&1", timeout=4, ttl=120)
    if "Logged in" not in auth:
        return "[dim]not connected[/dim]"
    from arasul_tui.core.git_info import parse_gh_account

    account = parse_gh_account(auth)
    return f"[cyan]{_CHECK}[/cyan] {account}" if account else f"[cyan]{_CHECK}[/cyan]"


def get_default_interface() -> str:
    """Detect primary network interface dynamically."""
    iface = cached_cmd("ip route show default 2>/dev/null | awk '/default/{print $5}'")
    return iface or "eth0"


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
        return f"[dim]{host} {_DOT} {branch}[/dim]"
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
    """Render a modern block bar like ▰▰▰▱▱▱▱▱ with color based on percentage."""
    filled = int(round(pct / 100 * width))
    empty = width - filled
    if pct >= 90:
        color = ERROR
    elif pct >= 70:
        color = WARNING
    else:
        color = PRIMARY
    bar_filled = f"[{color}]{BAR_FILLED * filled}[/{color}]"
    bar_empty = f"[{DIM}]{BAR_EMPTY * empty}[/{DIM}]"
    return f"{bar_filled}{bar_empty}"


def _build_full_dashboard(state: TuiState, content_w: int) -> list[str]:
    """Build the complete dashboard: greeting, system box, projects."""
    info = _system_info()
    lines: list[str] = []
    dot_sep = f" {_DOT} "

    # --- Greeting ---
    lines.append("")
    lines.append(f"  {_greeting(state.user)}")

    # --- Status subtitle ---
    status_parts: list[str] = [VERSION]
    power = info.get("power", "")
    if power:
        status_parts.append(power)
    ip = info.get("ip", "")
    if ip and ip != "n/a":
        status_parts.append(ip)
    joined = dot_sep.join(status_parts)
    lines.append(f"  [{DIM}]{joined}[/{DIM}]")
    lines.append("")

    # --- System box ---
    box_w = min(content_w - 2, 46)
    bar_w = max(8, min(10, box_w // 5))
    _corner_tl = "\u256d"  # ╭
    _corner_tr = "\u256e"  # ╮
    _corner_bl = "\u2570"  # ╰
    _corner_br = "\u256f"  # ╯
    _vline = "\u2502"      # │

    box_top = f"  [{DIM}]{_corner_tl}{_hline(box_w)}{_corner_tr}[/{DIM}]"
    box_bot = f"  [{DIM}]{_corner_bl}{_hline(box_w)}{_corner_br}[/{DIM}]"
    lines.append(box_top)

    # System metrics inside box
    def _box_row(label: str, bar: str, detail: str) -> str:
        return f"  [{DIM}]{_vline}[/{DIM}]  {label:<5}{bar}  [{DIM}]{detail}[/{DIM}]"

    ram_raw = info.get("ram_pct", 0)
    ram_pct = float(ram_raw) if isinstance(ram_raw, (int, float)) else 0.0
    lines.append(_box_row("RAM", _bar(ram_pct, bar_w), info["ram"]))

    disk_raw = info.get("disk_pct", 0)
    disk_pct = float(disk_raw) if isinstance(disk_raw, (int, float)) else 0.0
    lines.append(_box_row("Disk", _bar(disk_pct, bar_w), info["disk"]))

    temp = info.get("temp", 0)
    temp_pct = min(100, max(0, (temp - 20) * 100 // 80)) if temp else 0
    if temp:
        lines.append(_box_row("Temp", _bar(temp_pct, bar_w), f"{temp}{_DEG}C"))

    gpu_pct = info.get("gpu_pct", 0)
    lines.append(_box_row("GPU", _bar(gpu_pct, bar_w), f"{gpu_pct}%"))

    # Status row inside box
    svc_parts: list[str] = []
    gh = _github_status()
    svc_parts.append(f"GitHub: {gh}")
    docker = info.get("docker", "0")
    if docker and docker != "0":
        svc_parts.append(f"Docker: {docker}")
    svc_line = dot_sep.join(svc_parts)
    lines.append(f"  [{DIM}]{_vline}[/{DIM}]  [{DIM}]{svc_line}[/{DIM}]")

    lines.append(box_bot)

    # --- Projects ---
    lines.append("")
    lines.append("  [bold]Projects[/bold]")
    lines.append("")

    projects = project_list()
    for i, name in enumerate(projects, 1):
        branch, commit_time, is_dirty = _project_detail(name)
        parts: list[str] = []
        if branch:
            branch_str = f"[{DIM}]{branch}[/{DIM}]"
            if is_dirty:
                parts.append(f"{branch_str} [{WARNING}]*[/{WARNING}]")
            else:
                parts.append(f"{branch_str} [{SUCCESS}]{_CHECK}[/{SUCCESS}]")
        if commit_time:
            parts.append(f"[{DIM}]{commit_time}[/{DIM}]")
        detail = "  ".join(parts) if parts else f"[{DIM}]local[/{DIM}]"
        lines.append(f"  [{PRIMARY}]{i}[/{PRIMARY}]  {name}  {detail}")

    if not projects:
        lines.append(f"  [{DIM}]No projects yet. Type 'new' to create one.[/{DIM}]")

    lines.append("")
    lines.append(f"  [{DIM}]Type a command or project name. Try 'help'.[/{DIM}]")

    return lines


def _sep_width() -> int:
    """Separator width: just wide enough to cover content + small margin."""
    return 50


def _print_header_full(state: TuiState) -> None:
    """Full dashboard: frameless layout with gradient logo and boot animation."""
    w = _adaptive_width()
    content_w = w - 6
    pad = content_pad()
    sep = _dim_hline(_sep_width())

    console.print()

    # Logo with boot animation on first run
    animate = state.first_run
    for i, line in enumerate(LOGO_LARGE):
        color = LOGO_GRADIENT[i % len(LOGO_GRADIENT)]
        console.print(f"{pad}{line}", style=f"bold {color}", highlight=False)
        if animate:
            time.sleep(0.06)

    console.print(f"{pad}{sep}", highlight=False)
    if animate:
        time.sleep(0.04)

    dashboard = _build_full_dashboard(state, content_w)
    for line in dashboard:
        console.print(f"{pad}{line}", highlight=False)
    console.print()


def _print_header_medium(state: TuiState) -> None:
    """Medium header: compact logo + full dashboard."""
    content_w = min(console.width - 6, MAX_WIDTH - 6)
    pad = content_pad()
    sep = _dim_hline(_sep_width())

    console.print()
    for i, line in enumerate(LOGO_COMPACT):
        color = LOGO_GRADIENT[i % len(LOGO_GRADIENT)]
        console.print(f"{pad}{line}", style=f"bold {color}", highlight=False)
    console.print(f"{pad}{sep}", highlight=False)

    dashboard = _build_full_dashboard(state, content_w)
    for line in dashboard:
        console.print(f"{pad}{line}", highlight=False)
    console.print()


def _print_header_compact(state: TuiState) -> None:
    """Compact header: text-only with mini bars."""
    pad = " " * _frame_left_pad()
    console.print()
    console.print(f"{pad}[bold {PRIMARY}]ARASUL[/bold {PRIMARY}] [{DIM}]{VERSION}[/{DIM}]", highlight=False)
    w = min(console.width - 2, 40)
    console.print(f"{pad}{_dim_hline(w)}", highlight=False)
    info = _system_info()
    ram_pct = float(info.get("ram_pct", 0))
    disk_pct = float(info.get("disk_pct", 0))
    console.print(f"{pad}RAM {_bar(ram_pct, 6)} [{DIM}]{info['ram']}[/{DIM}]", highlight=False)
    console.print(f"{pad}Disk {_bar(disk_pct, 6)} [{DIM}]{info['disk']}[/{DIM}]", highlight=False)
    projects = project_list()
    if projects:
        console.print(f"{pad}Projects: {len(projects)}", highlight=False)
    console.print()


def _print_project_screen(state: TuiState) -> None:
    """Dedicated project mini-dashboard when a project is open."""
    project = state.active_project
    if not project:
        return

    pad = content_pad()
    name = project.name
    sep = _dim_hline(_sep_width())

    console.print()
    console.print(f"{pad}[bold {PRIMARY}]{name}[/bold {PRIMARY}]", highlight=False)
    console.print(f"{pad}{sep}", highlight=False)

    from arasul_tui.core.git_info import detect_language, get_disk_usage, get_git_info

    gi = get_git_info(project)
    lang = detect_language(project)
    disk = get_disk_usage(project)

    # Git info
    if gi:
        branch_color = WARNING if gi.is_dirty else SUCCESS
        dirty_mark = f" [{WARNING}]*[/{WARNING}]" if gi.is_dirty else ""
        console.print(
            f"{pad}  [{branch_color}]{gi.branch}[/{branch_color}]{dirty_mark}"
            f"  [{DIM}]{gi.short_hash}[/{DIM}]",
            highlight=False,
        )
        if gi.commit_message:
            console.print(
                f"{pad}  [{DIM}]{gi.commit_message}  {_DOT}  {gi.commit_time}[/{DIM}]",
                highlight=False,
            )
    else:
        console.print(f"{pad}  [{DIM}]no git[/{DIM}]", highlight=False)

    # Language + disk
    detail_parts: list[str] = []
    if lang:
        detail_parts.append(lang)
    if disk:
        detail_parts.append(disk)
    if detail_parts:
        detail_line = f"  {_DOT}  ".join(detail_parts)
        console.print(f"{pad}  [{DIM}]{detail_line}[/{DIM}]", highlight=False)

    # Shortcuts
    console.print()
    console.print(
        f"{pad}  [{DIM}][{PRIMARY}]c[/{PRIMARY}] Claude  "
        f"[{PRIMARY}]g[/{PRIMARY}] lazygit  "
        f"[{PRIMARY}]b[/{PRIMARY}] back[/{DIM}]",
        highlight=False,
    )
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
            parts.append(f"[{DIM}]main[/{DIM}]")
        dot_sep = f" [{DIM}]{_DOT}[/{DIM}] "
        title_len = _vis_len(dot_sep.join(parts)) + 2
        side = max(1, (w - title_len) // 2)
        right_side = max(1, w - title_len - side)
        left = _dim_hline(side)
        right = _dim_hline(right_side)
        joined = dot_sep.join(parts)
        console.print(
            f"{pad}{left} {joined} {right}",
            highlight=False,
        )
        return

    # Project screen: show project mini-dashboard
    if state.active_project:
        _print_project_screen(state)
        return

    if console.width >= TIER_FULL:
        _print_header_full(state)
    elif console.width >= TIER_MEDIUM:
        _print_header_medium(state)
    else:
        _print_header_compact(state)


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
    hline6 = _hline(6)
    console.print()
    console.print(f"{pad}[bold]{hline6} {title} {hline6}[/bold]", highlight=False)
    console.print()
    for label, detail, status in items:
        if status == "ok":
            icon = ICON_OK
        elif status == "warn":
            icon = ICON_WARN
        else:
            icon = ICON_FAIL
        console.print(f"{pad}   {icon}  [bold]{label}[/bold]       {detail}", highlight=False)
    console.print()


def print_progress(title: str, items: list[tuple[str, bool]]) -> None:
    """Print a progress checklist. Items: (label, done)."""
    pad = content_pad()
    console.print()
    console.print(f"{pad}[bold]{title}[/bold]", highlight=False)
    console.print()
    for label, done in items:
        icon = ICON_OK if done else ICON_DOT_OFF
        style = "" if done else f"[{DIM}]"
        end_style = "" if done else f"[/{DIM}]"
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
            console.print(f"{pad}[{SUCCESS}]{line}[/{SUCCESS}]", highlight=False)
    elif style == "error":
        for line in result.lines:
            console.print(f"{pad}[{ERROR}]{line}[/{ERROR}]", highlight=False)
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
                console.print(f"{pad}[{ERROR}]{line}[/{ERROR}]", highlight=False)
            else:
                console.print(f"{pad}{line}", highlight=False)


def print_step(current: int, total: int, title: str) -> None:
    pad = content_pad()
    w = _adaptive_width() - 6
    title_plain = f" {title} {_DOT} Step {current}/{total} "
    side = max(1, (w - len(title_plain)) // 2)
    right = max(1, w - len(title_plain) - side)
    left_line = _hline(side)
    right_line = _hline(right)
    console.print()
    console.print(
        f"{pad}[{PRIMARY}]{left_line}[/{PRIMARY}]"
        f" [bold]{title}[/bold] [{DIM}]{_DOT} Step {current}/{total}[/{DIM}] "
        f"[{PRIMARY}]{right_line}[/{PRIMARY}]",
        highlight=False,
    )
    console.print()


def print_success(msg: str) -> None:
    pad = content_pad()
    console.print(f"{pad}{ICON_OK} {msg}", highlight=False)


def print_error(msg: str) -> None:
    pad = content_pad()
    console.print(f"{pad}{ICON_FAIL} {msg}", highlight=False)


def print_info(msg: str) -> None:
    pad = content_pad()
    console.print(f"{pad}{ICON_ARROW} {msg}", highlight=False)


def print_warning(msg: str) -> None:
    pad = content_pad()
    console.print(f"{pad}[{WARNING}]![/{WARNING}] {msg}", highlight=False)


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

    sp = Spinner("dots", text=f"{content_pad()}{msg}", style=PRIMARY)
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


def print_separator(state: TuiState | None = None) -> None:
    """Print a thin separator line with optional contextual hint."""
    pad = " " * _frame_left_pad()
    console.print(f"{pad}{_dim_hline(_sep_width())}", highlight=False)


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
