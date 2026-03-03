from __future__ import annotations

from arasul_tui.providers.base import Provider


class ClaudeProvider(Provider):
    name = "claude"
    binary = "claude"

    def launch_command(self) -> str:
        return "claude"

