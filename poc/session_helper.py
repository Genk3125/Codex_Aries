#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StepResult:
    step: str
    command: List[str]
    exit_code: int
    envelope: Optional[Dict[str, Any]]
    parse_error: Optional[str]

    @property
    def operation_ok(self) -> Optional[bool]:
        if self.envelope is None:
            return None
        return bool(self.envelope.get("ok"))


def run_runtime_cmd(
    runtime_cmd: List[str],
    strict: bool,
    step: str,
    args: List[str],
    env: Dict[str, str],
) -> StepResult:
    cmd = list(runtime_cmd)
    if strict:
        cmd.append("--strict")
    cmd.extend(args)

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    text = (proc.stdout or "").strip()
    envelope: Optional[Dict[str, Any]] = None
    parse_error: Optional[str] = None
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

    return StepResult(
        step=step,
        command=cmd,
        exit_code=proc.returncode,
        envelope=envelope,
        parse_error=parse_error,
    )


def build_step_dict(step: StepResult) -> Dict[str, Any]:
    return {
        "step": step.step,
        "command": step.command,
        "exit_code": step.exit_code,
        "operation": (step.envelope or {}).get("operation"),
        "operation_ok": step.operation_ok,
        "error": (step.envelope or {}).get("error"),
        "result": (step.envelope or {}).get("result"),
        "parse_error": step.parse_error,
    }


def should_stop(step: StepResult) -> bool:
    if step.exit_code != 0:
        return True
    if step.parse_error:
        return True
    if step.operation_ok is False:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Thin session helper for team-create -> team_member_add -> task-create -> send-message",
    )
    parser.add_argument("--team-name", required=True)
    parser.add_argument("--member-id", required=True)
    parser.add_argument("--member-role", default="member")
    parser.add_argument("--task-title", required=True)
    parser.add_argument("--task-state", default="ready")
    parser.add_argument(
        "--task-owner",
        default="member",
        choices=["member", "leader"],
        help="Owner used for task-create",
    )
    parser.add_argument("--message-text", required=True)
    parser.add_argument("--team-idempotency-key", default="")
    parser.add_argument("--member-add-idempotency-key", default="")
    parser.add_argument("--task-idempotency-key", default="")
    parser.add_argument("--message-idempotency-key", default="")
    parser.add_argument(
        "--runtime-cmd",
        default=os.environ.get("CODEX_RUNTIME_HELPER_RUNTIME_CMD", "/Users/kondogenki/.codex/runtime-adapter/codex-runtime"),
        help="Runtime wrapper command path",
    )
    parser.add_argument("--store-root", default="")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output-json", default="")

    args = parser.parse_args()
    runtime_cmd = shlex.split(args.runtime_cmd)
    if not runtime_cmd:
        raise SystemExit("runtime command is empty")

    env = os.environ.copy()
    if args.store_root:
        env["CODEX_RUNTIME_STORE_ROOT"] = args.store_root

    steps: List[StepResult] = []
    ids: Dict[str, Any] = {
        "team_id": None,
        "leader_id": None,
        "member_id": args.member_id,
        "task_id": None,
        "message_id": None,
    }
    flow_error: Optional[Dict[str, Any]] = None

    team_create_cmd = ["team-create", args.team_name]
    if args.team_idempotency_key:
        team_create_cmd.append(args.team_idempotency_key)
    step = run_runtime_cmd(runtime_cmd, args.strict, "team_create", team_create_cmd, env)
    steps.append(step)
    if should_stop(step):
        flow_error = {"step": step.step, "reason": "team_create failed"}
    else:
        result = (step.envelope or {}).get("result", {})
        ids["team_id"] = result.get("team_id")
        ids["leader_id"] = result.get("leader_agent_id")
        if not ids["team_id"] or not ids["leader_id"]:
            flow_error = {"step": step.step, "reason": "team_create response missing ids"}

    if flow_error is None:
        member_args = {
            "team_id": ids["team_id"],
            "agent_id": args.member_id,
            "role": args.member_role,
        }
        if args.member_add_idempotency_key:
            member_args["idempotency_key"] = args.member_add_idempotency_key
        step = run_runtime_cmd(
            runtime_cmd,
            args.strict,
            "team_member_add",
            ["op", "--name", "team_member_add", "--args-json", json.dumps(member_args, ensure_ascii=False)],
            env,
        )
        steps.append(step)
        if should_stop(step):
            flow_error = {"step": step.step, "reason": "team_member_add failed"}

    if flow_error is None:
        owner_member_id = ids["leader_id"] if args.task_owner == "leader" else args.member_id
        task_cmd = ["task-create", ids["team_id"], args.task_title, owner_member_id, args.task_state]
        if args.task_idempotency_key:
            task_cmd.append(args.task_idempotency_key)
        step = run_runtime_cmd(runtime_cmd, args.strict, "task_create", task_cmd, env)
        steps.append(step)
        if should_stop(step):
            flow_error = {"step": step.step, "reason": "task_create failed"}
        else:
            task_result = (step.envelope or {}).get("result", {})
            ids["task_id"] = task_result.get("task_id")

    if flow_error is None:
        send_cmd = ["send-message", ids["team_id"], ids["leader_id"], args.member_id, args.message_text]
        if args.message_idempotency_key:
            send_cmd.append(args.message_idempotency_key)
        step = run_runtime_cmd(runtime_cmd, args.strict, "send_message", send_cmd, env)
        steps.append(step)
        if should_stop(step):
            flow_error = {"step": step.step, "reason": "send_message failed"}
        else:
            send_result = (step.envelope or {}).get("result", {})
            ids["message_id"] = send_result.get("message_id")

    step_dicts = [build_step_dict(step) for step in steps]
    helper_ok = flow_error is None
    output = {
        "ts": utc_now_iso(),
        "helper": "session_helper",
        "flow": "team_create->team_member_add->task_create->send_message",
        "mode": "strict" if args.strict else "fail-open",
        "runtime_cmd": runtime_cmd,
        "store_root": env.get("CODEX_RUNTIME_STORE_ROOT"),
        "ok": helper_ok,
        "error": flow_error,
        "ids": ids,
        "steps": step_dicts,
        "next": {
            "team_id": ids["team_id"],
            "leader_id": ids["leader_id"],
            "member_id": ids["member_id"],
            "task_id": ids["task_id"],
            "message_id": ids["message_id"],
            "task_update_example": {
                "task_id": ids["task_id"],
                "state": "in_progress",
                "idempotency_key": "<task-update-idempotency-key>",
            },
            "followup_send_message_example": {
                "team_id": ids["team_id"],
                "from_member_id": ids["leader_id"],
                "to_member_id": ids["member_id"],
                "text": "<next-message>",
                "idempotency_key": "<message-idempotency-key>",
            },
        },
    }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")

    if args.strict and not helper_ok:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
