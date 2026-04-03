from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, TypeAlias

JsonValue: TypeAlias = Any
JsonObject: TypeAlias = dict[str, JsonValue]
SlashMode: TypeAlias = Literal["preview", "apply"]


class SlashCommandError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SlashCommandRequest:
    command_name: str
    mode: SlashMode
    payload: JsonObject
    options: JsonObject
    raw_command: str


RouteHandler: TypeAlias = Callable[[SlashCommandRequest], JsonObject]


@dataclass(frozen=True)
class SlashCommandSpec:
    name: str
    summary: str
    route_handler: RouteHandler
