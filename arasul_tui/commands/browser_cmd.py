from __future__ import annotations

from arasul_tui.core.browser import (
    browser_health,
    browser_test,
    configure_mcp,
    install_browser,
    is_mcp_configured,
)
from arasul_tui.core.state import TuiState
from arasul_tui.core.types import CommandResult
from arasul_tui.core.ui import (
    print_error,
    print_info,
    print_styled_panel,
    print_success,
)


def cmd_browser(state: TuiState, args: list[str]) -> CommandResult:
    sub = args[0] if args else "status"

    if sub == "status":
        rows = browser_health()
        print_styled_panel("Browser", rows)
        return CommandResult(ok=True, style="silent")

    if sub == "test":
        ok, lines = browser_test()
        for line in lines:
            (print_success if ok else print_error)(line)
        return CommandResult(ok=ok, style="silent")

    if sub == "install":
        ok, lines = install_browser()
        if ok and not is_mcp_configured():
            try:
                mcp_ok, mcp_msg = configure_mcp()
                lines.append(mcp_msg)
            except OSError as exc:
                lines.append(f"MCP config failed: {exc}")
        for line in lines:
            (print_success if ok else print_error)(line)
        return CommandResult(ok=ok, style="silent")

    if sub == "mcp":
        if is_mcp_configured():
            print_success("Playwright MCP already configured.")
            return CommandResult(ok=True, style="silent")
        ok, msg = configure_mcp()
        if ok:
            print_success(msg)
        else:
            print_error(msg)
        return CommandResult(ok=ok, style="silent")

    print_error(f"Unknown subcommand: [bold]{sub}[/bold]")
    print_info("Available: [bold]status[/bold], [bold]test[/bold], [bold]install[/bold], [bold]mcp[/bold]")
    return CommandResult(ok=False, style="silent")
