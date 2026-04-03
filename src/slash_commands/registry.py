from __future__ import annotations

from .commands.agent_team import route_agent_team
from .types import SlashCommandError, SlashCommandSpec

_REGISTRY: dict[str, SlashCommandSpec] = {
    "agent_team": SlashCommandSpec(
        name="agent_team",
        summary="Delegate /agent_team preview/apply to poc/agent_team_command.py",
        route_handler=route_agent_team,
    ),
}


def get_command_spec(name: str) -> SlashCommandSpec:
    spec = _REGISTRY.get(name)
    if spec is None:
        available = ", ".join(sorted(_REGISTRY))
        raise SlashCommandError("UNKNOWN_COMMAND", f"unknown slash command: {name} (available: {available})")
    return spec


def list_command_specs() -> list[SlashCommandSpec]:
    return [_REGISTRY[name] for name in sorted(_REGISTRY)]
