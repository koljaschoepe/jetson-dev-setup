from __future__ import annotations

import os
import shutil
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from arasul_tui.core.auth import get_auth_env
from arasul_tui.core.router import REGISTRY, run_command
from arasul_tui.core.state import DEFAULT_PROJECT_ROOT, Screen, TuiState
from arasul_tui.core.types import PendingHandler
from arasul_tui.core.ui import (
    build_prompt,
    console,
    content_pad,
    print_header,
    print_info,
    print_result,
    print_separator,
    print_warning,
    project_list,
)


class SlashCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if not text.startswith("/"):
            return

        body = text[1:]
        parts = body.split()
        has_trailing_space = body.endswith(" ")

        if len(parts) <= 1 and not has_trailing_space:
            prefix = parts[0] if parts else ""
            for spec in REGISTRY.specs():
                if spec.name.startswith(prefix):
                    cmd_text = f"/{spec.name}"
                    yield Completion(
                        cmd_text,
                        start_position=-len(text),
                        display=HTML(f"<b>/{spec.name}</b>"),
                        display_meta=spec.help_text,
                    )
            return

        cmd = parts[0]

        # Generic subcommand completion
        spec = REGISTRY.get(cmd)
        if spec and spec.subcommands:
            pref = ""
            if len(parts) >= 2 and not has_trailing_space:
                pref = parts[1]
            for sub, desc in spec.subcommands.items():
                if sub.startswith(pref):
                    full = f"/{cmd} {sub}"
                    yield Completion(
                        full,
                        start_position=-len(text),
                        display=HTML(f"<b>/{cmd}</b> {sub}"),
                        display_meta=desc,
                    )
            return

        # /open <name> completion
        if cmd == "open":
            names = project_list()
            pref = ""
            if len(parts) >= 2 and not has_trailing_space:
                pref = parts[1]
            for name in names:
                if name.startswith(pref):
                    full = f"/open {name}"
                    yield Completion(
                        full,
                        start_position=-len(text),
                        display=HTML(f"<b>/open</b> {name}"),
                        display_meta="Open project",
                    )


def _handle_number(state: TuiState, num: int) -> bool:
    """Select project by number. Returns True if handled."""
    projects = project_list()
    if 1 <= num <= len(projects):
        name = projects[num - 1]
        target = (DEFAULT_PROJECT_ROOT / name).resolve()
        if target.exists() and target.is_dir():
            state.active_project = target
            state.screen = Screen.PROJECT
            return True
    return False


def _fuzzy_match(query: str, projects: list[str]) -> list[str]:
    """Simple fuzzy matching: score projects by substring and prefix match."""
    q = query.lower()
    exact = [p for p in projects if p.lower() == q]
    if exact:
        return exact
    prefix = [p for p in projects if p.lower().startswith(q)]
    if prefix:
        return prefix
    # Substring match
    sub = [p for p in projects if q in p.lower()]
    if sub:
        return sub
    # Character-by-character fuzzy
    def _score(name: str) -> int:
        n = name.lower()
        idx = 0
        for ch in q:
            pos = n.find(ch, idx)
            if pos == -1:
                return -1
            idx = pos + 1
        return idx - len(q)

    scored = [(p, _score(p)) for p in projects]
    matches = [(p, s) for p, s in scored if s >= 0]
    matches.sort(key=lambda x: x[1])
    return [p for p, _ in matches]


def run() -> None:
    state = TuiState()
    pending_handler: PendingHandler | None = None
    wizard_step: tuple[int, int, str] | None = None
    launch_request: tuple[str, Path] | None = None
    history = InMemoryHistory()
    prompt_style = Style.from_dict(
        {
            "completion-menu": "bg:#1a1a1a",
            "completion-menu.completion": "bg:#1a1a1a #888888",
            "completion-menu.completion.current": "bg:#2d2d2d #ffffff bold",
            "completion-menu.meta.completion": "bg:#1a1a1a #555555",
            "completion-menu.meta.completion.current": "bg:#2d2d2d #888888",
            "scrollbar.background": "bg:#1a1a1a",
            "scrollbar.button": "bg:#1a1a1a",
        }
    )
    session: PromptSession[str] = PromptSession(
        history=history,
        completer=SlashCompleter(),
        complete_while_typing=True,
        style=prompt_style,
    )

    # Show dashboard only once at startup
    print_header(state, full=True)
    state.first_run = False

    def _handle_result(result):
        """Process a CommandResult: print output, chain wizards, handle navigation."""
        nonlocal pending_handler, wizard_step, launch_request

        print_result(result)

        if result.prompt and result.pending_handler:
            pending_handler = result.pending_handler
            wizard_step = result.wizard_step

        if result.refresh:
            # Chat-flow: show compact context indicator instead of full redraw
            print_header(state, full=False)

        if result.launch_command and result.launch_cwd:
            launch_request = (result.launch_command, result.launch_cwd)

    while True:
        try:
            print_separator()
            prompt_markup = build_prompt(state, wizard_step)
            if pending_handler:
                raw = session.prompt(HTML(prompt_markup), completer=None)
            else:
                raw = session.prompt(HTML(prompt_markup))
        except (EOFError, KeyboardInterrupt):
            break

        command = raw.strip()
        if not command:
            continue

        # --- Pending handler (wizard) ---
        if pending_handler:
            if command.lower() == "q":
                pending_handler = None
                wizard_step = None
                print_info("Cancelled.")
                continue

            result = pending_handler(state, command)
            pending_handler = None
            wizard_step = None
            _handle_result(result)
            if result.quit_app:
                break
            continue

        # --- Shortcut: n (create) ---
        if command.lower() == "n":
            result = run_command(state, "/create")
            _handle_result(result)
            continue

        # --- Shortcut: d (delete) ---
        if command.lower() == "d":
            result = run_command(state, "/delete")
            _handle_result(result)
            continue

        # --- Number selection (project) ---
        if command.isdigit():
            num = int(command)
            if _handle_number(state, num):
                from arasul_tui.core.ui import print_success

                print_success(f"Opened [bold]{state.active_project.name}[/bold]")
                print_header(state, full=False)
                continue
            else:
                print_warning(f"No project with number [bold]{num}[/bold].")
                continue

        # --- Shortcut: b (back to main) ---
        if command.lower() == "b":
            state.active_project = None
            state.screen = Screen.MAIN
            print_info("Back to main.")
            continue

        # --- Single-letter shortcuts (c/g) when project is active ---
        if len(command) == 1 and command.lower() in ("c", "g") and state.active_project:
            key = command.lower()

            if key == "g":
                if not shutil.which("lazygit"):
                    from arasul_tui.core.ui import print_error

                    print_error("[bold]lazygit[/bold] is not installed.")
                    continue
                print_info(f"Starting [bold]lazygit[/bold] in [dim]{state.active_project.name}[/dim] ...")
                launch_request = ("lazygit", state.active_project)
                break

            if key == "c":
                from arasul_tui.core.auth import is_claude_configured

                if not is_claude_configured():
                    result = run_command(state, "/claude")
                    _handle_result(result)
                    continue

                if not shutil.which("claude"):
                    from arasul_tui.core.ui import print_error

                    print_error("[bold]claude[/bold] is not installed.")
                    continue

                print_info(f"Starting [bold]Claude Code[/bold] in [dim]{state.active_project.name}[/dim] ...")
                launch_request = ("claude", state.active_project)
                break

        # --- Fuzzy project search (non-slash, non-shortcut text) ---
        if not command.startswith("/"):
            projects = project_list()
            matches = _fuzzy_match(command, projects)
            if len(matches) == 1:
                target = (DEFAULT_PROJECT_ROOT / matches[0]).resolve()
                if target.exists() and target.is_dir():
                    state.active_project = target
                    state.screen = Screen.PROJECT
                    from arasul_tui.core.ui import print_success

                    print_success(f"Opened [bold]{matches[0]}[/bold]")
                    print_header(state, full=False)
                    continue
            elif len(matches) > 1:
                from arasul_tui.core.ui import print_info as _pi

                _pi(f"[bold]{len(matches)}[/bold] matches for [dim]{command}[/dim]:")
                pad = content_pad()
                for i, m in enumerate(matches[:5], 1):
                    console.print(f"{pad}  [cyan]{i}[/cyan]  {m}", highlight=False)
                continue

            # Fall through to slash command handler
            result = run_command(state, command)
            _handle_result(result)
            if result.quit_app:
                break
            continue

        # --- Slash commands ---
        result = run_command(state, command)
        _handle_result(result)

        if result.quit_app:
            break

    if launch_request:
        cmd, cwd = launch_request
        os.environ.update(get_auth_env())
        os.chdir(str(cwd))
        os.execvp(cmd, [cmd])


if __name__ == "__main__":
    run()
