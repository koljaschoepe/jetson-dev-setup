"""n8n workflow automation — /n8n command handler.

Smart command that does the right thing based on current state:
- Not installed  -> install + start + guide through API key + MCP
- Stopped        -> start
- No API key     -> prompt for key + configure MCP
- All good       -> show status dashboard

Only subcommand: /n8n stop
"""

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
    rows.append(("Web UI", f"[cyan]{N8N_BASE_URL}[/cyan]"))
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

        print_info("Installing n8n + PostgreSQL...")

        def _run_setup() -> str:
            return run_cmd("sudo bash scripts/09-n8n-setup.sh 2>&1", timeout=300)

        try:
            output = spinner_run("Installing n8n...", _run_setup)
        except Exception as exc:
            print_error(f"Installation failed: {exc}")
            return CommandResult(ok=False, style="silent")

        if not n8n_is_running():
            print_warning("Script finished but n8n is not running.")
            if output:
                pad = content_pad()
                console.print(f"{pad}[dim]{output[-300:]}[/dim]", highlight=False)
            return CommandResult(ok=False, style="silent")

        print_success("n8n installed and running!")

    # --- Step 2: Start if stopped ---
    if n8n_is_installed() and not n8n_is_running():
        def _run_start() -> str:
            return n8n_compose_cmd("up -d")

        spinner_run("Starting n8n...", _run_start)

        if not n8n_is_running():
            print_error("n8n failed to start.")
            return CommandResult(ok=False, style="silent")

        print_success(f"n8n started at [bold]{N8N_BASE_URL}[/bold]")

    # --- Step 3: API key if missing ---
    api_key = n8n_get_api_key()
    if not api_key:
        console.print()
        print_info(f"Open [bold cyan]{N8N_BASE_URL}/settings/api[/bold cyan] and create an API key.")
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
