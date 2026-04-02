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


def resolve_task_id(input_data: Dict[str, Any], explicit_task_id: str) -> Optional[str]:
    if explicit_task_id:
        return explicit_task_id
    next_block = input_data.get("next", {})
    if isinstance(next_block, dict):
        task_update_example = next_block.get("task_update_example", {})
        if isinstance(task_update_example, dict) and task_update_example.get("task_id"):
            return str(task_update_example["task_id"])
    ids_block = input_data.get("ids", {})
    if isinstance(ids_block, dict) and ids_block.get("task_id"):
        return str(ids_block["task_id"])
    return None


def run_runtime(
    runtime_cmd: List[str],
    strict: bool,
    args_json: Dict[str, Any],
    env: Dict[str, str],
) -> Dict[str, Any]:
    cmd = list(runtime_cmd)
    if strict:
        cmd.append("--strict")
    cmd.extend(
        [
            "op",
            "--name",
            "task_update",
            "--args-json",
            json.dumps(args_json, ensure_ascii=False),
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
        "helper_ok": helper_ok,
        "command": cmd,
        "exit_code": proc.returncode,
        "envelope": envelope,
        "parse_error": parse_error,
        "operation_ok": operation_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Thin helper for task_update using task_id from session_helper output",
    )
    parser.add_argument("--input-json", default="", help="session_helper output json path")
    parser.add_argument("--task-id", default="", help="explicit task_id (overrides --input-json)")
    parser.add_argument("--state", required=True, help="target task state")
    parser.add_argument("--blocked-reason", default="")
    parser.add_argument("--result-reference", default="")
    parser.add_argument("--idempotency-key", default="")
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

    task_id = resolve_task_id(source, args.task_id)
    if not task_id:
        raise SystemExit("task_id is required (use --task-id or provide --input-json from session_helper)")

    op_args: Dict[str, Any] = {
        "task_id": task_id,
        "state": args.state,
    }
    if args.blocked_reason:
        op_args["blocked_reason"] = args.blocked_reason
    if args.result_reference:
        op_args["result_reference"] = args.result_reference
    if args.idempotency_key:
        op_args["idempotency_key"] = args.idempotency_key

    env = os.environ.copy()
    if args.store_root:
        env["CODEX_RUNTIME_STORE_ROOT"] = args.store_root

    runtime_result = run_runtime(
        runtime_cmd=runtime_cmd,
        strict=args.strict,
        args_json=op_args,
        env=env,
    )

    output = {
        "ts": utc_now_iso(),
        "helper": "task_update_helper",
        "mode": "strict" if args.strict else "fail-open",
        "ok": runtime_result["helper_ok"],
        "runtime_cmd": runtime_cmd,
        "store_root": env.get("CODEX_RUNTIME_STORE_ROOT"),
        "input": {
            "input_json": source_path or None,
            "resolved_task_id": task_id,
            "state": args.state,
            "blocked_reason": args.blocked_reason or None,
            "result_reference": args.result_reference or None,
            "idempotency_key": args.idempotency_key or None,
        },
        "runtime": {
            "command": runtime_result["command"],
            "exit_code": runtime_result["exit_code"],
            "operation_ok": runtime_result["operation_ok"],
            "parse_error": runtime_result["parse_error"],
            "envelope": runtime_result["envelope"],
        },
        "next": {
            "task_get_example": {"task_id": task_id},
            "task_list_example": {
                "team_id": (source.get("ids", {}) if isinstance(source.get("ids", {}), dict) else {}).get("team_id"),
            },
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
