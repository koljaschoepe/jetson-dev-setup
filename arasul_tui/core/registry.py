from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from arasul_tui.core.state import TuiState
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
