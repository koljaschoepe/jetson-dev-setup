"""Shared helpers for reading/writing ~/.claude.json."""

from __future__ import annotations

import json

from arasul_tui.core.constants import CLAUDE_JSON


def load_claude_json() -> dict:
    """Load ~/.claude.json, returning empty dict on failure."""
    try:
        return json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_claude_json(data: dict) -> None:
    """Write ~/.claude.json with consistent formatting."""
    CLAUDE_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
