from __future__ import annotations

import datetime as dt
import json
import shlex
import shutil
import socket
import subprocess
from pathlib import Path

import psutil

from arasul_tui.core.auth import TOKEN_PREFIX, is_claude_configured, save_claude_auth
from arasul_tui.core.browser import (
    browser_health,
    browser_test,
    configure_mcp,
    ensure_browser,
    install_browser,
    is_mcp_configured,
)
from arasul_tui.core.projects import register_project, unregister_project
from arasul_tui.core.shell import run_cmd
from arasul_tui.core.state import TuiState
from arasul_tui.core.types import CommandResult
from arasul_tui.core.ui import (
    console,
    content_pad,
    get_default_interface,
    print_error,
    print_info,
    print_kv,
    print_step,
    print_success,
    print_warning,
    spinner_run,
)


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
    pad = content_pad()
    console.print()
    console.print(f"{pad}[bold]Shortcuts[/bold]", highlight=False)
    console.print(f"{pad}[cyan]1-9[/cyan]  [dim]Select project by number[/dim]", highlight=False)
    console.print(f"{pad}[cyan]n[/cyan]    [dim]Create new project[/dim]", highlight=False)
    console.print(f"{pad}[cyan]d[/cyan]    [dim]Delete project[/dim]", highlight=False)
    console.print(f"{pad}[cyan]c[/cyan]    [dim]Start Claude Code[/dim]", highlight=False)
    console.print(f"{pad}[cyan]x[/cyan]    [dim]Start Codex[/dim]", highlight=False)
    console.print(f"{pad}[cyan]b[/cyan]    [dim]Back to overview[/dim]", highlight=False)
    console.print()
    console.print(f"{pad}[bold]Projects[/bold]", highlight=False)
    console.print(f"{pad}[cyan]/open <name>[/cyan]    [dim]Open project[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/create[/cyan]         [dim]Create new project[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/clone[/cyan]          [dim]Clone GitHub repo[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/delete[/cyan]         [dim]Delete project[/dim]", highlight=False)
    console.print()
    console.print(f"{pad}[bold]AI Coding[/bold]", highlight=False)
    console.print(f"{pad}[cyan]/claude[/cyan]         [dim]Start Claude Code[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/codex[/cyan]          [dim]Start Codex[/dim]", highlight=False)
    console.print()
    console.print(f"{pad}[bold]System[/bold]", highlight=False)
    console.print(f"{pad}[cyan]/status[/cyan]         [dim]System status[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/git[/cyan]            [dim]GitHub setup[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/browser[/cyan]        [dim]Headless browser[/dim]", highlight=False)
    console.print()
    console.print(f"{pad}[cyan]/help[/cyan]           [dim]This help[/dim]", highlight=False)
    console.print(f"{pad}[cyan]/exit[/cyan]           [dim]Quit[/dim]", highlight=False)
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

    iface = get_default_interface()
    ip = run_cmd(f"ip -4 addr show {shlex.quote(iface)} | awk '/inet/{{print $2}}' | cut -d/ -f1")
    if not ip or ip.startswith("Error"):
        ip = run_cmd("hostname -I | awk '{print $1}'") or "n/a"
    power = run_cmd("sudo nvpmodel -q | head -1 | sed 's/NV Power Mode: //'") or "n/a"
    temp = run_cmd("cat /sys/devices/virtual/thermal/thermal_zone0/temp | awk '{printf \"%.0f\", $1/1000}'")
    temp_str = f"{temp}°C" if temp and temp.isdigit() else "n/a"
    docker = run_cmd("docker ps -q 2>/dev/null | wc -l | tr -d ' '") or "0"
    root = state.project_root
    project_count = len(_project_dirs(root)) if root.exists() else 0
    project_name = state.active_project.name if state.active_project else "[dim]-[/dim]"

    print_kv(
        [
            ("Host", socket.gethostname()),
            ("Uptime", uptime),
            ("RAM", f"{vm.used // (1024 * 1024)}M / {vm.total // (1024 * 1024)}M ({vm.percent:.0f}%)"),
            ("NVMe", f"{disk.used // (1024**3)}G / {disk.total // (1024**3)}G ({disk.percent:.0f}%)"),
            ("Temp", temp_str),
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
# /create
# ---------------------------------------------------------------------------


def _create_finish(state: TuiState, user_input: str) -> CommandResult:
    name = user_input.strip().replace(" ", "-")
    if not name:
        print_error("Project name must not be empty.")
        return CommandResult(ok=False, style="silent")
    root = _project_root(state)
    if not root:
        print_error(f"Project root not writable: {state.project_root}")
        return CommandResult(ok=False, style="silent")
    target = root / name
    if target.exists():
        print_error(f"Project already exists: {target}")
        return CommandResult(ok=False, style="silent")
    target.mkdir(parents=True, exist_ok=False)
    register_project(name=name, path=target, provider_default="claude")
    state.active_project = target
    print_success(f"Project created: [bold]{name}[/bold]")
    print_info(f"Path: [dim]{target}[/dim]")
    return CommandResult(ok=True, style="silent", refresh=True)


def cmd_create(state: TuiState, args: list[str]) -> CommandResult:
    if args:
        return _create_finish(state, args[0])
    print_info("What should the new project be called?")
    return CommandResult(
        ok=True,
        style="silent",
        prompt="Name",
        pending_handler=_create_finish,
        wizard_step=(1, 1, "Project"),
    )


# ---------------------------------------------------------------------------
# /clone
# ---------------------------------------------------------------------------


def _clone_finish(state: TuiState, user_input: str) -> CommandResult:
    url = user_input.strip()
    if not url:
        print_error("URL must not be empty.")
        return CommandResult(ok=False, style="silent")

    if not (url.startswith("https://") or url.startswith("git@")):
        print_error("Invalid URL. Expected: [dim]https://github.com/user/repo[/dim]")
        return CommandResult(ok=False, style="silent")

    repo_name = url.rstrip("/").split("/")[-1].removesuffix(".git")
    if not repo_name:
        print_error("Could not derive repo name from URL.")
        return CommandResult(ok=False, style="silent")

    root = _project_root(state)
    if not root:
        print_error(f"Project root not writable: {state.project_root}")
        return CommandResult(ok=False, style="silent")

    target = root / repo_name
    if target.exists():
        print_error(f"Directory already exists: [bold]{repo_name}[/bold]")
        return CommandResult(ok=False, style="silent")

    def _do_clone() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "clone", url, str(target)],
            capture_output=True,
            text=True,
            timeout=120,
        )

    try:
        result = spinner_run(f"Cloning [bold]{repo_name}[/bold] ...", _do_clone)
    except Exception as exc:
        print_error(f"Clone failed: {exc}")
        return CommandResult(ok=False, style="silent")

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        print_error(f"git clone failed: {err}")
        return CommandResult(ok=False, style="silent")

    register_project(name=repo_name, path=target, provider_default="claude")
    state.active_project = target
    print_success(f"Repo cloned: [bold]{repo_name}[/bold]")
    print_info(f"Path: [dim]{target}[/dim]")
    return CommandResult(ok=True, style="silent", refresh=True)


def cmd_clone(state: TuiState, args: list[str]) -> CommandResult:
    if args:
        return _clone_finish(state, args[0])
    print_info("Enter GitHub URL (e.g. [dim]https://github.com/user/repo[/dim])")
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
        print_error(f"Project root not found: {root}")
        return CommandResult(ok=False, style="silent")
    if not args:
        names = [p.name for p in _project_dirs(root)]
        if not names:
            print_warning("No projects found.")
            print_info("Create one with [bold]n[/bold] or [bold]/create[/bold]")
            return CommandResult(ok=False, style="silent")
        print_info("Usage: [bold]/open <name>[/bold] or select by number")
        return CommandResult(ok=False, style="silent")

    name = args[0]
    target = (root / name).resolve()
    if not target.exists() or not target.is_dir():
        print_error(f"Project not found: [bold]{name}[/bold]")
        return CommandResult(ok=False, style="silent")
    state.active_project = target
    return CommandResult(ok=True, style="silent", refresh=True)


# ---------------------------------------------------------------------------
# /claude, /codex
# ---------------------------------------------------------------------------


def _launch_inline(state: TuiState, command: str) -> CommandResult:
    if not state.active_project:
        print_warning("No active project.")
        print_info("Set one with [bold]/open <name>[/bold]")
        return CommandResult(ok=False, style="silent")
    if not shutil.which(command):
        print_error(f"Binary not found: [bold]{command}[/bold]")
        return CommandResult(ok=False, style="silent")
    print_info(f"Starting [bold]{command}[/bold] in [dim]{state.active_project}[/dim] ...")
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

    gh = run_cmd("command -v gh && gh --version | head -1", timeout=3)
    if "gh version" in gh:
        ver = gh.splitlines()[-1].strip()
        rows.append(("gh CLI", f"[green]✓[/green] {ver}"))
    else:
        rows.append(("gh CLI", "[red]✗[/red] not installed"))

    auth = run_cmd("gh auth status 2>&1", timeout=5)
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
        rows.append(("Auth", f"[green]✓[/green] {account}" if account else "[green]✓[/green] logged in"))
    else:
        rows.append(("Auth", "[red]✗[/red] not logged in"))

    name = run_cmd("git config --global user.name")
    email = run_cmd("git config --global user.email")
    rows.append(("Git Name", name or "[dim]not set[/dim]"))
    rows.append(("Git Email", email or "[dim]not set[/dim]"))

    ssh_key = Path.home() / ".ssh" / "id_ed25519.pub"
    if ssh_key.exists():
        rows.append(("SSH Key", f"[green]✓[/green] [dim]{ssh_key}[/dim]"))
    else:
        rows.append(("SSH Key", "[dim]not found[/dim]"))

    ssh_test = run_cmd("ssh -o StrictHostKeyChecking=accept-new -T git@github.com 2>&1", timeout=5)
    if "successfully authenticated" in ssh_test.lower():
        user = ""
        for part in ssh_test.split():
            if part.endswith("!"):
                user = part.rstrip("!")
                break
        rows.append(("GitHub SSH", f"[green]✓[/green] {user}" if user else "[green]✓[/green]"))
    else:
        rows.append(("GitHub SSH", "[dim]not connected[/dim]"))

    cred = run_cmd("git config --global credential.helper")
    if cred:
        rows.append(("Credentials", f"[green]✓[/green] {cred}"))

    return rows


def _git_install_gh() -> tuple[bool, str]:
    check = run_cmd("command -v gh", timeout=2)
    if check and "gh" in check:
        ver = run_cmd("gh --version | head -1", timeout=3)
        return True, ver or "installed"

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
        return run_cmd(install_cmd, timeout=120)

    spinner_run("Installing gh CLI...", _do_install)

    check2 = run_cmd("command -v gh", timeout=2)
    if check2 and "gh" in check2:
        ver = run_cmd("gh --version | head -1", timeout=3)
        return True, ver or "installed"
    return False, "Installation failed"


def _git_setup_known_hosts() -> None:
    known_hosts = Path.home() / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = known_hosts.read_text(encoding="utf-8") if known_hosts.exists() else ""
    except OSError:
        existing = ""
    if "github.com" not in existing:
        run_cmd("ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null", timeout=10)


def _git_wizard_start(state: TuiState, user_input: str) -> CommandResult:
    print_step(1, 3, "GitHub Setup")

    ok, ver_or_err = _git_install_gh()
    if not ok:
        print_error(ver_or_err)
        return CommandResult(ok=False, style="silent")

    print_success(f"gh CLI [dim]{ver_or_err}[/dim]")

    _git_setup_known_hosts()

    auth_check = run_cmd("gh auth status 2>&1", timeout=5)
    if "Logged in" in auth_check:
        print_success("Already authenticated!")
        run_cmd("gh auth setup-git", timeout=5)
        print_success("Git credential helper configured")
        console.print()
        print_kv(_git_status_lines(), title="GitHub Status")
        return CommandResult(ok=True, style="silent", refresh=True)

    print_step(2, 3, "GitHub Setup")

    pad = content_pad()
    print_info("Create a Personal Access Token (classic):")
    console.print()
    console.print(f"{pad}[cyan bold]https://github.com/settings/tokens/new[/cyan bold]", highlight=False)
    console.print()
    console.print(
        f"{pad}[dim]Scopes:[/dim] [bold]repo[/bold], [bold]read:org[/bold], [bold]workflow[/bold]", highlight=False
    )
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
        print_error("Token must not be empty.")
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

    result = spinner_run("Authenticating...", _do_auth)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()[:150]
        print_error(f"Failed: [dim]{err}[/dim]")
        console.print(f"{content_pad()}[dim]Check your token and try again.[/dim]", highlight=False)
        return CommandResult(
            ok=False,
            style="silent",
            prompt="Token",
            pending_handler=_git_wizard_auth_token,
            wizard_step=(2, 3, "Token"),
        )

    run_cmd("gh auth setup-git", timeout=5)

    auth_check = run_cmd("gh auth status 2>&1", timeout=5)
    account = ""
    for line in auth_check.splitlines():
        if "account" in line.lower():
            parts = line.strip().split()
            for i, p in enumerate(parts):
                if p == "account" and i + 1 < len(parts):
                    account = parts[i + 1]
                    break
            break

    print_success(f"Logged in as [bold]{account}[/bold]" if account else "Authentication successful!")
    print_success("Git credential helper configured")

    ssh_key_path = Path.home() / ".ssh" / "id_ed25519.pub"
    if ssh_key_path.exists():
        print_step(3, 3, "GitHub Setup")
        pad = content_pad()
        print_info("SSH key found. Add it to GitHub?")
        console.print()
        console.print(f"{pad}[bold]y[/bold] [dim]Yes, add SSH key[/dim]", highlight=False)
        console.print(f"{pad}[bold]n[/bold] [dim]No, HTTPS only (usually sufficient)[/dim]", highlight=False)
        console.print()
        return CommandResult(
            ok=True,
            style="silent",
            prompt="SSH",
            pending_handler=_git_wizard_ssh_key,
            wizard_step=(3, 3, "SSH"),
        )

    print_success("HTTPS access configured")
    console.print()
    print_kv(_git_status_lines(), title="GitHub Status")
    return CommandResult(ok=True, style="silent", refresh=True)


def _git_wizard_ssh_key(state: TuiState, user_input: str) -> CommandResult:
    choice = user_input.strip().lower()
    if choice in ("y", "yes", "j", "ja"):
        hostname = socket.gethostname()

        def _do_add() -> str:
            return run_cmd(
                f'gh ssh-key add ~/.ssh/id_ed25519.pub --title "arasul@{hostname}"',
                timeout=10,
            )

        result = spinner_run("Adding SSH key...", _do_add)

        if "already" in result.lower() or not result:
            print_success("SSH key already registered on GitHub")
        else:
            print_success(f"SSH key added: [dim]arasul@{hostname}[/dim]")

        ssh_test = run_cmd("ssh -o StrictHostKeyChecking=accept-new -T git@github.com 2>&1", timeout=8)
        if "successfully authenticated" in ssh_test.lower():
            print_success("SSH connection to GitHub: OK")
        else:
            print_warning(f"SSH test: [dim]{ssh_test[:100]}[/dim]")

    elif choice in ("n", "no", "nein"):
        print_info("SSH skipped. HTTPS access is configured.")
    else:
        print_error("Please enter [bold]y[/bold] or [bold]n[/bold].")
        return CommandResult(
            ok=False,
            style="silent",
            prompt="SSH",
            pending_handler=_git_wizard_ssh_key,
            wizard_step=(3, 3, "SSH"),
        )

    console.print()
    print_success("[bold]GitHub setup complete![/bold]")
    console.print()
    print_kv(_git_status_lines(), title="GitHub Status")
    return CommandResult(ok=True, style="silent", refresh=True)


def cmd_git(state: TuiState, args: list[str]) -> CommandResult:
    gh_check = run_cmd("gh auth status 2>&1", timeout=5)
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


# ---------------------------------------------------------------------------
# Claude OAuth Setup Wizard
# ---------------------------------------------------------------------------


def _wizard_step_token(state: TuiState, user_input: str) -> CommandResult:
    token = user_input.strip()
    if not token.startswith(TOKEN_PREFIX):
        print_error(f"Token must start with [bold]{TOKEN_PREFIX}...[/bold].")
        return CommandResult(
            ok=False,
            style="silent",
            prompt="Token",
            pending_handler=_wizard_step_token,
            wizard_step=(1, 2, "Token"),
        )
    state._wizard_token = token
    print_success("Token accepted.")

    print_step(2, 2, "Claude Setup")

    pad = content_pad()
    print_info("Account info (JSON or UUID)")
    console.print(f"{pad}[dim]Run on your Mac:[/dim]", highlight=False)
    console.print(
        f"{pad}[cyan]cat ~/.claude.json | python3 -c \"import json,sys; print(json.dumps(json.load(sys.stdin).get('oauthAccount',{{}})))\"[/cyan]",
        highlight=False,
    )
    console.print()
    console.print(f"{pad}[dim]Paste the JSON or just the UUID:[/dim]", highlight=False)
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
            data = json.loads(raw)
            uuid_val = data.get("accountUuid", "")
            email_val = data.get("emailAddress", "")
            if not uuid_val or "@" in uuid_val:
                print_error("JSON does not contain a valid accountUuid.")
                return CommandResult(
                    ok=False,
                    style="silent",
                    prompt="JSON/UUID",
                    pending_handler=_wizard_step_account_info,
                    wizard_step=(2, 2, "Account"),
                )
            if not email_val or "@" not in email_val:
                print_error("JSON does not contain a valid emailAddress.")
                return CommandResult(
                    ok=False,
                    style="silent",
                    prompt="JSON/UUID",
                    pending_handler=_wizard_step_account_info,
                    wizard_step=(2, 2, "Account"),
                )
            save_claude_auth(state._wizard_token, uuid_val, email_val)
            print_success(f"Account: [bold]{email_val}[/bold]")
            print_success("Claude Code is configured.")
            print_info("Now run [bold]/claude[/bold] again.")
            return CommandResult(ok=True, style="silent", refresh=True)
        except Exception:
            print_error("Invalid JSON.")
            return CommandResult(
                ok=False,
                style="silent",
                prompt="JSON/UUID",
                pending_handler=_wizard_step_account_info,
                wizard_step=(2, 2, "Account"),
            )

    uuid = raw
    if "@" in uuid:
        print_error("That's an email, not a UUID!")
        print_info("Find the UUID on your Mac with:")
        console.print(
            f"{content_pad()}[cyan]cat ~/.claude.json | python3 -c \"import json,sys; print(json.load(sys.stdin).get('oauthAccount',{{}}).get('accountUuid','NOT FOUND'))\"[/cyan]",
            highlight=False,
        )
        return CommandResult(
            ok=False,
            style="silent",
            prompt="UUID",
            pending_handler=_wizard_step_account_info,
            wizard_step=(2, 2, "Account"),
        )
    if len(uuid) < 8 or "-" not in uuid:
        print_error("Invalid UUID. Format: [dim]xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx[/dim]")
        return CommandResult(
            ok=False,
            style="silent",
            prompt="UUID",
            pending_handler=_wizard_step_account_info,
            wizard_step=(2, 2, "Account"),
        )
    state._wizard_uuid = uuid
    print_success("UUID accepted.")
    console.print()
    print_info("Email address of your Claude/Anthropic account:")
    return CommandResult(
        ok=True,
        style="silent",
        prompt="Email",
        pending_handler=_wizard_step_email,
        wizard_step=(2, 2, "Email"),
    )


def _wizard_step_email(state: TuiState, user_input: str) -> CommandResult:
    email = user_input.strip()
    if "@" not in email:
        print_error("Invalid email.")
        return CommandResult(
            ok=False,
            style="silent",
            prompt="Email",
            pending_handler=_wizard_step_email,
            wizard_step=(2, 2, "Email"),
        )
    save_claude_auth(state._wizard_token, state._wizard_uuid, email)
    print_success("Claude Code is configured.")
    print_info("Now run [bold]/claude[/bold] again.")
    return CommandResult(ok=True, style="silent", refresh=True)


def _auth_choice(state: TuiState, user_input: str) -> CommandResult:
    choice = user_input.strip()
    if choice == "1":
        print_step(1, 2, "Claude Setup")
        pad = content_pad()
        print_info("OAuth token from your Mac:")
        console.print(f"{pad}[dim]Run:[/dim] [cyan]claude setup-token[/cyan]", highlight=False)
        console.print(f"{pad}[dim]Copy the token (sk-ant-oat01-...) and paste it here.[/dim]", highlight=False)
        console.print()
        return CommandResult(
            ok=True,
            style="silent",
            prompt="Token",
            pending_handler=_wizard_step_token,
            wizard_step=(1, 2, "Token"),
        )
    if choice == "2":
        ok, msg = ensure_browser()
        if not ok:
            print_error(msg)
            print_info("Install first: [bold]/browser install[/bold]")
            return CommandResult(ok=False, style="silent")
        pad = content_pad()
        print_info("SSH tunnel method:")
        console.print()
        console.print(f"{pad}[bold]1.[/bold] [dim]Open a new terminal on your Mac[/dim]", highlight=False)
        console.print(f"{pad}[bold]2.[/bold] [cyan]ssh -L 1455:localhost:1455 user@<jetson-ip>[/cyan]", highlight=False)
        console.print(f"{pad}[bold]3.[/bold] [dim]Then here:[/dim] [cyan]claude login[/cyan]", highlight=False)
        console.print()
        return CommandResult(ok=True, style="silent")
    if choice == "3":
        pad = content_pad()
        print_info("SSH tunnel (manual):")
        console.print()
        console.print(f"{pad}[bold]1.[/bold] [dim]Open a new terminal on your Mac[/dim]", highlight=False)
        console.print(f"{pad}[bold]2.[/bold] [cyan]ssh -L 1455:localhost:1455 user@<jetson-ip>[/cyan]", highlight=False)
        console.print(f"{pad}[bold]3.[/bold] [dim]On the server:[/dim] [cyan]claude login[/cyan]", highlight=False)
        console.print()
        return CommandResult(ok=True, style="silent")
    print_error("Please enter [bold]1[/bold], [bold]2[/bold], or [bold]3[/bold].")
    return CommandResult(
        ok=False,
        style="silent",
        prompt="Method",
        pending_handler=_auth_choice,
        wizard_step=(1, 1, "Method"),
    )


def cmd_claude(state: TuiState, _: list[str]) -> CommandResult:
    if not is_claude_configured():
        browser_ok, _ = ensure_browser()
        pad = content_pad()
        print_warning("Claude Code is not configured yet.")
        console.print()
        console.print(f"{pad}[dim]How would you like to log in?[/dim]", highlight=False)
        console.print()
        console.print(f"{pad}[bold]1[/bold]  Enter token [dim](setup-token on Mac)[/dim]", highlight=False)
        console.print(f"{pad}[bold]2[/bold]  SSH tunnel [dim](browser on Mac)[/dim]", highlight=False)
        console.print(f"{pad}[bold]3[/bold]  SSH tunnel manual [dim](instructions)[/dim]", highlight=False)
        console.print()
        return CommandResult(
            ok=True,
            style="silent",
            prompt="Method",
            pending_handler=_auth_choice,
            wizard_step=(1, 1, "Method"),
        )
    return _launch_inline(state, "claude")


def cmd_codex(state: TuiState, _: list[str]) -> CommandResult:
    return _launch_inline(state, "codex")


def cmd_exit(_: TuiState, __: list[str]) -> CommandResult:
    pad = content_pad()
    console.print(f"{pad}[dim]Goodbye.[/dim]", highlight=False)
    return CommandResult(ok=True, quit_app=True, style="silent")


# ---------------------------------------------------------------------------
# /delete
# ---------------------------------------------------------------------------


def _delete_confirm(state: TuiState, user_input: str) -> CommandResult:
    """Step 2: confirm deletion with y/n."""
    choice = user_input.strip().lower()
    target: Path = state._delete_target

    if choice not in ("y", "yes", "j", "ja"):
        if choice in ("n", "no", "nein"):
            print_info("Cancelled.")
            return CommandResult(ok=True, style="silent")
        print_error("Please enter [bold]y[/bold] or [bold]n[/bold].")
        return CommandResult(
            ok=False,
            style="silent",
            prompt="Confirm",
            pending_handler=_delete_confirm,
            wizard_step=(2, 2, "Confirm"),
        )

    try:
        shutil.rmtree(target)
    except Exception as exc:
        print_error(f"Deletion failed: {exc}")
        return CommandResult(ok=False, style="silent")

    if state.active_project and state.active_project.resolve() == target.resolve():
        state.active_project = None

    # Remove from project registry
    unregister_project(target.name)

    print_success(f"Project [bold]{target.name}[/bold] deleted.")
    return CommandResult(ok=True, style="silent", refresh=True)


def _delete_select(state: TuiState, user_input: str) -> CommandResult:
    """Step 1: select project by number."""
    num_str = user_input.strip()
    if not num_str.isdigit():
        print_error("Please enter a number.")
        return CommandResult(ok=False, style="silent")

    root = _project_root(state)
    if not root:
        print_error("Project root not available.")
        return CommandResult(ok=False, style="silent")

    projects = _project_dirs(root)
    num = int(num_str)
    if num < 1 or num > len(projects):
        print_error(f"Invalid number. Available: 1-{len(projects)}")
        return CommandResult(ok=False, style="silent")

    target = projects[num - 1]
    state._delete_target = target
    print_warning(f"Really delete [bold]{target.name}[/bold]? [dim](y/n)[/dim]")
    return CommandResult(
        ok=True,
        style="silent",
        prompt="Confirm",
        pending_handler=_delete_confirm,
        wizard_step=(2, 2, "Confirm"),
    )


def cmd_delete(state: TuiState, args: list[str]) -> CommandResult:
    root = _project_root(state)
    if not root:
        print_error(f"Project root not available: {state.project_root}")
        return CommandResult(ok=False, style="silent")

    projects = _project_dirs(root)
    if not projects:
        print_warning("No projects found.")
        return CommandResult(ok=False, style="silent")

    pad = content_pad()
    console.print()
    for i, p in enumerate(projects, 1):
        console.print(f"{pad}[cyan]{i}[/cyan]  {p.name}", highlight=False)
    console.print()
    print_info("Enter project number:")
    return CommandResult(
        ok=True,
        style="silent",
        prompt="Number",
        pending_handler=_delete_select,
        wizard_step=(1, 2, "Select"),
    )
