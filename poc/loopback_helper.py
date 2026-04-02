#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
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
            ("input.task_id", nested_get(source, ["input", "task_id"])),
            (
                "bridge_result.task_update_notify_output.input.task_id",
                nested_get(source, ["bridge_result", "task_update_notify_output", "input", "task_id"]),
            ),
            (
                "bridge_result.task_update_notify_output.task_update.envelope.result.task_id",
                nested_get(source, ["bridge_result", "task_update_notify_output", "task_update", "envelope", "result", "task_id"]),
            ),
            ("gate_result.checks.task_id", nested_get(source, ["gate_result", "checks", "task_id"])),
        ]
    )


def resolve_team_id(source: Dict[str, Any], explicit_team_id: str) -> Tuple[Optional[str], Optional[str]]:
    return first_string(
        [
            ("--team-id", explicit_team_id),
            ("input.team_id", nested_get(source, ["input", "team_id"])),
            (
                "bridge_result.task_update_notify_output.input.team_id",
                nested_get(source, ["bridge_result", "task_update_notify_output", "input", "team_id"]),
            ),
            (
                "bridge_result.task_update_notify_output.task_update.envelope.result.team_id",
                nested_get(source, ["bridge_result", "task_update_notify_output", "task_update", "envelope", "result", "team_id"]),
            ),
            ("gate_result.checks.team_id", nested_get(source, ["gate_result", "checks", "team_id"])),
        ]
    )


def run_post_check(
    python_cmd: str,
    script_path: str,
    strict: bool,
    store_root: str,
    task_id: str,
    team_id: str,
) -> Dict[str, Any]:
    cmd: List[str] = [python_cmd, script_path]
    if strict:
        cmd.append("--strict")
    if store_root:
        cmd.extend(["--store-root", store_root])
    cmd.extend(["--task-id", task_id, "--team-id", team_id])

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=os.environ.copy())
    text = (proc.stdout or "").strip()
    parse_error = None
    parsed = None
    if text:
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                parsed = obj
            else:
                parse_error = "post_step_check_helper output is not a JSON object"
        except json.JSONDecodeError as error:
            parse_error = f"invalid post_step_check_helper JSON output: {error}"
    else:
        parse_error = "empty post_step_check_helper output"

    operation_ok = None
    if isinstance(parsed, dict):
        operation_ok = bool(parsed.get("ok"))
    helper_ok = proc.returncode == 0 and parse_error is None and operation_ok is True

    return {
        "executed": True,
        "command": cmd,
        "exit_code": proc.returncode,
        "operation_ok": operation_ok,
        "parse_error": parse_error,
        "post_step_check_output": parsed,
        "stdout": text,
        "stderr": (proc.stderr or "").strip(),
        "ok": helper_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Loopback helper: rerun post_step_check_helper after bridge execution",
    )
    parser.add_argument("--input-json", required=True, help="bridge_helper output json")
    parser.add_argument("--task-id", default="", help="explicit task_id override")
    parser.add_argument("--team-id", default="", help="explicit team_id override")
    parser.add_argument(
        "--python-cmd",
        default=os.environ.get("CODEX_LOOPBACK_PYTHON_CMD", "python3"),
        help="python executable for calling post_step_check_helper",
    )
    parser.add_argument(
        "--post-check-script",
        default=os.environ.get(
            "CODEX_LOOPBACK_POST_CHECK_SCRIPT",
            "/Users/kondogenki/AI Agent Maximizer/poc/post_step_check_helper.py",
        ),
        help="post_step_check_helper script path",
    )
    parser.add_argument("--store-root", default="", help="runtime store root override")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    if not input_path.exists():
        raise SystemExit(f"input json not found: {args.input_json}")
    source = parse_json_file(input_path)

    bridge_result = source.get("bridge_result")
    if not isinstance(bridge_result, dict):
        bridge_result = {}
    bridge_executed = bool(bridge_result.get("executed"))

    task_id, task_id_source = resolve_task_id(source, args.task_id)
    team_id, team_id_source = resolve_team_id(source, args.team_id)

    resolved_store_root = args.store_root
    if not resolved_store_root:
        candidate = nested_get(source, ["input", "store_root"])
        if isinstance(candidate, str):
            resolved_store_root = candidate

    post_check_result: Dict[str, Any]
    if not bridge_executed:
        post_check_result = {
            "executed": False,
            "skipped_reason": "bridge_not_executed",
            "ok": True,
        }
    elif not task_id or not team_id:
        post_check_result = {
            "executed": False,
            "skipped_reason": "missing_task_or_team_id",
            "ok": False,
        }
    else:
        post_check_result = run_post_check(
            python_cmd=args.python_cmd,
            script_path=args.post_check_script,
            strict=args.strict,
            store_root=resolved_store_root,
            task_id=task_id,
            team_id=team_id,
        )

    helper_ok = bool(post_check_result.get("ok"))
    output = {
        "ts": utc_now_iso(),
        "helper": "loopback_helper",
        "mode": "strict" if args.strict else "fail-open",
        "ok": helper_ok,
        "input": {
            "input_json": args.input_json,
            "task_id": task_id,
            "task_id_source": task_id_source,
            "team_id": team_id,
            "team_id_source": team_id_source,
            "post_check_script": args.post_check_script,
            "store_root": resolved_store_root or None,
        },
        "bridge_result": bridge_result,
        "post_check_result": post_check_result,
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
