from __future__ import annotations

from arasul_tui.providers.base import Provider
from arasul_tui.providers.claude import ClaudeProvider
from arasul_tui.providers.codex import CodexProvider


class ProviderManager:
    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {
            "claude": ClaudeProvider(),
            "openai": CodexProvider(),
        }

    def names(self) -> list[str]:
        return sorted(self._providers.keys())

    def get(self, name: str) -> Provider | None:
        return self._providers.get(name.lower())

