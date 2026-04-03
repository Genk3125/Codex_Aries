#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.slash_commands import SlashCommandError, build_request, resolve_mode, route_request  # noqa: E402


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_payload(input_file: str, input_json: str) -> dict[str, Any]:
    if input_file:
        raw = Path(input_file).read_text(encoding="utf-8")
    else:
        raw = input_json
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SlashCommandError("VALIDATION_ERROR", "slash command input must be a JSON object")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Slash adapter (preview-first). Default mode=preview; use --apply to execute apply mode explicitly.",
    )
    parser.add_argument(
        "slash_command",
        help="Slash command name (e.g. /agent_team or agent_team)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Explicitly use apply mode. Omitted means preview mode.",
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--input-file", default="", help="Path to command payload JSON")
    source_group.add_argument("--input-json", default="", help="Payload JSON object string")
    parser.add_argument("--presets-file", default="", help="Pass-through to agent_team_command --presets-file")
    parser.add_argument("--runtime-cmd", default="", help="Pass-through to agent_team_command --runtime-cmd")
    parser.add_argument("--store-root", default="", help="Pass-through to agent_team_command --store-root")
    parser.add_argument("--idempotency-prefix", default="", help="Pass-through to agent_team_command --idempotency-prefix")
    parser.add_argument("--strict", action="store_true", help="Pass-through strict mode (apply only)")
    parser.add_argument("--force-task-create", action="store_true", help="Pass-through flag (apply only)")
    parser.add_argument("--skip-task-create", action="store_true", help="Pass-through flag (apply only)")
    parser.add_argument("--force-send-messages", action="store_true", help="Pass-through flag (apply only)")
    parser.add_argument("--skip-send-messages", action="store_true", help="Pass-through flag (apply only)")
    parser.add_argument("--output-json", default="", help="Optional path to save rendered envelope")
    return parser


def build_envelope(
    *,
    mode: str,
    command_name: str,
    parse: dict[str, Any],
    validate: dict[str, Any],
    route: dict[str, Any],
    result: dict[str, Any] | None,
    error: dict[str, str] | None,
) -> dict[str, Any]:
    return {
        "ts": utc_now_iso(),
        "mode": mode,
        "command_name": command_name,
        "ok": error is None,
        "stages": {
            "parse": parse,
            "validate": validate,
            "route": route,
            "render": {"status": "done"},
        },
        "result": result,
        "error": error,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    mode = resolve_mode(args.apply)

    options: dict[str, Any] = {
        "presets_file": args.presets_file or None,
        "runtime_cmd": args.runtime_cmd or None,
        "store_root": args.store_root or None,
        "idempotency_prefix": args.idempotency_prefix or None,
        "strict": bool(args.strict),
        "force_task_create": bool(args.force_task_create),
        "skip_task_create": bool(args.skip_task_create),
        "force_send_messages": bool(args.force_send_messages),
        "skip_send_messages": bool(args.skip_send_messages),
    }
    input_source = {
        "input_file": args.input_file or None,
        "input_json": None if args.input_file else "<provided>",
    }

    parse_stage = {
        "raw_command": args.slash_command,
        "resolved_mode": mode,
        "preview_default_applied": not args.apply,
        "input_source": input_source,
    }

    try:
        payload = load_payload(args.input_file, args.input_json)
        request = build_request(
            raw_command=args.slash_command,
            mode=mode,
            payload=payload,
            options=options,
        )
        result = route_request(request)
        envelope = build_envelope(
            mode=mode,
            command_name=request.command_name,
            parse=parse_stage,
            validate={"status": "ok", "payload_type": "json_object"},
            route={"status": "ok", "delegate": "agent_team_command.py"},
            result=result,
            error=None,
        )
        route_ok = isinstance(result, dict) and bool(
            (((result.get("delegate_output") or {}).get("ok")) if isinstance(result.get("delegate_output"), dict) else False)
        )
        if mode == "apply":
            exit_code = 0 if route_ok else 2
        else:
            exit_code = 0
    except FileNotFoundError as error:
        envelope = build_envelope(
            mode=mode,
            command_name=args.slash_command,
            parse=parse_stage,
            validate={"status": "failed"},
            route={"status": "not_reached"},
            result=None,
            error={"code": "INPUT_NOT_FOUND", "message": str(error)},
        )
        exit_code = 2
    except json.JSONDecodeError as error:
        envelope = build_envelope(
            mode=mode,
            command_name=args.slash_command,
            parse=parse_stage,
            validate={"status": "failed"},
            route={"status": "not_reached"},
            result=None,
            error={"code": "INVALID_JSON", "message": str(error)},
        )
        exit_code = 2
    except SlashCommandError as error:
        envelope = build_envelope(
            mode=mode,
            command_name=args.slash_command,
            parse=parse_stage,
            validate={"status": "failed"},
            route={"status": "failed"},
            result=None,
            error={"code": error.code, "message": error.message},
        )
        exit_code = 2

    text = json.dumps(envelope, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
