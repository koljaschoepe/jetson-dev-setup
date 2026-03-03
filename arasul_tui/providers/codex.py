from __future__ import annotations

from arasul_tui.providers.base import Provider


class CodexProvider(Provider):
    name = "openai"
    binary = "codex"

    def launch_command(self) -> str:
        return "codex"

