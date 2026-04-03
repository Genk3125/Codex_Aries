from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..types import JsonObject, SlashCommandError, SlashCommandRequest

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT_TEAM_COMMAND = REPO_ROOT / "poc" / "agent_team_command.py"


def _as_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SlashCommandError("VALIDATION_ERROR", f"{label} must be a non-empty string")
    return value.strip()


def _ensure_payload_shape(payload: JsonObject) -> None:
    _as_non_empty_string(payload.get("team_name"), "payload.team_name")
    if not isinstance(payload.get("main_agent"), dict):
        raise SlashCommandError("VALIDATION_ERROR", "payload.main_agent must be an object")
    if "sub_agents" in payload and payload.get("sub_agents") is not None and not isinstance(payload.get("sub_agents"), list):
        raise SlashCommandError("VALIDATION_ERROR", "payload.sub_agents must be an array when provided")


def _option_string(options: JsonObject, key: str) -> str:
    value = options.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SlashCommandError("VALIDATION_ERROR", f"slash option {key} must be a string")
    return value.strip()


def _option_bool(options: JsonObject, key: str) -> bool:
    value = options.get(key, False)
    if isinstance(value, bool):
        return value
    raise SlashCommandError("VALIDATION_ERROR", f"slash option {key} must be boolean")


def _build_delegate_command(request: SlashCommandRequest) -> list[str]:
    if not AGENT_TEAM_COMMAND.exists():
        raise SlashCommandError("DELEGATE_NOT_FOUND", f"agent_team_command.py not found: {AGENT_TEAM_COMMAND}")

    delegate_mode = "plan" if request.mode == "preview" else "apply"
    command = [sys.executable, str(AGENT_TEAM_COMMAND), delegate_mode]
    command.extend(["--input-json", json.dumps(request.payload, ensure_ascii=False)])

    presets_file = _option_string(request.options, "presets_file")
    if presets_file:
        command.extend(["--presets-file", presets_file])

    if request.mode == "apply":
        runtime_cmd = _option_string(request.options, "runtime_cmd")
        if runtime_cmd:
            command.extend(["--runtime-cmd", runtime_cmd])

        store_root = _option_string(request.options, "store_root")
        if store_root:
            command.extend(["--store-root", store_root])

        idempotency_prefix = _option_string(request.options, "idempotency_prefix")
        if idempotency_prefix:
            command.extend(["--idempotency-prefix", idempotency_prefix])

        if _option_bool(request.options, "strict"):
            command.append("--strict")
        if _option_bool(request.options, "force_task_create"):
            command.append("--force-task-create")
        if _option_bool(request.options, "skip_task_create"):
            command.append("--skip-task-create")
        if _option_bool(request.options, "force_send_messages"):
            command.append("--force-send-messages")
        if _option_bool(request.options, "skip_send_messages"):
            command.append("--skip-send-messages")

    return command


def _parse_delegate_stdout(stdout_text: str) -> JsonObject:
    text = stdout_text.strip()
    if not text:
        raise SlashCommandError("DELEGATE_EMPTY_OUTPUT", "agent_team_command.py produced empty stdout")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise SlashCommandError("DELEGATE_INVALID_JSON", f"agent_team_command.py output is invalid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise SlashCommandError("DELEGATE_INVALID_JSON", "agent_team_command.py output must be a JSON object")
    return parsed


def route_agent_team(request: SlashCommandRequest) -> JsonObject:
    _ensure_payload_shape(request.payload)
    command = _build_delegate_command(request)

    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    delegated_output = _parse_delegate_stdout(proc.stdout or "")
    stderr_text = (proc.stderr or "").strip()
    delegated_ok = bool(delegated_output.get("ok"))
    delegate_error = delegated_output.get("error")

    if request.mode == "preview" and (proc.returncode != 0 or not delegated_ok):
        code = "DELEGATE_PREVIEW_FAILED"
        message = "agent_team_command plan delegation failed"
        if isinstance(delegate_error, dict):
            error_code = delegate_error.get("code")
            error_message = delegate_error.get("message")
            if isinstance(error_code, str) and error_code:
                code = error_code
            if isinstance(error_message, str) and error_message:
                message = error_message
        if stderr_text:
            message = f"{message} (stderr: {stderr_text})"
        raise SlashCommandError(code, message)

    return {
        "command_name": "agent_team",
        "mode": request.mode,
        "preview_default": request.mode == "preview",
        "delegation": {
            "delegate_entrypoint": str(AGENT_TEAM_COMMAND),
            "delegate_command": command,
            "delegate_command_shell": " ".join(shlex.quote(part) for part in command),
            "return_code": proc.returncode,
            "stderr": stderr_text or None,
            "delegated_ok": delegated_ok,
        },
        "delegate_output": delegated_output,
    }
