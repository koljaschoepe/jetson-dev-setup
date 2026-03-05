from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from arasul_tui.core.state import DEFAULT_PROJECT_ROOT, TuiState
from arasul_tui.core.types import CommandResult

Handler = Callable[[TuiState, list[str]], CommandResult]


@dataclass
class CommandSpec:
    name: str
    handler: Handler
    help_text: str
    category: str = ""
    subcommands: dict[str, str] | None = None


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, CommandSpec] = {}

    def register(self, spec: CommandSpec) -> None:
        self._commands[spec.name] = spec

    def get(self, name: str) -> CommandSpec | None:
        return self._commands.get(name)

    def names(self) -> list[str]:
        return sorted(self._commands.keys())

    def specs(self) -> list[CommandSpec]:
        return [self._commands[n] for n in self.names()]

    def categories(self) -> dict[str, list[CommandSpec]]:
        """Return specs grouped by category, preserving order."""
        cats: dict[str, list[CommandSpec]] = {}
        for spec in self.specs():
            cat = spec.category or "Other"
            cats.setdefault(cat, []).append(spec)
        return cats

    def complete(self, line: str) -> list[str]:
        """Return completion candidates for a slash command line."""
        text = line.lstrip()
        if not text.startswith("/"):
            return []
        body = text[1:]
        parts = body.split()
        has_trailing_space = body.endswith(" ")

        if len(parts) <= 1 and not has_trailing_space:
            prefix = parts[0] if parts else ""
            return [f"/{name}" for name in self.names() if name.startswith(prefix)]

        if not parts:
            return [f"/{name}" for name in self.names()]

        cmd = parts[0]
        args = parts[1:]

        if cmd == "open":
            names = self._project_names()
            pref = ""
            if len(args) >= 1 and not has_trailing_space:
                pref = args[0]
            return [f"/open {name}" for name in names if name.startswith(pref)]

        # Generic subcommand completion
        spec = self.get(cmd)
        if spec and spec.subcommands:
            pref = ""
            if len(args) >= 1 and not has_trailing_space:
                pref = args[0]
            return [f"/{cmd} {s}" for s in spec.subcommands if s.startswith(pref)]

        return []

    @staticmethod
    def _project_names() -> list[str]:
        root = DEFAULT_PROJECT_ROOT
        try:
            return sorted([p.name for p in root.iterdir() if p.is_dir()], key=str.lower)
        except Exception:
            return []
