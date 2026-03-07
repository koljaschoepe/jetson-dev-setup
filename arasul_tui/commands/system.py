from __future__ import annotations

import datetime as dt
import shlex
import socket
from pathlib import Path

import psutil

from arasul_tui.core.docker_info import docker_running_count, list_containers
from arasul_tui.core.setup_wizard import check_setup_status, run_setup_step
from arasul_tui.core.shell import run_cmd
from arasul_tui.core.state import TuiState
from arasul_tui.core.types import CommandResult
from arasul_tui.core.ui import (
    console,
    content_pad,
    content_width,
    get_default_interface,
    print_error,
    print_info,
    print_kv,
    print_progress,
    print_styled_panel,
    print_success,
    print_warning,
    spinner_run,
    truncate,
)

# ---------------------------------------------------------------------------
# /status (enhanced)
# ---------------------------------------------------------------------------


def cmd_status(state: TuiState, _: list[str]) -> CommandResult:
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/mnt/nvme" if Path("/mnt/nvme").exists() else "/")
    uptime_s = int(dt.datetime.now().timestamp() - psutil.boot_time())
    hours, rem = divmod(uptime_s, 3600)
    mins = rem // 60
    uptime = f"{hours}h {mins}m" if hours else f"{mins}m"

    iface = get_default_interface()
    ip = run_cmd(f"ip -4 addr show {shlex.quote(iface)} | awk '/inet/{{print $2}}' | cut -d/ -f1")
    if not ip or ip.startswith("Error"):
        ip = run_cmd("hostname -I | awk '{print $1}'") or "n/a"
    power = run_cmd("sudo nvpmodel -q | head -1 | sed 's/NV Power Mode: //'") or "n/a"
    temp = run_cmd("cat /sys/devices/virtual/thermal/thermal_zone0/temp | awk '{printf \"%.0f\", $1/1000}'")
    temp_str = f"{temp}°C" if temp and temp.isdigit() else "n/a"

    gpu = run_cmd("cat /sys/devices/gpu.0/load 2>/dev/null")
    gpu_str = f"{int(gpu) // 10}%" if gpu and gpu.isdigit() else "n/a"

    docker = str(docker_running_count())
    root = state.project_root
    project_count = len([p for p in root.iterdir() if p.is_dir()]) if root.exists() else 0
    project_name = state.active_project.name if state.active_project else "[dim]-[/dim]"

    print_kv(
        [
            ("Host", socket.gethostname()),
            ("Uptime", uptime),
            ("RAM", f"{vm.used // (1024 * 1024)}M / {vm.total // (1024 * 1024)}M ({vm.percent:.0f}%)"),
            ("NVMe", f"{disk.used // (1024**3)}G / {disk.total // (1024**3)}G ({disk.percent:.0f}%)"),
            ("Temp", temp_str),
            ("GPU", gpu_str),
            ("LAN", ip),
            ("Power", power),
            ("Docker", f"{docker} running"),
            ("Projects", str(project_count)),
            ("Active", project_name),
        ],
        title="System Status",
    )
    return CommandResult(ok=True, style="silent", refresh=True)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def cmd_health(state: TuiState, _: list[str]) -> CommandResult:
    """Health diagnostic panel."""
    rows: list[tuple[str, str]] = []

    # Load average
    try:
        load = psutil.getloadavg()
        rows.append(("Load Average", f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}"))
    except Exception:
        rows.append(("Load Average", "n/a"))

    # RAM
    vm = psutil.virtual_memory()
    rows.append(("RAM", f"{vm.percent:.0f}% ({vm.used // (1024 * 1024)}M / {vm.total // (1024 * 1024)}M)"))

    # Swap
    swap = psutil.swap_memory()
    rows.append(("Swap", f"{swap.percent:.0f}% ({swap.used // (1024 * 1024)}M / {swap.total // (1024 * 1024)}M)"))

    # NVMe health
    cw = content_width()
    nvme_health = run_cmd("sudo smartctl -A /dev/nvme0n1 2>/dev/null | grep 'Percentage Used'", timeout=5)
    if nvme_health and ":" in nvme_health:
        rows.append(("NVMe Health", truncate(nvme_health.split(":", 1)[-1].strip(), cw)))
    else:
        rows.append(("NVMe Health", "n/a"))

    # Temperature
    temp = run_cmd("cat /sys/devices/virtual/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.0f\", $1/1000}'")
    rows.append(("Temperature", f"{temp}°C" if temp and temp.isdigit() else "n/a"))

    # Docker
    rows.append(("Docker", f"{docker_running_count()} running"))

    # Uptime
    uptime_s = int(dt.datetime.now().timestamp() - psutil.boot_time())
    days, rem = divmod(uptime_s, 86400)
    hours = rem // 3600
    if days:
        rows.append(("Uptime", f"up {days} days, {hours} hours"))
    else:
        rows.append(("Uptime", f"up {hours} hours"))

    # fail2ban
    f2b = run_cmd("sudo fail2ban-client status sshd 2>/dev/null | grep 'Currently banned'", timeout=5)
    if f2b and ":" in f2b:
        rows.append(("fail2ban", truncate(f2b.split(":", 1)[-1].strip(), cw)))
    else:
        f2b_active = run_cmd("systemctl is-active fail2ban 2>/dev/null")
        rows.append(("fail2ban", f2b_active if f2b_active else "n/a"))

    print_styled_panel("System Health", rows)
    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /setup
# ---------------------------------------------------------------------------


def _setup_run_step(state: TuiState, user_input: str) -> CommandResult:
    """Run a specific setup step by number."""
    num_str = user_input.strip()
    if not num_str.isdigit():
        print_error("Please enter a step number (1-8) or [bold]q[/bold] to quit.")
        return CommandResult(
            ok=False,
            style="silent",
            prompt="Step",
            pending_handler=_setup_run_step,
            wizard_step=(1, 1, "Setup"),
        )

    num = int(num_str)
    status = check_setup_status()
    if num < 1 or num > len(status):
        print_error(f"Invalid step. Available: 1-{len(status)}")
        return CommandResult(
            ok=False,
            style="silent",
            prompt="Step",
            pending_handler=_setup_run_step,
            wizard_step=(1, 1, "Setup"),
        )

    step, _done = status[num - 1]
    print_info(f"Running step {num}: [bold]{step.name}[/bold] ...")

    def _run() -> tuple[bool, str]:
        return run_setup_step(step)

    try:
        ok, output = spinner_run(f"Running {step.name}...", _run)
    except OSError as exc:
        print_error(f"Failed: {exc}")
        return CommandResult(ok=False, style="silent")

    if ok:
        print_success(f"Step {num} complete: [bold]{step.name}[/bold]")
    else:
        print_warning(f"Step {num} may have issues. Check output.")
        if output:
            console.print(f"{content_pad()}[dim]{output[:200]}[/dim]", highlight=False)

    # Show updated status
    updated = check_setup_status()
    items = [(s.name, done) for s, done in updated]
    print_progress("Setup Progress", items)

    print_info("Enter step number to run, or [bold]q[/bold] to quit:")
    return CommandResult(
        ok=True,
        style="silent",
        prompt="Step",
        pending_handler=_setup_run_step,
        wizard_step=(1, 1, "Setup"),
    )


def cmd_setup(state: TuiState, _: list[str]) -> CommandResult:
    """Interactive setup wizard showing all 8 steps."""
    status = check_setup_status()
    items = [(step.name, done) for step, done in status]
    print_progress("Setup Steps", items)

    pad = content_pad()
    for step, done in status:
        icon = "[green]✓[/green]" if done else "[dim]○[/dim]"
        num = f"[cyan]{step.number}[/cyan]"
        console.print(f"{pad}   {icon} {num}  {step.description}", highlight=False)
    console.print()

    print_info("Enter step number to run, or [bold]q[/bold] to quit:")
    return CommandResult(
        ok=True,
        style="silent",
        prompt="Step",
        pending_handler=_setup_run_step,
        wizard_step=(1, 1, "Setup"),
    )


# ---------------------------------------------------------------------------
# /docker
# ---------------------------------------------------------------------------


def cmd_docker(state: TuiState, _: list[str]) -> CommandResult:
    """Show Docker container status."""
    containers = list_containers(all_containers=True)
    if not containers:
        print_info("No Docker containers found.")
        return CommandResult(ok=True, style="silent")

    from arasul_tui.core.theme import ICON_DOT_OFF, ICON_DOT_ON

    cw = content_width()
    rows: list[tuple[str, str]] = []
    for c in containers:
        status = c.status
        icon = ICON_DOT_ON if "Up" in status else ICON_DOT_OFF
        name = truncate(c.name, 24)
        image = truncate(c.image, cw - 10)
        rows.append((f"{icon} {name}", f"{image} \u2014 {status}"))

    print_styled_panel("Docker Containers", rows)
    return CommandResult(ok=True, style="silent")
