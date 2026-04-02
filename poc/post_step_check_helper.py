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
from typing import Any, Dict, List, Optional, Sequence, Tuple


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_json_file(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("input json must be an object")
    return data


def nested_get(data: Dict[str, Any], path: Sequence[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def first_string(values: Sequence[Tuple[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    for label, value in values:
        if isinstance(value, str) and value.strip():
            return value.strip(), label
    return None, None


def resolve_task_id(source: Dict[str, Any], explicit_task_id: str) -> Tuple[Optional[str], Optional[str]]:
    return first_string(
        [
            ("--task-id", explicit_task_id),
            ("next.task_update_example.task_id", nested_get(source, ["next", "task_update_example", "task_id"])),
            ("ids.task_id", nested_get(source, ["ids", "task_id"])),
            ("input.task_id", nested_get(source, ["input", "task_id"])),
            ("input.resolved_task_id", nested_get(source, ["input", "resolved_task_id"])),
            ("task_update.envelope.result.task_id", nested_get(source, ["task_update", "envelope", "result", "task_id"])),
            ("task_update.envelope.args.task_id", nested_get(source, ["task_update", "envelope", "args", "task_id"])),
            ("runtime.envelope.result.task_id", nested_get(source, ["runtime", "envelope", "result", "task_id"])),
            ("runtime.envelope.args.task_id", nested_get(source, ["runtime", "envelope", "args", "task_id"])),
            ("next.task_get_example.task_id", nested_get(source, ["next", "task_get_example", "task_id"])),
        ]
    )


def resolve_team_id(source: Dict[str, Any], explicit_team_id: str) -> Tuple[Optional[str], Optional[str]]:
    return first_string(
        [
            ("--team-id", explicit_team_id),
            ("next.team_id", nested_get(source, ["next", "team_id"])),
            ("ids.team_id", nested_get(source, ["ids", "team_id"])),
            ("input.team_id", nested_get(source, ["input", "team_id"])),
            ("task_update.envelope.result.team_id", nested_get(source, ["task_update", "envelope", "result", "team_id"])),
            ("task_update.envelope.args.team_id", nested_get(source, ["task_update", "envelope", "args", "team_id"])),
            ("runtime.envelope.result.team_id", nested_get(source, ["runtime", "envelope", "result", "team_id"])),
            ("runtime.envelope.args.team_id", nested_get(source, ["runtime", "envelope", "args", "team_id"])),
            ("next.message_list_example.team_id", nested_get(source, ["next", "message_list_example", "team_id"])),
            ("next.task_list_example.team_id", nested_get(source, ["next", "task_list_example", "team_id"])),
        ]
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
        description="Thin helper for post-step checks: reconcile-all -> task_get -> message_list",
    )
    parser.add_argument("--input-json", default="", help="session/task helper output json")
    parser.add_argument("--task-id", default="", help="explicit task_id override")
    parser.add_argument("--team-id", default="", help="explicit team_id override")
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

    resolved_task_id, task_id_source = resolve_task_id(source, args.task_id)
    resolved_team_id, team_id_source = resolve_team_id(source, args.team_id)

    env = os.environ.copy()
    if args.store_root:
        env["CODEX_RUNTIME_STORE_ROOT"] = args.store_root

    reconcile_result = run_runtime_op(
        runtime_cmd=runtime_cmd,
        strict=args.strict,
        operation_name="runtime_reconcile_all",
        op_args={},
        env=env,
    )

    task_get_result: Dict[str, Any]
    if resolved_task_id:
        task_get_result = run_runtime_op(
            runtime_cmd=runtime_cmd,
            strict=args.strict,
            operation_name="task_get",
            op_args={"task_id": resolved_task_id},
            env=env,
        )
    else:
        task_get_result = {"executed": False, "skipped_reason": "task_id_unresolved"}

    message_list_result: Dict[str, Any]
    if resolved_team_id:
        message_list_result = run_runtime_op(
            runtime_cmd=runtime_cmd,
            strict=args.strict,
            operation_name="message_list",
            op_args={"team_id": resolved_team_id},
            env=env,
        )
    else:
        message_list_result = {"executed": False, "skipped_reason": "team_id_unresolved"}

    all_ok = bool(reconcile_result.get("ok")) and bool(task_get_result.get("ok")) and bool(message_list_result.get("ok"))
    output = {
        "ts": utc_now_iso(),
        "helper": "post_step_check_helper",
        "mode": "strict" if args.strict else "fail-open",
        "ok": all_ok,
        "runtime_cmd": runtime_cmd,
        "store_root": env.get("CODEX_RUNTIME_STORE_ROOT"),
        "input": {
            "input_json": source_path or None,
            "task_id": resolved_task_id,
            "task_id_source": task_id_source,
            "team_id": resolved_team_id,
            "team_id_source": team_id_source,
        },
        "reconcile": reconcile_result,
        "task_get": task_get_result,
        "message_list": message_list_result,
        "next": {
            "task_update_notify_example": {
                "task_id": resolved_task_id,
                "team_id": resolved_team_id,
                "state": "<next-state>",
                "to_member_id": "<member-id>",
                "message_text": "<message>",
            },
            "team_list_example": {},
        },
    }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")

    if args.strict and not output["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
