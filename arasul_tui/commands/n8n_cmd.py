"""n8n workflow automation — /n8n command handler."""

from __future__ import annotations

from arasul_tui.core.n8n_client import (
    N8N_BASE_URL,
    N8N_DIR,
    n8n_compose_cmd,
    n8n_get_api_key,
    n8n_health,
    n8n_is_installed,
    n8n_is_running,
    n8n_list_workflows,
    n8n_save_api_key,
)
from arasul_tui.core.n8n_mcp import (
    configure_n8n_mcp,
    is_n8n_mcp_configured,
    remove_n8n_mcp,
)
from arasul_tui.core.shell import run_cmd
from arasul_tui.core.state import TuiState
from arasul_tui.core.types import CommandResult
from arasul_tui.core.ui import (
    console,
    content_pad,
    print_error,
    print_info,
    print_styled_panel,
    print_success,
    print_warning,
    spinner_run,
)

# ---------------------------------------------------------------------------
# /n8n or /n8n status — dashboard
# ---------------------------------------------------------------------------

def _show_status() -> CommandResult:
    rows: list[tuple[str, str]] = []

    if not n8n_is_installed():
        rows.append(("n8n", "[dim]not installed[/dim]"))
        rows.append(("Install", "[cyan]/n8n install[/cyan]"))
        print_styled_panel("n8n Automation", rows)
        return CommandResult(ok=True, style="silent")

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
        rows.append(("API Key", "[dim]not set[/dim] [cyan]/n8n api-key[/cyan]"))

    # Workflows (only if API key is set and n8n is running)
    if api_key and api == "healthy":
        workflows = n8n_list_workflows()
        active = sum(1 for w in workflows if w.get("active"))
        rows.append(("Workflows", f"{len(workflows)} total, {active} active"))

    # MCP server
    if is_n8n_mcp_configured():
        rows.append(("MCP Server", "[green]configured[/green]"))
    else:
        rows.append(("MCP Server", "[dim]not set[/dim] [cyan]/n8n mcp[/cyan]"))

    # URLs
    rows.append(("Web UI", f"[cyan]{N8N_BASE_URL}[/cyan]"))
    rows.append(("Data", f"[dim]{N8N_DIR}[/dim]"))

    print_styled_panel("n8n Automation", rows)
    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /n8n install
# ---------------------------------------------------------------------------

def _do_install() -> CommandResult:
    if n8n_is_installed() and n8n_is_running():
        print_success("n8n is already installed and running.")
        return _show_status()

    script = run_cmd("command -v sudo 2>/dev/null", timeout=2)
    if not script:
        print_error("sudo not available.")
        return CommandResult(ok=False, style="silent")

    print_info("Running n8n setup script...")

    def _run_setup() -> str:
        return run_cmd("sudo bash scripts/09-n8n-setup.sh 2>&1", timeout=300)

    try:
        output = spinner_run("Installing n8n + PostgreSQL...", _run_setup)
    except Exception as exc:
        print_error(f"Installation failed: {exc}")
        return CommandResult(ok=False, style="silent")

    if n8n_is_running():
        print_success("n8n installed and running!")
        console.print()
        print_info(f"Open [bold]{N8N_BASE_URL}[/bold] to create your account.")
        print_info("Then set up API key: [bold]/n8n api-key[/bold]")
    else:
        print_warning("Script finished but n8n is not running.")
        if output:
            pad = content_pad()
            console.print(f"{pad}[dim]{output[-300:]}[/dim]", highlight=False)

    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /n8n start
# ---------------------------------------------------------------------------

def _do_start() -> CommandResult:
    if not n8n_is_installed():
        print_warning("n8n not installed. Run [bold]/n8n install[/bold] first.")
        return CommandResult(ok=False, style="silent")

    if n8n_is_running():
        print_success("n8n is already running.")
        return CommandResult(ok=True, style="silent")

    def _run_start() -> str:
        return n8n_compose_cmd("up -d")

    spinner_run("Starting n8n...", _run_start)

    if n8n_is_running():
        print_success(f"n8n started at [bold]{N8N_BASE_URL}[/bold]")
    else:
        print_error("n8n failed to start. Check [bold]/n8n logs[/bold]")

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
# /n8n logs
# ---------------------------------------------------------------------------

def _do_logs() -> CommandResult:
    if not n8n_is_installed():
        print_warning("n8n not installed.")
        return CommandResult(ok=False, style="silent")

    output = n8n_compose_cmd("logs --tail=30 n8n")
    pad = content_pad()
    console.print()
    if output and not output.startswith("Error"):
        for line in output.splitlines()[-30:]:
            console.print(f"{pad}[dim]{line}[/dim]", highlight=False)
    else:
        print_info("No logs available.")
    console.print()
    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /n8n workflows
# ---------------------------------------------------------------------------

def _do_workflows() -> CommandResult:
    if not n8n_is_running():
        print_warning("n8n is not running. Start with [bold]/n8n start[/bold]")
        return CommandResult(ok=False, style="silent")

    api_key = n8n_get_api_key()
    if not api_key:
        print_warning("API key not set. Run [bold]/n8n api-key[/bold] first.")
        return CommandResult(ok=False, style="silent")

    workflows = n8n_list_workflows()
    if not workflows:
        print_info("No workflows found.")
        return CommandResult(ok=True, style="silent")

    rows: list[tuple[str, str]] = []
    for wf in workflows:
        name = wf.get("name", "untitled")
        active = wf.get("active", False)
        status = "[green]active[/green]" if active else "[dim]inactive[/dim]"
        wf_id = wf.get("id", "")
        rows.append((f"#{wf_id}", f"{name}  {status}"))

    print_styled_panel(f"Workflows ({len(workflows)})", rows)
    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /n8n open
# ---------------------------------------------------------------------------

def _do_open() -> CommandResult:
    print_info(f"n8n Web UI: [bold cyan]{N8N_BASE_URL}[/bold cyan]")
    if n8n_is_running():
        print_info("Status: [green]running[/green]")
    else:
        print_warning("n8n is not running. Start with [bold]/n8n start[/bold]")
    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /n8n api-key — wizard to set API key
# ---------------------------------------------------------------------------

def _do_api_key_start() -> CommandResult:
    current = n8n_get_api_key()
    if current:
        print_info(f"Current API key: [dim]{current[:8]}...[/dim]")
    print_info("Get your API key from n8n: Settings > API > Create API Key")
    print_info(f"Web UI: [bold cyan]{N8N_BASE_URL}/settings/api[/bold cyan]")
    return CommandResult(
        ok=True,
        style="silent",
        prompt="Paste API key",
        pending_handler=_api_key_finish,
        wizard_step=(1, 1, "API Key"),
    )


def _api_key_finish(state: TuiState, raw: str) -> CommandResult:
    key = raw.strip()
    if not key:
        print_error("No key provided.")
        return CommandResult(ok=False, style="silent")

    n8n_save_api_key(key)
    print_success(f"API key saved: [dim]{key[:8]}...[/dim]")
    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /n8n backup — manual backup of workflows + database
# ---------------------------------------------------------------------------

def _do_backup() -> CommandResult:
    if not n8n_is_installed():
        print_warning("n8n not installed.")
        return CommandResult(ok=False, style="silent")

    if not n8n_is_running():
        print_warning("n8n is not running. Start with [bold]/n8n start[/bold]")
        return CommandResult(ok=False, style="silent")

    results: list[tuple[str, bool]] = []

    # Workflow export
    def _export_workflows() -> str:
        return n8n_compose_cmd(
            "exec -T n8n n8n export:workflow --all --separate --output=/home/node/workflows/"
        )

    try:
        spinner_run("Exporting workflows...", _export_workflows)
        results.append(("Workflow export", True))
    except Exception:
        results.append(("Workflow export", False))

    # PostgreSQL dump
    def _pg_dump() -> str:
        return run_cmd(
            "bash -c '"
            'set -a; source /mnt/nvme/n8n/.env 2>/dev/null; set +a; '
            "docker compose -f /mnt/nvme/n8n/docker-compose.yml exec -T postgres "
            'pg_dump -U "${N8N_DB_USER:-n8n}" -d n8n 2>/dev/null '
            "| gzip > /mnt/nvme/backups/n8n/n8n-postgres-$(date +%Y%m%d-%H%M%S).sql.gz"
            "'",
            timeout=60,
        )

    try:
        spinner_run("Dumping PostgreSQL...", _pg_dump)
        results.append(("PostgreSQL dump", True))
    except Exception:
        results.append(("PostgreSQL dump", False))

    from arasul_tui.core.ui import print_progress

    print_progress("Backup Results", results)

    all_ok = all(ok for _, ok in results)
    if all_ok:
        print_info("Backups at: [dim]/mnt/nvme/backups/n8n/[/dim] + [dim]/mnt/nvme/n8n/workflows/[/dim]")
    return CommandResult(ok=all_ok, style="silent")


# ---------------------------------------------------------------------------
# /n8n mcp — configure MCP server for Claude Code
# ---------------------------------------------------------------------------

def _do_mcp(args: list[str]) -> CommandResult:
    sub = args[0].lower() if args else ""

    if sub == "remove":
        ok, msg = remove_n8n_mcp()
        if ok:
            print_success(msg)
        else:
            print_error(msg)
        return CommandResult(ok=ok, style="silent")

    # Default: configure / update
    if is_n8n_mcp_configured() and not sub:
        print_success("n8n MCP server already configured.")
        print_info("Use [bold]/n8n mcp remove[/bold] to remove, or [bold]/n8n mcp update[/bold] to refresh.")
        return CommandResult(ok=True, style="silent")

    api_key = n8n_get_api_key()
    if not api_key:
        print_warning("API key not set. Run [bold]/n8n api-key[/bold] first, then [bold]/n8n mcp[/bold].")
        return CommandResult(ok=False, style="silent")

    ok, msg = configure_n8n_mcp(api_key)
    if ok:
        print_success(msg)
        print_info("Claude Code can now access n8n workflows, credentials, and templates.")
    else:
        print_error(msg)
    return CommandResult(ok=ok, style="silent")


# ---------------------------------------------------------------------------
# /n8n (dispatcher)
# ---------------------------------------------------------------------------

def cmd_n8n(state: TuiState, args: list[str]) -> CommandResult:
    if not args:
        return _show_status()

    sub = args[0].lower()

    if sub == "status":
        return _show_status()
    if sub == "install":
        return _do_install()
    if sub == "start":
        return _do_start()
    if sub == "stop":
        return _do_stop()
    if sub == "logs":
        return _do_logs()
    if sub == "workflows":
        return _do_workflows()
    if sub == "open":
        return _do_open()
    if sub in ("api-key", "apikey", "key"):
        return _do_api_key_start()
    if sub == "mcp":
        return _do_mcp(args[1:])
    if sub == "backup":
        return _do_backup()

    print_error(f"Unknown: [bold]/n8n {sub}[/bold]")
    print_info(
        "Available: [bold]status[/bold], [bold]install[/bold], [bold]start[/bold], "
        "[bold]stop[/bold], [bold]logs[/bold], [bold]workflows[/bold], "
        "[bold]open[/bold], [bold]api-key[/bold], [bold]mcp[/bold], [bold]backup[/bold]"
    )
    return CommandResult(ok=False, style="silent")
