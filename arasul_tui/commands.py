from __future__ import annotations

from pathlib import Path
import datetime as dt
import socket
import subprocess

import psutil

from arasul_tui.core.auth import is_claude_configured, save_claude_auth, TOKEN_PREFIX
from arasul_tui.core.browser import (
    browser_health,
    browser_test,
    configure_mcp,
    ensure_browser,
    install_browser,
    is_mcp_configured,
)
from arasul_tui.core.state import TuiState
from arasul_tui.core.types import CommandResult
from arasul_tui.core.projects import register_project
from arasul_tui.core.ui import (
    console,
    _content_pad,
    print_step,
    print_success,
    print_error,
    print_info,
    print_warning,
    print_kv,
    print_table,
    spinner_run,
)


def _run(cmd: str, timeout: int = 4) -> str:
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        return out
    except Exception as exc:
        return f"Fehler: {exc}"


def _project_root(state: TuiState) -> Path | None:
    root = state.project_root
    try:
        root.mkdir(parents=True, exist_ok=True)
        return root
    except Exception:
        return None


def _project_dirs(root: Path) -> list[Path]:
    try:
        return sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
    except Exception:
        return []


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

def cmd_help(_: TuiState, __: list[str]) -> CommandResult:
    pad = _content_pad()
    console.print()
    console.print(f"{pad}[bold]Schnelltasten[/bold]", highlight=False)
    console.print(f"{pad}[cyan]1-9[/cyan]  [dim]Projekt per Nummer waehlen[/dim]", highlight=False)
    console.print(f"{pad}[cyan]n[/cyan]    [dim]Neues Projekt erstellen[/dim]", highlight=False)
    console.print(f"{pad}[cyan]d[/cyan]    [dim]Projekt loeschen[/dim]", highlight=False)
    console.print(f"{pad}[cyan]c[/cyan]    [dim]Claude Code starten[/dim]", highlight=False)
    console.print(f"{pad}[cyan]x[/cyan]    [dim]Codex starten[/dim]", highlight=False)
    console.print(f"{pad}[cyan]b[/cyan]    [dim]Zurueck zur Uebersicht[/dim]", highlight=False)
    console.print()
    console.print(f"{pad}[bold]Projekte[/bold]", highlight=False)
    console.print(f"{pad}[cyan]/open <name>[/cyan]    [dim]Projekt oeffnen[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/create[/cyan]         [dim]Neues Projekt erstellen[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/clone[/cyan]          [dim]GitHub Repo klonen[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/delete[/cyan]         [dim]Projekt loeschen[/dim]", highlight=False)
    console.print()
    console.print(f"{pad}[bold]AI Coding[/bold]", highlight=False)
    console.print(f"{pad}[cyan]/claude[/cyan]         [dim]Claude Code starten[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/codex[/cyan]          [dim]Codex starten[/dim]", highlight=False)
    console.print()
    console.print(f"{pad}[bold]System[/bold]", highlight=False)
    console.print(f"{pad}[cyan]/status[/cyan]         [dim]Systemstatus[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/git[/cyan]            [dim]GitHub einrichten[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/browser[/cyan]        [dim]Headless Browser[/dim]", highlight=False)
    console.print()
    console.print(f"{pad}[cyan]/help[/cyan]           [dim]Diese Hilfe[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/exit[/cyan]           [dim]Beenden[/dim]", highlight=False)
    console.print()
    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

def cmd_status(state: TuiState, _: list[str]) -> CommandResult:
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/mnt/nvme" if Path("/mnt/nvme").exists() else "/")
    uptime_s = int(dt.datetime.now().timestamp() - psutil.boot_time())
    hours, rem = divmod(uptime_s, 3600)
    mins = rem // 60
    uptime = f"{hours}h {mins}m" if hours else f"{mins}m"

    ip = _run("ip -4 addr show enP8p1s0 | awk '/inet/{print $2}' | cut -d/ -f1")
    if not ip:
        ip = "n/a"
    power = _run("sudo nvpmodel -q | head -1 | sed 's/NV Power Mode: //'") or "n/a"
    temp = _run(
        "cat /sys/devices/virtual/thermal/thermal_zone0/temp | awk '{printf \"%.0f\", $1/1000}'"
    )
    temp_str = f"{temp}°C" if temp and temp.isdigit() else "n/a"
    docker = _run("docker ps -q 2>/dev/null | wc -l | tr -d ' '") or "0"
    root = state.project_root
    project_count = len(_project_dirs(root)) if root.exists() else 0
    project_name = state.active_project.name if state.active_project else "[dim]-[/dim]"

    print_kv(
        [
            ("Host", socket.gethostname()),
            ("Uptime", uptime),
            ("RAM", f"{vm.used // (1024*1024)}M / {vm.total // (1024*1024)}M ({vm.percent:.0f}%)"),
            ("NVMe", f"{disk.used // (1024**3)}G / {disk.total // (1024**3)}G ({disk.percent:.0f}%)"),
            ("Temp", temp_str),
            ("LAN", ip),
            ("Power", power),
            ("Docker", f"{docker} running"),
            ("Projekte", str(project_count)),
            ("Aktiv", project_name),
        ],
        title="System Status",
    )
    return CommandResult(ok=True, style="silent", refresh=True)


# ---------------------------------------------------------------------------
# /create
# ---------------------------------------------------------------------------

def _create_finish(state: TuiState, user_input: str) -> CommandResult:
    name = user_input.strip().replace(" ", "-")
    if not name:
        print_error("Projektname darf nicht leer sein.")
        return CommandResult(ok=False, style="silent")
    root = _project_root(state)
    if not root:
        print_error(f"Projekt-Root nicht beschreibbar: {state.project_root}")
        return CommandResult(ok=False, style="silent")
    target = root / name
    if target.exists():
        print_error(f"Projekt existiert bereits: {target}")
        return CommandResult(ok=False, style="silent")
    target.mkdir(parents=True, exist_ok=False)
    register_project(name=name, path=target, provider_default="claude")
    state.active_project = target
    print_success(f"Projekt erstellt: [bold]{name}[/bold]")
    print_info(f"Pfad: [dim]{target}[/dim]")
    return CommandResult(ok=True, style="silent", refresh=True)


def cmd_create(state: TuiState, args: list[str]) -> CommandResult:
    if args:
        return _create_finish(state, args[0])
    print_info("Wie soll das neue Projekt heissen?")
    return CommandResult(
        ok=True,
        style="silent",
        prompt="Projektname",
        pending_handler=_create_finish,
        wizard_step=(1, 1, "Projekt"),
    )


# ---------------------------------------------------------------------------
# /clone
# ---------------------------------------------------------------------------

def _clone_finish(state: TuiState, user_input: str) -> CommandResult:
    url = user_input.strip()
    if not url:
        print_error("URL darf nicht leer sein.")
        return CommandResult(ok=False, style="silent")

    if not (url.startswith("https://") or url.startswith("git@")):
        print_error("Ungueltige URL. Erwartet: [dim]https://github.com/user/repo[/dim]")
        return CommandResult(ok=False, style="silent")

    repo_name = url.rstrip("/").split("/")[-1].removesuffix(".git")
    if not repo_name:
        print_error("Konnte Repo-Name nicht aus URL ableiten.")
        return CommandResult(ok=False, style="silent")

    root = _project_root(state)
    if not root:
        print_error(f"Projekt-Root nicht beschreibbar: {state.project_root}")
        return CommandResult(ok=False, style="silent")

    target = root / repo_name
    if target.exists():
        print_error(f"Ordner existiert bereits: [bold]{repo_name}[/bold]")
        return CommandResult(ok=False, style="silent")

    def _do_clone() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "clone", url, str(target)],
            capture_output=True, text=True, timeout=120,
        )

    try:
        result = spinner_run(f"Klone [bold]{repo_name}[/bold] ...", _do_clone)
    except Exception as exc:
        print_error(f"Clone fehlgeschlagen: {exc}")
        return CommandResult(ok=False, style="silent")

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        print_error(f"git clone fehlgeschlagen: {err}")
        return CommandResult(ok=False, style="silent")

    register_project(name=repo_name, path=target, provider_default="claude")
    state.active_project = target
    print_success(f"Repo geklont: [bold]{repo_name}[/bold]")
    print_info(f"Pfad: [dim]{target}[/dim]")
    return CommandResult(ok=True, style="silent", refresh=True)


def cmd_clone(state: TuiState, args: list[str]) -> CommandResult:
    if args:
        return _clone_finish(state, args[0])
    print_info("GitHub URL eingeben (z.B. [dim]https://github.com/user/repo[/dim])")
    return CommandResult(
        ok=True,
        style="silent",
        prompt="URL",
        pending_handler=_clone_finish,
        wizard_step=(1, 1, "Clone"),
    )


# ---------------------------------------------------------------------------
# /open
# ---------------------------------------------------------------------------

def cmd_open(state: TuiState, args: list[str]) -> CommandResult:
    root = state.project_root
    if not root.exists():
        print_error(f"Projekt-Root nicht gefunden: {root}")
        return CommandResult(ok=False, style="silent")
    if not args:
        names = [p.name for p in _project_dirs(root)]
        if not names:
            print_warning("Keine Projekte gefunden.")
            print_info("Erstelle eins mit [bold]n[/bold] oder [bold]/create[/bold]")
            return CommandResult(ok=False, style="silent")
        print_info("Usage: [bold]/open <name>[/bold] oder waehle per Nummer")
        return CommandResult(ok=False, style="silent")

    name = args[0]
    target = (root / name).resolve()
    if not target.exists() or not target.is_dir():
        print_error(f"Projekt nicht gefunden: [bold]{name}[/bold]")
        return CommandResult(ok=False, style="silent")
    state.active_project = target
    return CommandResult(ok=True, style="silent", refresh=True)


# ---------------------------------------------------------------------------
# /claude, /codex
# ---------------------------------------------------------------------------

def _launch_inline(state: TuiState, command: str) -> CommandResult:
    if not state.active_project:
        print_warning("Kein aktives Projekt.")
        print_info("Setze eins mit [bold]/open <name>[/bold]")
        return CommandResult(ok=False, style="silent")
    binary = subprocess.run(
        f"command -v {command}",
        shell=True,
        check=False,
        capture_output=True,
        text=True,
    )
    if binary.returncode != 0:
        print_error(f"Binary nicht gefunden: [bold]{command}[/bold]")
        return CommandResult(ok=False, style="silent")
    print_info(f"Starte [bold]{command}[/bold] in [dim]{state.active_project}[/dim] ...")
    return CommandResult(
        ok=True,
        style="silent",
        quit_app=True,
        launch_command=command,
        launch_cwd=state.active_project,
    )


# ---------------------------------------------------------------------------
# /git — GitHub Setup
# ---------------------------------------------------------------------------

def _git_status_lines() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []

    gh = _run("command -v gh && gh --version | head -1", timeout=3)
    if "gh version" in gh:
        ver = gh.splitlines()[-1].strip()
        rows.append(("gh CLI", f"[green]✓[/green] {ver}"))
    else:
        rows.append(("gh CLI", "[red]✗[/red] nicht installiert"))

    auth = _run("gh auth status 2>&1", timeout=5)
    if "Logged in" in auth:
        account = ""
        for line in auth.splitlines():
            if "account" in line.lower():
                parts = line.strip().split()
                for i, p in enumerate(parts):
                    if p == "account" and i + 1 < len(parts):
                        account = parts[i + 1]
                        break
                break
        rows.append(("Auth", f"[green]✓[/green] {account}" if account else "[green]✓[/green] eingeloggt"))
    else:
        rows.append(("Auth", "[red]✗[/red] nicht eingeloggt"))

    name = _run("git config --global user.name")
    email = _run("git config --global user.email")
    rows.append(("Git Name", name or "[dim]nicht gesetzt[/dim]"))
    rows.append(("Git Email", email or "[dim]nicht gesetzt[/dim]"))

    ssh_key = Path.home() / ".ssh" / "id_ed25519.pub"
    if ssh_key.exists():
        rows.append(("SSH Key", f"[green]✓[/green] [dim]{ssh_key}[/dim]"))
    else:
        rows.append(("SSH Key", "[dim]nicht vorhanden[/dim]"))

    ssh_test = _run("ssh -o StrictHostKeyChecking=no -T git@github.com 2>&1", timeout=5)
    if "successfully authenticated" in ssh_test.lower():
        user = ""
        for part in ssh_test.split():
            if part.endswith("!"):
                user = part.rstrip("!")
                break
        rows.append(("GitHub SSH", f"[green]✓[/green] {user}" if user else "[green]✓[/green]"))
    else:
        rows.append(("GitHub SSH", "[dim]nicht verbunden[/dim]"))

    cred = _run("git config --global credential.helper")
    if cred:
        rows.append(("Credentials", f"[green]✓[/green] {cred}"))

    return rows


def _git_install_gh() -> tuple[bool, str]:
    check = _run("command -v gh", timeout=2)
    if check and "gh" in check:
        ver = _run("gh --version | head -1", timeout=3)
        return True, ver or "installiert"

    def _do_install() -> str:
        install_cmd = (
            "sudo mkdir -p -m 755 /etc/apt/keyrings && "
            "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg "
            "| sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null && "
            "sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg && "
            'echo "deb [arch=$(dpkg --print-architecture) '
            "signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] "
            'https://cli.github.com/packages stable main" '
            "| sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null && "
            "sudo apt-get update -qq && "
            "sudo apt-get install -y -qq gh"
        )
        return _run(install_cmd, timeout=120)

    spinner_run("gh CLI wird installiert...", _do_install)

    check2 = _run("command -v gh", timeout=2)
    if check2 and "gh" in check2:
        ver = _run("gh --version | head -1", timeout=3)
        return True, ver or "installiert"
    return False, "Installation fehlgeschlagen"


def _git_setup_known_hosts() -> None:
    known_hosts = Path.home() / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = known_hosts.read_text(encoding="utf-8") if known_hosts.exists() else ""
    except OSError:
        existing = ""
    if "github.com" not in existing:
        _run("ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null", timeout=10)


def _git_wizard_start(state: TuiState, user_input: str) -> CommandResult:
    # Step 1: gh CLI
    print_step(1, 3, "GitHub Setup")

    ok, ver_or_err = _git_install_gh()
    if not ok:
        print_error(ver_or_err)
        return CommandResult(ok=False, style="silent")

    print_success(f"gh CLI [dim]{ver_or_err}[/dim]")

    _git_setup_known_hosts()

    # Already authenticated?
    auth_check = _run("gh auth status 2>&1", timeout=5)
    if "Logged in" in auth_check:
        print_success("Bereits authentifiziert!")
        _run("gh auth setup-git", timeout=5)
        print_success("Git Credential Helper konfiguriert")
        console.print()
        print_kv(_git_status_lines(), title="GitHub Status")
        return CommandResult(ok=True, style="silent", refresh=True)

    # Step 2: Token
    print_step(2, 3, "GitHub Setup")

    pad = _content_pad()
    print_info("Personal Access Token (classic) erstellen:")
    console.print()
    console.print(f"{pad}[cyan bold]https://github.com/settings/tokens/new[/cyan bold]", highlight=False)
    console.print()
    console.print(f"{pad}[dim]Scopes:[/dim] [bold]repo[/bold], [bold]read:org[/bold], [bold]workflow[/bold]", highlight=False)
    console.print()

    return CommandResult(
        ok=True,
        style="silent",
        prompt="Token",
        pending_handler=_git_wizard_auth_token,
        wizard_step=(2, 3, "Token"),
    )


def _git_wizard_auth_token(state: TuiState, user_input: str) -> CommandResult:
    token = user_input.strip()
    if not token:
        print_error("Token darf nicht leer sein.")
        return CommandResult(
            ok=False,
            style="silent",
            prompt="Token",
            pending_handler=_git_wizard_auth_token,
            wizard_step=(2, 3, "Token"),
        )

    def _do_auth() -> subprocess.CompletedProcess:
        return subprocess.run(
            "gh auth login --with-token",
            input=token,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )

    result = spinner_run("Authentifiziere...", _do_auth)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()[:150]
        print_error(f"Fehlgeschlagen: [dim]{err}[/dim]")
        console.print(f"{_content_pad()}[dim]Token pruefen und erneut eingeben.[/dim]", highlight=False)
        return CommandResult(
            ok=False,
            style="silent",
            prompt="Token",
            pending_handler=_git_wizard_auth_token,
            wizard_step=(2, 3, "Token"),
        )

    _run("gh auth setup-git", timeout=5)

    # Extract account name
    auth_check = _run("gh auth status 2>&1", timeout=5)
    account = ""
    for line in auth_check.splitlines():
        if "account" in line.lower():
            parts = line.strip().split()
            for i, p in enumerate(parts):
                if p == "account" and i + 1 < len(parts):
                    account = parts[i + 1]
                    break
            break

    print_success(f"Eingeloggt als [bold]{account}[/bold]" if account else "Authentifizierung erfolgreich!")
    print_success("Git Credential Helper konfiguriert")

    # Step 3: SSH Key
    ssh_key_path = Path.home() / ".ssh" / "id_ed25519.pub"
    if ssh_key_path.exists():
        print_step(3, 3, "GitHub Setup")
        pad = _content_pad()
        print_info("SSH-Key gefunden. Zu GitHub hinzufuegen?")
        console.print()
        console.print(f"{pad}[bold]j[/bold] [dim]Ja, SSH-Key hinzufuegen[/dim]", highlight=False)
        console.print(f"{pad}[bold]n[/bold] [dim]Nein, nur HTTPS (reicht meistens)[/dim]", highlight=False)
        console.print()
        return CommandResult(
            ok=True,
            style="silent",
            prompt="SSH",
            pending_handler=_git_wizard_ssh_key,
            wizard_step=(3, 3, "SSH"),
        )

    print_success("HTTPS-Zugang konfiguriert")
    console.print()
    print_kv(_git_status_lines(), title="GitHub Status")
    return CommandResult(ok=True, style="silent", refresh=True)


def _git_wizard_ssh_key(state: TuiState, user_input: str) -> CommandResult:
    choice = user_input.strip().lower()
    if choice in ("j", "ja", "y", "yes"):
        hostname = socket.gethostname()

        def _do_add() -> str:
            return _run(
                f'gh ssh-key add ~/.ssh/id_ed25519.pub --title "arasul@{hostname}"',
                timeout=10,
            )

        result = spinner_run("SSH-Key wird hinzugefuegt...", _do_add)

        if "already" in result.lower() or not result:
            print_success("SSH-Key bereits auf GitHub registriert")
        else:
            print_success(f"SSH-Key hinzugefuegt: [dim]arasul@{hostname}[/dim]")

        ssh_test = _run("ssh -o StrictHostKeyChecking=no -T git@github.com 2>&1", timeout=8)
        if "successfully authenticated" in ssh_test.lower():
            print_success("SSH-Verbindung zu GitHub: OK")
        else:
            print_warning(f"SSH-Test: [dim]{ssh_test[:100]}[/dim]")

    elif choice in ("n", "nein", "no"):
        print_info("SSH uebersprungen. HTTPS-Zugang ist konfiguriert.")
    else:
        print_error("Bitte [bold]j[/bold] oder [bold]n[/bold] eingeben.")
        return CommandResult(
            ok=False,
            style="silent",
            prompt="SSH",
            pending_handler=_git_wizard_ssh_key,
            wizard_step=(3, 3, "SSH"),
        )

    console.print()
    print_success("[bold]GitHub Setup abgeschlossen![/bold]")
    console.print()
    print_kv(_git_status_lines(), title="GitHub Status")
    return CommandResult(ok=True, style="silent", refresh=True)


def cmd_git(state: TuiState, args: list[str]) -> CommandResult:
    gh_check = _run("gh auth status 2>&1", timeout=5)
    if "Logged in" in gh_check:
        print_kv(_git_status_lines(), title="GitHub Status")
        return CommandResult(ok=True, style="silent")

    return _git_wizard_start(state, "")


# ---------------------------------------------------------------------------
# /browser
# ---------------------------------------------------------------------------

def cmd_browser(state: TuiState, args: list[str]) -> CommandResult:
    sub = args[0] if args else "status"

    if sub == "status":
        lines = browser_health()
        return CommandResult(ok=True, lines=lines, style="panel")

    if sub == "test":
        ok, lines = browser_test()
        return CommandResult(ok=ok, lines=lines, style="panel")

    if sub == "install":
        ok, lines = install_browser()
        if ok and not is_mcp_configured():
            mcp_ok, mcp_msg = configure_mcp()
            lines.append(mcp_msg)
        return CommandResult(ok=ok, lines=lines, style="panel")

    if sub == "mcp":
        if is_mcp_configured():
            print_success("Playwright MCP bereits konfiguriert.")
            return CommandResult(ok=True, style="silent")
        ok, msg = configure_mcp()
        if ok:
            print_success(msg)
        else:
            print_error(msg)
        return CommandResult(ok=ok, style="silent")

    print_error(f"Unbekannter Subcommand: [bold]{sub}[/bold]")
    print_info("Verfuegbar: [bold]status[/bold], [bold]test[/bold], [bold]install[/bold], [bold]mcp[/bold]")
    return CommandResult(ok=False, style="silent")


# ---------------------------------------------------------------------------
# Claude OAuth Setup Wizard
# ---------------------------------------------------------------------------

def _wizard_step_token(state: TuiState, user_input: str) -> CommandResult:
    token = user_input.strip()
    if not token.startswith(TOKEN_PREFIX):
        print_error(f"Token muss mit [bold]{TOKEN_PREFIX}...[/bold] beginnen.")
        return CommandResult(
            ok=False,
            style="silent",
            prompt="Token",
            pending_handler=_wizard_step_token,
            wizard_step=(1, 2, "Token"),
        )
    state._wizard_token = token
    print_success("Token akzeptiert.")

    print_step(2, 2, "Claude Setup")

    pad = _content_pad()
    print_info("Account-Info (JSON oder UUID)")
    console.print(f"{pad}[dim]Fuehre auf dem Mac aus:[/dim]", highlight=False)
    console.print(f'{pad}[cyan]cat ~/.claude.json | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin).get(\'oauthAccount\',{{}})))"[/cyan]', highlight=False)
    console.print()
    console.print(f"{pad}[dim]Paste das JSON oder nur die UUID:[/dim]", highlight=False)
    console.print()

    return CommandResult(
        ok=True,
        style="silent",
        prompt="JSON/UUID",
        pending_handler=_wizard_step_account_info,
        wizard_step=(2, 2, "Account"),
    )


def _wizard_step_account_info(state: TuiState, user_input: str) -> CommandResult:
    raw = user_input.strip()

    if raw.startswith("{"):
        try:
            import json
            data = json.loads(raw)
            uuid_val = data.get("accountUuid", "")
            email_val = data.get("emailAddress", "")
            if not uuid_val or "@" in uuid_val:
                print_error("JSON enthaelt keine gueltige accountUuid.")
                return CommandResult(
                    ok=False, style="silent",
                    prompt="JSON/UUID", pending_handler=_wizard_step_account_info,
                    wizard_step=(2, 2, "Account"),
                )
            if not email_val or "@" not in email_val:
                print_error("JSON enthaelt keine gueltige emailAddress.")
                return CommandResult(
                    ok=False, style="silent",
                    prompt="JSON/UUID", pending_handler=_wizard_step_account_info,
                    wizard_step=(2, 2, "Account"),
                )
            save_claude_auth(state._wizard_token, uuid_val, email_val)
            print_success(f"Account: [bold]{email_val}[/bold]")
            print_success("Claude Code ist konfiguriert.")
            print_info("Starte jetzt [bold]/claude[/bold] erneut.")
            return CommandResult(ok=True, style="silent", refresh=True)
        except Exception:
            print_error("JSON ungueltig.")
            return CommandResult(
                ok=False, style="silent",
                prompt="JSON/UUID", pending_handler=_wizard_step_account_info,
                wizard_step=(2, 2, "Account"),
            )

    uuid = raw
    if "@" in uuid:
        print_error("Das ist eine Email, keine UUID!")
        print_info("UUID findest du auf dem Mac mit:")
        console.print(f'{_content_pad()}[cyan]cat ~/.claude.json | python3 -c "import json,sys; print(json.load(sys.stdin).get(\'oauthAccount\',{{}}).get(\'accountUuid\',\'NICHT GEFUNDEN\'))"[/cyan]', highlight=False)
        return CommandResult(
            ok=False, style="silent",
            prompt="UUID", pending_handler=_wizard_step_account_info,
            wizard_step=(2, 2, "Account"),
        )
    if len(uuid) < 8 or "-" not in uuid:
        print_error("Ungueltige UUID. Format: [dim]xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx[/dim]")
        return CommandResult(
            ok=False, style="silent",
            prompt="UUID", pending_handler=_wizard_step_account_info,
            wizard_step=(2, 2, "Account"),
        )
    state._wizard_uuid = uuid
    print_success("UUID akzeptiert.")
    console.print()
    print_info("Email-Adresse deines Claude/Anthropic Accounts:")
    return CommandResult(
        ok=True, style="silent",
        prompt="Email", pending_handler=_wizard_step_email,
        wizard_step=(2, 2, "Email"),
    )


def _wizard_step_email(state: TuiState, user_input: str) -> CommandResult:
    email = user_input.strip()
    if "@" not in email:
        print_error("Ungueltige Email.")
        return CommandResult(
            ok=False, style="silent",
            prompt="Email", pending_handler=_wizard_step_email,
            wizard_step=(2, 2, "Email"),
        )
    save_claude_auth(state._wizard_token, state._wizard_uuid, email)
    print_success("Claude Code ist konfiguriert.")
    print_info("Starte jetzt [bold]/claude[/bold] erneut.")
    return CommandResult(ok=True, style="silent", refresh=True)


def _auth_choice(state: TuiState, user_input: str) -> CommandResult:
    choice = user_input.strip()
    if choice == "1":
        print_step(1, 2, "Claude Setup")
        pad = _content_pad()
        print_info("OAuth Token von deinem Mac:")
        console.print(f"{pad}[dim]Fuehre aus:[/dim] [cyan]claude setup-token[/cyan]", highlight=False)
        console.print(f"{pad}[dim]Kopiere den Token (sk-ant-oat01-...) und paste ihn hier.[/dim]", highlight=False)
        console.print()
        return CommandResult(
            ok=True, style="silent",
            prompt="Token", pending_handler=_wizard_step_token,
            wizard_step=(1, 2, "Token"),
        )
    if choice == "2":
        ok, msg = ensure_browser()
        if not ok:
            print_error(msg)
            print_info("Installiere zuerst: [bold]/browser install[/bold]")
            return CommandResult(ok=False, style="silent")
        pad = _content_pad()
        print_info("SSH-Tunnel-Methode:")
        console.print()
        console.print(f"{pad}[bold]1.[/bold] [dim]Neues Terminal auf dem Mac oeffnen[/dim]", highlight=False)
        console.print(f"{pad}[bold]2.[/bold] [cyan]ssh -L 1455:localhost:1455 arasul@<jetson-ip>[/cyan]", highlight=False)
        console.print(f"{pad}[bold]3.[/bold] [dim]Dann hier:[/dim] [cyan]claude login[/cyan]", highlight=False)
        console.print()
        return CommandResult(ok=True, style="silent")
    if choice == "3":
        pad = _content_pad()
        print_info("SSH-Tunnel (manuell):")
        console.print()
        console.print(f"{pad}[bold]1.[/bold] [dim]Neues Terminal auf dem Mac oeffnen[/dim]", highlight=False)
        console.print(f"{pad}[bold]2.[/bold] [cyan]ssh -L 1455:localhost:1455 arasul@<jetson-ip>[/cyan]", highlight=False)
        console.print(f"{pad}[bold]3.[/bold] [dim]Auf dem Server:[/dim] [cyan]claude login[/cyan]", highlight=False)
        console.print()
        return CommandResult(ok=True, style="silent")
    print_error("Bitte [bold]1[/bold], [bold]2[/bold] oder [bold]3[/bold] eingeben.")
    return CommandResult(
        ok=False, style="silent",
        prompt="Methode", pending_handler=_auth_choice,
        wizard_step=(1, 1, "Methode"),
    )


def cmd_claude(state: TuiState, _: list[str]) -> CommandResult:
    if not is_claude_configured():
        browser_ok, _ = ensure_browser()
        pad = _content_pad()
        print_warning("Claude Code ist noch nicht konfiguriert.")
        console.print()
        console.print(f"{pad}[dim]Wie moechtest du dich anmelden?[/dim]", highlight=False)
        console.print()
        console.print(f"{pad}[bold]1[/bold]  Token eingeben [dim](setup-token auf Mac)[/dim]", highlight=False)
        console.print(f"{pad}[bold]2[/bold]  SSH-Tunnel [dim](Browser auf Mac)[/dim]", highlight=False)
        console.print(f"{pad}[bold]3[/bold]  SSH-Tunnel manuell [dim](Anleitung)[/dim]", highlight=False)
        console.print()
        return CommandResult(
            ok=True, style="silent",
            prompt="Methode", pending_handler=_auth_choice,
            wizard_step=(1, 1, "Methode"),
        )
    return _launch_inline(state, "claude")


def cmd_codex(state: TuiState, _: list[str]) -> CommandResult:
    return _launch_inline(state, "codex")


def cmd_exit(_: TuiState, __: list[str]) -> CommandResult:
    pad = _content_pad()
    console.print(f"{pad}[dim]Bis bald.[/dim]", highlight=False)
    return CommandResult(ok=True, quit_app=True, style="silent")


# ---------------------------------------------------------------------------
# /delete
# ---------------------------------------------------------------------------

def _delete_confirm(state: TuiState, user_input: str) -> CommandResult:
    """Step 2: confirm deletion with j/n."""
    import shutil

    choice = user_input.strip().lower()
    target: Path = state._delete_target

    if choice not in ("j", "ja", "y", "yes"):
        if choice in ("n", "nein", "no"):
            print_info("Abgebrochen.")
            return CommandResult(ok=True, style="silent")
        print_error("Bitte [bold]j[/bold] oder [bold]n[/bold] eingeben.")
        return CommandResult(
            ok=False,
            style="silent",
            prompt="Bestaetigung",
            pending_handler=_delete_confirm,
            wizard_step=(2, 2, "Bestaetigung"),
        )

    try:
        shutil.rmtree(target)
    except Exception as exc:
        print_error(f"Loeschen fehlgeschlagen: {exc}")
        return CommandResult(ok=False, style="silent")

    if state.active_project and state.active_project.resolve() == target.resolve():
        state.active_project = None

    print_success(f"Projekt [bold]{target.name}[/bold] geloescht.")
    return CommandResult(ok=True, style="silent", refresh=True)


def _delete_select(state: TuiState, user_input: str) -> CommandResult:
    """Step 1: select project by number."""
    num_str = user_input.strip()
    if not num_str.isdigit():
        print_error("Bitte eine Nummer eingeben.")
        return CommandResult(ok=False, style="silent")

    root = _project_root(state)
    if not root:
        print_error("Projekt-Root nicht verfuegbar.")
        return CommandResult(ok=False, style="silent")

    projects = _project_dirs(root)
    num = int(num_str)
    if num < 1 or num > len(projects):
        print_error(f"Ungueltige Nummer. Verfuegbar: 1-{len(projects)}")
        return CommandResult(ok=False, style="silent")

    target = projects[num - 1]
    state._delete_target = target
    print_warning(f"[bold]{target.name}[/bold] wirklich loeschen? [dim](j/n)[/dim]")
    return CommandResult(
        ok=True,
        style="silent",
        prompt="Bestaetigung",
        pending_handler=_delete_confirm,
        wizard_step=(2, 2, "Bestaetigung"),
    )


def cmd_delete(state: TuiState, args: list[str]) -> CommandResult:
    root = _project_root(state)
    if not root:
        print_error(f"Projekt-Root nicht verfuegbar: {state.project_root}")
        return CommandResult(ok=False, style="silent")

    projects = _project_dirs(root)
    if not projects:
        print_warning("Keine Projekte vorhanden.")
        return CommandResult(ok=False, style="silent")

    pad = _content_pad()
    console.print()
    for i, p in enumerate(projects, 1):
        console.print(f"{pad}[cyan]{i}[/cyan]  {p.name}", highlight=False)
    console.print()
    print_info("Nummer des Projekts eingeben:")
    return CommandResult(
        ok=True,
        style="silent",
        prompt="Nummer",
        pending_handler=_delete_select,
        wizard_step=(1, 2, "Auswahl"),
    )
