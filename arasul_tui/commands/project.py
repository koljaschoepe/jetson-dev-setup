from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from arasul_tui.core.projects import (
    register_project,
    unregister_project,
)
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


def _project_root(state: TuiState) -> Path | None:
    root = state.project_root
    try:
        root.mkdir(parents=True, exist_ok=True)
        return root
    except OSError:
        return None


def _project_dirs(root: Path) -> list[Path]:
    try:
        return sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
    except OSError:
        return []


def _is_safe_name(name: str) -> bool:
    """Reject names that could escape the project root."""
    return bool(name and "/" not in name and "\\" not in name and not name.startswith(".") and ".." not in name)


def _validate_project_path(target: Path, root: Path) -> str | None:
    """Return error message if path is invalid, else None."""
    if not target.resolve().is_relative_to(root.resolve()):
        return "Path outside project root is not allowed."
    return None


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
            print_info("Type [bold]new[/bold] to create one, or [bold]clone[/bold] to grab a repo.")
            return CommandResult(ok=False, style="silent")
        print_info("Type a project name or number to open it.")
        return CommandResult(ok=False, style="silent")

    name = args[0]
    target = (root / name).resolve()
    path_err = _validate_project_path(target, root)
    if path_err:
        print_error(path_err)
        return CommandResult(ok=False, style="silent")
    if not target.exists() or not target.is_dir():
        print_error(f"Project not found: [bold]{name}[/bold]")
        return CommandResult(ok=False, style="silent")
    state.active_project = target
    return CommandResult(ok=True, style="silent", refresh=True)


# ---------------------------------------------------------------------------
# /create
# ---------------------------------------------------------------------------


def _create_finish(state: TuiState, user_input: str) -> CommandResult:
    name = user_input.strip().replace(" ", "-")
    if not _is_safe_name(name):
        print_error("Invalid project name.")
        return CommandResult(ok=False, style="silent")
    root = _project_root(state)
    if not root:
        print_error(f"Project root not writable: {state.project_root}")
        return CommandResult(ok=False, style="silent")
    target = (root / name).resolve()
    path_err = _validate_project_path(target, root)
    if path_err:
        print_error(path_err)
        return CommandResult(ok=False, style="silent")
    if target.exists():
        print_error(f"Project already exists: {target}")
        return CommandResult(ok=False, style="silent")
    target.mkdir(parents=True, exist_ok=False)
    register_project(name=name, path=target, provider_default="claude")

    # n8n project scaffolding
    from arasul_tui.core.n8n_project import is_n8n_project_name, scaffold_n8n_project

    if is_n8n_project_name(name):
        scaffold_n8n_project(target)
        print_success(f"n8n project created: [bold]{name}[/bold]")
        print_info("CLAUDE.md and guardrails configured.")
        print_info("Subdirs: [dim]workflows/[/dim], [dim]docs/[/dim]")
    else:
        print_success(f"Project created: [bold]{name}[/bold]")

    state.active_project = target
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

    _GIT_URL_RE = re.compile(r"^(https://[\w.\-]+/[\w.\-/]+|git@[\w.\-]+:[\w.\-/]+)$")
    if not _GIT_URL_RE.match(url):
        print_error("Invalid URL. Expected: [dim]https://github.com/user/repo[/dim]")
        return CommandResult(ok=False, style="silent")

    repo_name = url.rstrip("/").split("/")[-1].removesuffix(".git")
    if not _is_safe_name(repo_name):
        print_error("Could not derive a safe repo name from URL.")
        return CommandResult(ok=False, style="silent")

    root = _project_root(state)
    if not root:
        print_error(f"Project root not writable: {state.project_root}")
        return CommandResult(ok=False, style="silent")

    target = (root / repo_name).resolve()
    path_err = _validate_project_path(target, root)
    if path_err:
        print_error(path_err)
        return CommandResult(ok=False, style="silent")
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
    except (subprocess.TimeoutExpired, OSError) as exc:
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
    except OSError as exc:
        print_error(f"Deletion failed: {exc}")
        return CommandResult(ok=False, style="silent")

    if state.active_project and state.active_project.resolve() == target.resolve():
        state.active_project = None

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


# ---------------------------------------------------------------------------
# /info
# ---------------------------------------------------------------------------


def cmd_info(state: TuiState, args: list[str]) -> CommandResult:
    """Show detailed project info panel."""
    from arasul_tui.core.git_info import detect_language, get_disk_usage, get_git_info, get_readme_headline

    if args:
        root = state.project_root
        target = root / args[0]
        if not target.exists():
            print_error(f"Project not found: [bold]{args[0]}[/bold]")
            return CommandResult(ok=False, style="silent")
    elif state.active_project:
        target = state.active_project
    else:
        print_warning("No active project. Open one first, then try [bold]info[/bold].")
        return CommandResult(ok=False, style="silent")

    git = get_git_info(target)
    rows: list[tuple[str, str]] = [("Name", target.name)]

    if git:
        branch_str = git.branch or "detached"
        if git.is_dirty:
            branch_str += " [yellow]*[/yellow]"
        rows.append(("Branch", branch_str))
        rows.append(("Status", "[yellow]modified[/yellow]" if git.is_dirty else "[green]clean[/green]"))
        if git.short_hash:
            rows.append(("Commit", f"{git.short_hash} {git.commit_message}"))
        if git.commit_time:
            rows.append(("Time", git.commit_time))
        if git.remote_url:
            rows.append(("Remote", git.remote_url))

    headline = get_readme_headline(target)
    if headline:
        rows.append(("About", headline))
    lang = detect_language(target)
    if lang:
        rows.append(("Lang", lang))
    disk = get_disk_usage(target)
    if disk:
        rows.append(("Disk", disk))
    rows.append(("Path", str(target)))

    print_styled_panel(target.name, rows)
    return CommandResult(ok=True, style="silent")


# ---------------------------------------------------------------------------
# /repos
# ---------------------------------------------------------------------------


def cmd_repos(state: TuiState, _: list[str]) -> CommandResult:
    """Show all projects dashboard."""
    from arasul_tui.core.git_info import get_git_info

    root = state.project_root
    projects = _project_dirs(root)
    if not projects:
        print_warning("No projects found.")
        return CommandResult(ok=False, style="silent")

    rows: list[tuple[str, str]] = []
    for p in projects:
        git = get_git_info(p)
        if git:
            branch = git.branch or "?"
            status = "[yellow]*[/yellow]" if git.is_dirty else "[green]✓[/green]"
            info = f"{branch} {status}  {git.commit_time}"
        else:
            info = "[dim]local[/dim]"
        active = " [cyan]←[/cyan]" if state.active_project and state.active_project.name == p.name else ""
        rows.append((p.name + active, info))

    print_styled_panel("Projects", rows)
    return CommandResult(ok=True, style="silent")
