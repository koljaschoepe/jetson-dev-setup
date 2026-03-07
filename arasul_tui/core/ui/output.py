"""Console instance, print helpers, and spinner utilities."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

from arasul_tui.core.theme import (
    DIM,
    ERROR,
    ICON_ARROW,
    ICON_FAIL,
    ICON_OK,
    PRIMARY,
    SUCCESS,
    WARNING,
)

if TYPE_CHECKING:
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


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

# Box-drawing and separator characters
_HLINE = "\u2500"  # ─
_DOT = "\u00b7"  # ·
_DEG = "\u00b0"  # °
_CHECK = "\u2713"  # ✓


def _hline(n: int) -> str:
    """Return n horizontal line characters."""
    return _HLINE * n


def _dim_hline(n: int) -> str:
    """Return n dim horizontal line characters with Rich markup."""
    return f"[{DIM}]{_hline(n)}[/{DIM}]"


def _frame_left_pad() -> int:
    """Fixed left margin for left-aligned layout."""
    return 1


def content_pad() -> str:
    """Left padding to align output with frame interior."""
    return " " * (_frame_left_pad() + 3)


def _adaptive_width() -> int:
    """Calculate optimal panel width based on terminal size with margins."""
    return max(MIN_WIDTH, min(console.width - 2, MAX_WIDTH))


# ---------------------------------------------------------------------------
# Print functions
# ---------------------------------------------------------------------------


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
        from rich import box
        from rich.panel import Panel

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


def print_separator(state: Any = None) -> None:
    """Print a thin separator line."""
    pad = " " * _frame_left_pad()
    console.print(f"{pad}{_dim_hline(50)}", highlight=False)


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------


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
