from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

NVME_BROWSER_CACHE = Path("/mnt/nvme/playwright-browsers")
FALLBACK_BROWSER_CACHE = Path.home() / ".cache" / "ms-playwright"
CLAUDE_JSON = Path.home() / ".claude.json"


def _browsers_path() -> Path:
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env:
        return Path(env)
    if NVME_BROWSER_CACHE.exists():
        return NVME_BROWSER_CACHE
    return FALLBACK_BROWSER_CACHE


def _find_chromium_binary() -> Path | None:
    base = _browsers_path()
    if not base.exists():
        return None
    for candidate in base.rglob("chrome"):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    for candidate in base.rglob("chromium"):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def is_playwright_installed() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def is_chromium_installed() -> bool:
    return _find_chromium_binary() is not None


def ensure_browser() -> tuple[bool, str]:
    """Check if headless browser stack is ready. Returns (ok, message)."""
    if not is_playwright_installed():
        return False, "Playwright Python nicht installiert. Fuehre /browser install aus."
    if not is_chromium_installed():
        return False, "Chromium nicht gefunden. Fuehre /browser install aus."
    return True, "Playwright + Chromium bereit."


def browser_health() -> list[str]:
    """Detailed health check, returns status lines."""
    lines: list[str] = ["Browser Health-Check"]

    pw_ok = is_playwright_installed()
    if pw_ok:
        try:
            import playwright
            lines.append(f"  Playwright: v{playwright.__version__}")
        except Exception:
            lines.append("  Playwright: installiert (Version unbekannt)")
    else:
        lines.append("  Playwright: NICHT installiert")

    chrome_bin = _find_chromium_binary()
    if chrome_bin:
        lines.append(f"  Chromium: {chrome_bin}")
    else:
        lines.append("  Chromium: NICHT gefunden")

    cache = _browsers_path()
    lines.append(f"  Cache: {cache}")
    if cache.exists():
        try:
            size_mb = sum(f.stat().st_size for f in cache.rglob("*") if f.is_file()) / (1024 * 1024)
            lines.append(f"  Cache-Groesse: {size_mb:.0f} MB")
        except Exception:
            pass

    mcp_ok = is_mcp_configured()
    lines.append(f"  MCP Server: {'konfiguriert' if mcp_ok else 'NICHT konfiguriert'}")

    return lines


def browser_test() -> tuple[bool, list[str]]:
    """Launch headless Chromium and load a test page. Returns (ok, lines)."""
    ok, msg = ensure_browser()
    if not ok:
        return False, [msg]

    try:
        env = os.environ.copy()
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(_browsers_path())
        result = subprocess.run(
            [
                "python3", "-c",
                "from playwright.sync_api import sync_playwright\n"
                "with sync_playwright() as p:\n"
                "    b = p.chromium.launch(headless=True)\n"
                "    pg = b.new_page()\n"
                "    pg.goto('https://httpbin.org/get', timeout=10000)\n"
                "    status = pg.title()\n"
                "    b.close()\n"
                "    print('OK')\n",
            ],
            capture_output=True, text=True, timeout=30, env=env,
        )
        if result.returncode == 0 and "OK" in result.stdout:
            return True, ["Browser-Test erfolgreich: Chromium headless laeuft."]
        stderr = result.stderr.strip()[:200] if result.stderr else "unbekannter Fehler"
        return False, [f"Browser-Test fehlgeschlagen: {stderr}"]
    except subprocess.TimeoutExpired:
        return False, ["Browser-Test Timeout (30s). Netzwerk oder Chromium Problem."]
    except Exception as exc:
        return False, [f"Browser-Test Fehler: {exc}"]


def install_browser() -> tuple[bool, list[str]]:
    """Install/update Playwright + Chromium. Requires system packages pre-installed."""
    lines: list[str] = []

    if not is_playwright_installed():
        lines.append("Installiere Playwright...")
        result = subprocess.run(
            ["pip3", "install", "playwright"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            return False, lines + [f"pip install playwright fehlgeschlagen: {result.stderr[:200]}"]
        lines.append("Playwright installiert.")

    cache = _browsers_path()
    lines.append(f"Lade Chromium nach {cache}...")
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(cache)
    result = subprocess.run(
        ["python3", "-m", "playwright", "install", "chromium"],
        capture_output=True, text=True, timeout=300, env=env,
    )
    if result.returncode != 0:
        return False, lines + [f"Chromium-Download fehlgeschlagen: {result.stderr[:200]}"]
    lines.append("Chromium heruntergeladen.")

    return True, lines


def is_mcp_configured() -> bool:
    """Check if Playwright MCP server is configured in claude.json."""
    try:
        data = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
        return "playwright" in data.get("mcpServers", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return False


def configure_mcp() -> tuple[bool, str]:
    """Add Playwright MCP server to claude.json."""
    try:
        data = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    if "mcpServers" not in data:
        data["mcpServers"] = {}

    data["mcpServers"]["playwright"] = {
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest", "--headless"],
        "env": {
            "PLAYWRIGHT_BROWSERS_PATH": str(_browsers_path()),
        },
    }

    CLAUDE_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True, "Playwright MCP Server in ~/.claude.json konfiguriert."
