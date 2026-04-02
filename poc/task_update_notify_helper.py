#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_json_file(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("input json must be an object")
    return data


def nested_get(data: Dict[str, Any], path: List[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def first_string(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def resolve_task_id(source: Dict[str, Any], explicit_task_id: str) -> Optional[str]:
    return first_string(
        explicit_task_id,
        nested_get(source, ["next", "task_update_example", "task_id"]),
        nested_get(source, ["ids", "task_id"]),
        nested_get(source, ["input", "resolved_task_id"]),
        nested_get(source, ["runtime", "envelope", "args", "task_id"]),
        nested_get(source, ["runtime", "envelope", "result", "task_id"]),
        nested_get(source, ["next", "task_get_example", "task_id"]),
    )


def resolve_team_id(source: Dict[str, Any], explicit_team_id: str) -> Optional[str]:
    return first_string(
        explicit_team_id,
        nested_get(source, ["next", "team_id"]),
        nested_get(source, ["ids", "team_id"]),
        nested_get(source, ["next", "task_list_example", "team_id"]),
        nested_get(source, ["runtime", "envelope", "result", "team_id"]),
        nested_get(source, ["runtime", "envelope", "args", "team_id"]),
    )


def resolve_from_member_id(source: Dict[str, Any], explicit_from_member_id: str) -> Optional[str]:
    return first_string(
        explicit_from_member_id,
        nested_get(source, ["next", "followup_send_message_example", "from_member_id"]),
        nested_get(source, ["ids", "leader_id"]),
    )


def run_runtime_op(
    runtime_cmd: List[str],
    strict: bool,
    operation_name: str,
    op_args: Dict[str, Any],
    env: Dict[str, str],
) -> Dict[str, Any]:
    cmd = list(runtime_cmd)
    if strict:
        cmd.append("--strict")
    cmd.extend(
        [
            "op",
            "--name",
            operation_name,
            "--args-json",
            json.dumps(op_args, ensure_ascii=False),
        ]
    )
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    text = (proc.stdout or "").strip()
    envelope = None
    parse_error = None
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                envelope = parsed
            else:
                parse_error = "runtime output is not a JSON object"
        except json.JSONDecodeError as error:
            parse_error = f"invalid runtime JSON output: {error}"
    else:
        parse_error = "empty runtime output"

    operation_ok = None
    if isinstance(envelope, dict):
        operation_ok = bool(envelope.get("ok"))
    helper_ok = proc.returncode == 0 and parse_error is None and operation_ok is True
    return {
        "executed": True,
        "command": cmd,
        "exit_code": proc.returncode,
        "operation_ok": operation_ok,
        "parse_error": parse_error,
        "envelope": envelope,
        "ok": helper_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Thin helper that runs task_update then send_message on success",
    )
    parser.add_argument("--input-json", default="", help="session_helper or task_update_helper output json")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--team-id", default="")
    parser.add_argument("--from-member-id", default="")
    parser.add_argument("--to-member-id", required=True)
    parser.add_argument("--message-text", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--blocked-reason", default="")
    parser.add_argument("--result-reference", default="")
    parser.add_argument("--task-idempotency-key", default="")
    parser.add_argument("--message-idempotency-key", default="")
    parser.add_argument(
        "--runtime-cmd",
        default=os.environ.get("CODEX_RUNTIME_HELPER_RUNTIME_CMD", "/Users/kondogenki/.codex/runtime-adapter/codex-runtime"),
        help="runtime wrapper command",
    )
    parser.add_argument("--store-root", default="")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    runtime_cmd = shlex.split(args.runtime_cmd)
    if not runtime_cmd:
        raise SystemExit("runtime command is empty")

    source: Dict[str, Any] = {}
    source_path = ""
    if args.input_json:
        source_path = args.input_json
        input_path = Path(args.input_json)
        if not input_path.exists():
            raise SystemExit(f"input json not found: {args.input_json}")
        source = parse_json_file(input_path)

    resolved_task_id = resolve_task_id(source, args.task_id)
    resolved_team_id = resolve_team_id(source, args.team_id)
    resolved_from_member_id = resolve_from_member_id(source, args.from_member_id)

    task_update_output: Dict[str, Any] = {"executed": False}
    send_message_output: Dict[str, Any] = {"executed": False}
    helper_error: Optional[Dict[str, str]] = None

    if not resolved_task_id:
        helper_error = {
            "step": "resolve_inputs",
            "reason": "task_id is required (use --task-id or --input-json)",
        }
    elif not resolved_team_id:
        helper_error = {
            "step": "resolve_inputs",
            "reason": "team_id is required for send_message (use --team-id or --input-json with team context)",
        }
    elif not resolved_from_member_id:
        helper_error = {
            "step": "resolve_inputs",
            "reason": "from_member_id is required for send_message (use --from-member-id or --input-json with leader context)",
        }

    env = os.environ.copy()
    if args.store_root:
        env["CODEX_RUNTIME_STORE_ROOT"] = args.store_root

    if helper_error is None:
        task_update_args: Dict[str, Any] = {
            "task_id": resolved_task_id,
            "state": args.state,
        }
        if args.blocked_reason:
            task_update_args["blocked_reason"] = args.blocked_reason
        if args.result_reference:
            task_update_args["result_reference"] = args.result_reference
        if args.task_idempotency_key:
            task_update_args["idempotency_key"] = args.task_idempotency_key

        task_update_output = run_runtime_op(
            runtime_cmd=runtime_cmd,
            strict=args.strict,
            operation_name="task_update",
            op_args=task_update_args,
            env=env,
        )

        if task_update_output["ok"]:
            send_args: Dict[str, Any] = {
                "team_id": resolved_team_id,
                "from_member_id": resolved_from_member_id,
                "to_member_id": args.to_member_id,
                "message_type": "direct",
                "payload": {"text": args.message_text},
            }
            if args.message_idempotency_key:
                send_args["idempotency_key"] = args.message_idempotency_key

            send_message_output = run_runtime_op(
                runtime_cmd=runtime_cmd,
                strict=args.strict,
                operation_name="send_message",
                op_args=send_args,
                env=env,
            )
        else:
            send_message_output = {
                "executed": False,
                "skipped_reason": "task_update_failed",
            }

    helper_ok = helper_error is None and bool(task_update_output.get("ok")) and bool(send_message_output.get("ok"))
    output = {
        "ts": utc_now_iso(),
        "helper": "task_update_notify_helper",
        "mode": "strict" if args.strict else "fail-open",
        "ok": helper_ok,
        "error": helper_error,
        "runtime_cmd": runtime_cmd,
        "store_root": env.get("CODEX_RUNTIME_STORE_ROOT"),
        "input": {
            "input_json": source_path or None,
            "task_id": resolved_task_id,
            "team_id": resolved_team_id,
            "from_member_id": resolved_from_member_id,
            "to_member_id": args.to_member_id,
            "message_text": args.message_text,
            "state": args.state,
            "blocked_reason": args.blocked_reason or None,
            "result_reference": args.result_reference or None,
            "task_idempotency_key": args.task_idempotency_key or None,
            "message_idempotency_key": args.message_idempotency_key or None,
        },
        "task_update": task_update_output,
        "send_message": send_message_output,
        "next": {
            "task_get_example": {"task_id": resolved_task_id},
            "message_list_example": {"team_id": resolved_team_id},
            "reconcile_all_example": {},
        },
    }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")

    if args.strict and not helper_ok:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
