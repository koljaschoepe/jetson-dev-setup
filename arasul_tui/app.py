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
from arasul_tui.core.state import DEFAULT_PROJECT_ROOT, TuiState
from arasul_tui.core.types import PendingHandler
from arasul_tui.core.ui import (
    build_prompt,
    print_header,
    print_info,
    print_project_menu,
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

        if not parts:
            return

        cmd = parts[0]
        if cmd == "open":
            names = REGISTRY._project_names()
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
        elif cmd == "browser":
            browser_subs = {
                "status": "Health check",
                "test": "Connection test",
                "install": "Install/update",
                "mcp": "Configure MCP",
            }
            pref = ""
            if len(parts) >= 2 and not has_trailing_space:
                pref = parts[1]
            for sub, desc in browser_subs.items():
                if sub.startswith(pref):
                    full = f"/browser {sub}"
                    yield Completion(
                        full,
                        start_position=-len(text),
                        display=HTML(f"<b>/browser</b> {sub}"),
                        display_meta=desc,
                    )


def _handle_number(state: TuiState, num: int) -> bool:
    """Select project by number. Returns True if handled."""
    projects = project_list()
    if 1 <= num <= len(projects):
        name = projects[num - 1]
        target = (DEFAULT_PROJECT_ROOT / name).resolve()
        if target.exists() and target.is_dir():
            state.active_project = target
            return True
    return False


def _handle_action_shortcut(state: TuiState, key: str) -> tuple[bool, str | None]:
    """Handle single-letter action shortcuts when a project is active."""
    if key == "c":
        return True, "claude"
    if key == "x":
        return True, "codex"
    return False, None


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

    print_header(state, full=True)
    state.first_run = False

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

        if pending_handler:
            result = pending_handler(state, command)
            pending_handler = None
            wizard_step = None
            print_result(result)

            if result.prompt and result.pending_handler:
                pending_handler = result.pending_handler
                wizard_step = result.wizard_step

            if result.refresh:
                if state.active_project:
                    print_project_menu(state)
                else:
                    print_header(state, full=True)

            if result.launch_command and result.launch_cwd:
                launch_request = (result.launch_command, result.launch_cwd)
            if result.quit_app:
                break
            continue

        if command.lower() == "n":
            result = run_command(state, "/create")
            print_result(result)
            if result.prompt and result.pending_handler:
                pending_handler = result.pending_handler
                wizard_step = result.wizard_step
            if result.refresh:
                print_header(state, full=True)
            continue

        if command.lower() == "d":
            result = run_command(state, "/delete")
            print_result(result)
            if result.prompt and result.pending_handler:
                pending_handler = result.pending_handler
                wizard_step = result.wizard_step
            if result.refresh:
                print_header(state, full=True)
            continue

        if command.isdigit():
            num = int(command)
            if _handle_number(state, num):
                print_project_menu(state)
                continue
            else:
                print_warning(f"No project with number [bold]{num}[/bold].")
                continue

        if command.lower() == "b":
            state.active_project = None
            print_header(state, full=True)
            continue

        if len(command) == 1 and command.lower() in ("c", "x") and state.active_project:
            handled, launch_cmd = _handle_action_shortcut(state, command.lower())
            if handled and launch_cmd:
                if not shutil.which(launch_cmd):
                    from arasul_tui.core.ui import print_error

                    print_error(f"[bold]{launch_cmd}[/bold] not found.")
                    continue

                if launch_cmd == "claude":
                    from arasul_tui.core.auth import is_claude_configured

                    if not is_claude_configured():
                        result = run_command(state, "/claude")
                        print_result(result)
                        if result.prompt and result.pending_handler:
                            pending_handler = result.pending_handler
                            wizard_step = result.wizard_step
                        continue

                print_info(f"Starting [bold]{launch_cmd}[/bold] in [dim]{state.active_project}[/dim] ...")
                launch_request = (launch_cmd, state.active_project)
                break

        result = run_command(state, command)
        print_result(result)

        if result.prompt and result.pending_handler:
            pending_handler = result.pending_handler
            wizard_step = result.wizard_step

        if result.refresh:
            if state.active_project:
                print_project_menu(state)
            else:
                print_header(state, full=True)

        if result.launch_command and result.launch_cwd:
            launch_request = (result.launch_command, result.launch_cwd)

        if result.quit_app:
            break

    if launch_request:
        cmd, cwd = launch_request
        os.environ.update(get_auth_env())
        os.chdir(str(cwd))
        os.execvp(cmd, [cmd])


if __name__ == "__main__":
    run()
