from __future__ import annotations

from arasul_tui.core.registry import CommandRegistry, CommandSpec
from arasul_tui.core.state import TuiState
from arasul_tui.core.types import CommandResult


def _noop_handler(state: TuiState, args: list[str]) -> CommandResult:
    return CommandResult(ok=True)


def test_register_and_get():
    reg = CommandRegistry()
    spec = CommandSpec("test", _noop_handler, "A test command")
    reg.register(spec)
    assert reg.get("test") is spec
    assert reg.get("nonexistent") is None


def test_names_sorted():
    reg = CommandRegistry()
    reg.register(CommandSpec("zebra", _noop_handler, "Z"))
    reg.register(CommandSpec("alpha", _noop_handler, "A"))
    reg.register(CommandSpec("middle", _noop_handler, "M"))
    assert reg.names() == ["alpha", "middle", "zebra"]


def test_specs_order():
    reg = CommandRegistry()
    reg.register(CommandSpec("beta", _noop_handler, "B"))
    reg.register(CommandSpec("alpha", _noop_handler, "A"))
    specs = reg.specs()
    assert [s.name for s in specs] == ["alpha", "beta"]


def test_categories():
    reg = CommandRegistry()
    reg.register(CommandSpec("help", _noop_handler, "Help", category="Meta"))
    reg.register(CommandSpec("status", _noop_handler, "Status", category="System"))
    reg.register(CommandSpec("health", _noop_handler, "Health", category="System"))

    cats = reg.categories()
    assert "Meta" in cats
    assert "System" in cats
    assert len(cats["System"]) == 2


def test_category_field():
    spec = CommandSpec("test", _noop_handler, "Test", category="Custom")
    assert spec.category == "Custom"


def test_subcommands_field():
    spec = CommandSpec("git", _noop_handler, "Git", subcommands={"pull": "Pull", "push": "Push"})
    assert spec.subcommands == {"pull": "Pull", "push": "Push"}
