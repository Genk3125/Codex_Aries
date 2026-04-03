from __future__ import annotations

from .registry import get_command_spec
from .types import JsonObject, SlashCommandError, SlashCommandRequest, SlashMode


def parse_command_name(raw_command: str) -> str:
    command_text = raw_command.strip()
    if not command_text:
        raise SlashCommandError("VALIDATION_ERROR", "slash command is empty")
    if command_text.startswith("/"):
        command_text = command_text[1:]
    command_name = command_text.strip()
    if not command_name:
        raise SlashCommandError("VALIDATION_ERROR", "slash command name is empty")
    return command_name


def resolve_mode(apply: bool) -> SlashMode:
    return "apply" if apply else "preview"


def build_request(
    *,
    raw_command: str,
    mode: SlashMode,
    payload: JsonObject,
    options: JsonObject,
) -> SlashCommandRequest:
    command_name = parse_command_name(raw_command)
    return SlashCommandRequest(
        command_name=command_name,
        mode=mode,
        payload=payload,
        options=options,
        raw_command=raw_command,
    )


def route_request(request: SlashCommandRequest) -> JsonObject:
    spec = get_command_spec(request.command_name)
    return spec.route_handler(request)
