"""n8n workflow automation — /n8n command handler.

Smart command that does the right thing based on current state:
- Not installed  -> install + start + guide through API key + MCP
- Stopped        -> start
- No API key     -> prompt for key + configure MCP
- All good       -> show status dashboard

Only subcommand: /n8n stop
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
from pathlib import Path

from rich import box
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel

from arasul_tui.core.n8n_client import (
    N8N_BASE_URL,
    N8N_DIR,
    n8n_compose_cmd,
    n8n_get_api_key,
    n8n_health,
    n8n_is_installed,
    n8n_is_running,
    n8n_lan_url,
    n8n_list_workflows,
    n8n_save_api_key,
)
from arasul_tui.core.n8n_mcp import (
    configure_n8n_mcp,
    is_n8n_mcp_configured,
)
from arasul_tui.core.shell import run_cmd
from arasul_tui.core.state import TuiState
from arasul_tui.core.theme import BAR_EMPTY, BAR_FILLED, DIM, PRIMARY, SUCCESS
from arasul_tui.core.types import CommandResult
from arasul_tui.core.ui import (
    _adaptive_width,
    _frame_left_pad,
    console,
    content_pad,
    print_error,
    print_info,
    print_styled_panel,
    print_success,
    print_warning,
    spinner_run,
)

# Spinner animation frames
_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# Step status icons
_ICON_DONE = f"[{SUCCESS}]\u2713[/{SUCCESS}]"  # ✓
_ICON_PENDING = f"[{DIM}]\u25cb[/{DIM}]"        # ○


# ---------------------------------------------------------------------------
# Animated install display
# ---------------------------------------------------------------------------

def _check_milestone(index: int) -> bool:
    """Check if a milestone is reached by polling filesystem/docker."""
    if index == 0:  # Directories
        return Path("/mnt/nvme/n8n").is_dir()
    if index == 1:  # Environment
        return Path("/mnt/nvme/n8n/.env").is_file()
    if index == 2:  # Compose file
        return Path("/mnt/nvme/n8n/docker-compose.yml").is_file()
    if index == 3:  # Images pulled (containers exist, even if not running yet)
        out = run_cmd(
            "docker images --format '{{.Repository}}' 2>/dev/null | grep -c n8n",
            timeout=5,
        )
        return bool(out and out.strip().isdigit() and int(out.strip()) > 0)
    if index == 4:  # Containers running
        return n8n_is_running()
    if index == 5:  # Health check
        try:
            from urllib.request import Request, urlopen
            req = Request(f"{N8N_BASE_URL}/healthz", method="GET")
            with urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False
    return False


_STEPS = [
    ("Directories", "/mnt/nvme/n8n"),
    ("Environment", "credentials + encryption key"),
    ("Compose file", "n8n + PostgreSQL stack"),
    ("Pulling images", "this may take a few minutes"),
    ("Starting containers", "n8n + PostgreSQL"),
    ("Health check", "waiting for API"),
]


def _build_install_panel(
    step_states: list[bool],
    active_step: int,
    frame_idx: int,
    elapsed: float,
    done: bool,
    failed: bool,
) -> Padding:
    """Build the animated installation panel, matching print_styled_panel layout."""
    lines: list[str] = [""]

    total = len(_STEPS)
    completed = sum(step_states)

    for i, (label, detail) in enumerate(_STEPS):
        if step_states[i]:
            icon = _ICON_DONE
            line = f"  {icon}  [bold]{label}[/bold]  [{DIM}]{detail}[/{DIM}]"
        elif i == active_step and not done and not failed:
            frame = _SPINNER_FRAMES[frame_idx % len(_SPINNER_FRAMES)]
            icon = f"[{PRIMARY}]{frame}[/{PRIMARY}]"
            line = f"  {icon}  [bold]{label}[/bold]  [{DIM}]{detail}[/{DIM}]"
        else:
            icon = _ICON_PENDING
            line = f"  {icon}  [{DIM}]{label}[/{DIM}]"
        lines.append(line)

    # Progress bar
    lines.append("")
    bar_w = 20
    fill = int(completed / total * bar_w)
    empty = bar_w - fill
    bar = f"[{PRIMARY}]{BAR_FILLED * fill}[/{PRIMARY}][{DIM}]{BAR_EMPTY * empty}[/{DIM}]"
    pct = int(completed / total * 100)

    mins = int(elapsed) // 60
    secs = int(elapsed) % 60
    time_str = f"{mins}:{secs:02d}" if mins else f"{secs}s"

    if failed:
        lines.append(f"  {bar}  [red]failed[/red]  [{DIM}]{time_str}[/{DIM}]")
    elif done:
        lines.append(f"  {bar}  [{SUCCESS}]complete[/{SUCCESS}]  [{DIM}]{time_str}[/{DIM}]")
    else:
        lines.append(f"  {bar}  [{DIM}]{pct}%  {time_str}[/{DIM}]")

    lines.append("")

    content = "\n".join(lines)
    title = "[bold]n8n Setup[/bold]"
    if done:
        title = f"[bold {SUCCESS}]n8n Setup[/bold {SUCCESS}]"
    elif failed:
        title = "[bold red]n8n Setup[/bold red]"

    # Match print_styled_panel: width = _adaptive_width() - 4, left pad = _frame_left_pad() + 2
    panel_w = _adaptive_width() - 4
    left_pad = _frame_left_pad() + 2

    panel = Panel(
        content,
        title=title,
        border_style=SUCCESS if done else ("red" if failed else DIM),
        box=box.ROUNDED,
        padding=(0, 1),
        width=panel_w,
    )
    return Padding(panel, (0, 0, 0, left_pad))


def _run_install_animated(setup_cmd: str) -> tuple[bool, str]:
    """Run the setup script with an animated progress display."""
    output = ""
    error: Exception | None = None
    script_done = False

    def _worker() -> None:
        nonlocal output, error, script_done
        try:
            output = run_cmd(setup_cmd, timeout=600)
        except Exception as exc:
            error = exc
        finally:
            script_done = True

    t = threading.Thread(target=_worker)
    t.start()

    step_states = [False] * len(_STEPS)
    frame_idx = 0
    start_time = time.monotonic()

    with Live(
        _build_install_panel(step_states, 0, 0, 0, False, False),
        console=console,
        refresh_per_second=8,
        transient=False,
    ) as live:
        while not script_done:
            elapsed = time.monotonic() - start_time
            frame_idx += 1

            # Poll milestones
            for i in range(len(_STEPS)):
                if not step_states[i]:
                    with contextlib.suppress(Exception):
                        step_states[i] = _check_milestone(i)

            # Find active step (first incomplete)
            active = next(
                (i for i in range(len(_STEPS)) if not step_states[i]),
                len(_STEPS) - 1,
            )

            live.update(
                _build_install_panel(
                    step_states, active, frame_idx, elapsed, False, False
                )
            )
            time.sleep(0.12)

        # Final state — check all milestones one last time
        elapsed = time.monotonic() - start_time
        for i in range(len(_STEPS)):
            if not step_states[i]:
                with contextlib.suppress(Exception):
                    step_states[i] = _check_milestone(i)

        ok = error is None and n8n_is_running()
        live.update(
            _build_install_panel(
                step_states,
                len(_STEPS) - 1,
                frame_idx,
                elapsed,
                done=ok,
                failed=not ok,
            )
        )

    if error:
        raise error
    return ok, output


# ---------------------------------------------------------------------------
# Status dashboard
# ---------------------------------------------------------------------------

def _show_status() -> CommandResult:
    rows: list[tuple[str, str]] = []

    health = n8n_health()

    # Container status
    container = health.get("container", "not found")
    if "Up" in container:
        rows.append(("n8n", f"[green]running[/green] [dim]({container})[/dim]"))
    else:
        rows.append(("n8n", f"[yellow]{container}[/yellow]"))

    # Postgres
    pg = health.get("postgres", "not found")
    if "Up" in pg:
        rows.append(("PostgreSQL", "[green]running[/green]"))
    else:
        rows.append(("PostgreSQL", f"[yellow]{pg}[/yellow]"))

    # API
    api = health.get("api", "unreachable")
    if api == "healthy":
        rows.append(("API", "[green]healthy[/green]"))
    else:
        rows.append(("API", f"[yellow]{api}[/yellow]"))

    # API key
    api_key = n8n_get_api_key()
    if api_key:
        rows.append(("API Key", f"[green]configured[/green] [dim]({api_key[:8]}...)[/dim]"))
    else:
        rows.append(("API Key", "[dim]not set[/dim]"))

    # Workflows (only if API key is set and n8n is running)
    if api_key and api == "healthy":
        workflows = n8n_list_workflows()
        active = sum(1 for w in workflows if w.get("active"))
        rows.append(("Workflows", f"{len(workflows)} total, {active} active"))

    # MCP server
    if is_n8n_mcp_configured():
        rows.append(("MCP Server", "[green]configured[/green]"))
    else:
        rows.append(("MCP Server", "[dim]not set[/dim]"))

    # URLs
    lan = n8n_lan_url()
    rows.append(("Web UI", f"[cyan]{lan}[/cyan]"))
    rows.append(("Data", f"[dim]{N8N_DIR}[/dim]"))

    print_styled_panel("n8n Automation", rows)
    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# Smart flow: install -> start -> api-key -> mcp
# ---------------------------------------------------------------------------

def _smart_flow(state: TuiState) -> CommandResult:
    # --- Step 1: Install if needed ---
    if not n8n_is_installed():
        script = run_cmd("command -v sudo 2>/dev/null", timeout=2)
        if not script:
            print_error("sudo not available.")
            return CommandResult(ok=False, style="silent")

        # Resolve absolute path to setup script
        repo_root = Path(__file__).parent.parent.parent
        setup_script = repo_root / "scripts" / "09-n8n-setup.sh"
        if not setup_script.exists():
            print_error(f"Setup script not found: {setup_script}")
            return CommandResult(ok=False, style="silent")

        # The script needs NVME_MOUNT, REAL_USER, and SCRIPT_DIR
        real_user = os.environ.get("USER") or os.environ.get("LOGNAME", "")
        env_vars = (
            f'NVME_MOUNT=/mnt/nvme REAL_USER={real_user} SCRIPT_DIR="{repo_root}"'
        )

        console.print()
        try:
            ok, output = _run_install_animated(
                f"sudo {env_vars} bash {setup_script} 2>&1"
            )
        except Exception as exc:
            print_error(f"Installation failed: {exc}")
            return CommandResult(ok=False, style="silent")

        if not ok:
            print_warning("n8n is not running after install.")
            if output:
                pad = content_pad()
                console.print(f"{pad}[dim]{output[-300:]}[/dim]", highlight=False)
            return CommandResult(ok=False, style="silent")

        console.print()
        print_success("n8n installed and running!")

    # --- Step 2: Start if stopped ---
    if n8n_is_installed() and not n8n_is_running():
        def _run_start() -> str:
            return n8n_compose_cmd("up -d")

        spinner_run("Starting n8n...", _run_start)

        if not n8n_is_running():
            print_error("n8n failed to start.")
            return CommandResult(ok=False, style="silent")

        print_success(f"n8n started at [bold]{n8n_lan_url()}[/bold]")

    # --- Step 3: API key if missing ---
    api_key = n8n_get_api_key()
    if not api_key:
        console.print()
        lan = n8n_lan_url()
        print_info(f"Open [bold cyan]{lan}/settings/api[/bold cyan] and create an API key.")
        return CommandResult(
            ok=True,
            style="silent",
            prompt="Paste API key",
            pending_handler=_api_key_finish,
            wizard_step=(1, 1, "API Key"),
        )

    # --- Step 4: MCP if not configured ---
    if not is_n8n_mcp_configured():
        ok, msg = configure_n8n_mcp(api_key)
        if ok:
            print_success("MCP server configured.")
        else:
            print_warning(f"MCP setup failed: {msg}")

    # --- All good: show status ---
    return _show_status()


def _api_key_finish(state: TuiState, raw: str) -> CommandResult:
    key = raw.strip()
    if not key:
        print_error("No key provided.")
        return CommandResult(ok=False, style="silent")

    n8n_save_api_key(key)
    print_success(f"API key saved: [dim]{key[:8]}...[/dim]")

    # Auto-configure MCP after saving API key
    if not is_n8n_mcp_configured():
        ok, msg = configure_n8n_mcp(key)
        if ok:
            print_success("MCP server configured. n8n is ready!")
        else:
            print_warning(f"MCP setup failed: {msg}")

    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /n8n stop
# ---------------------------------------------------------------------------

def _do_stop() -> CommandResult:
    if not n8n_is_installed():
        print_warning("n8n not installed.")
        return CommandResult(ok=False, style="silent")

    if not n8n_is_running():
        print_info("n8n is already stopped.")
        return CommandResult(ok=True, style="silent")

    def _run_stop() -> str:
        return n8n_compose_cmd("down")

    spinner_run("Stopping n8n...", _run_stop)
    print_success("n8n stopped.")
    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /n8n (dispatcher)
# ---------------------------------------------------------------------------

def cmd_n8n(state: TuiState, args: list[str]) -> CommandResult:
    if args and args[0].lower() == "stop":
        return _do_stop()

    return _smart_flow(state)
