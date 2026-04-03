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

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def read_optional_json(path_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(path_text, str) or not path_text.strip():
        return None, None
    path = Path(path_text.strip())
    if not path.exists():
        return None, None
    return parse_json_file(path), str(path)


def summarize_triggers(gate_result: Dict[str, Any]) -> str:
    triggers = gate_result.get("triggers")
    if not isinstance(triggers, list) or not triggers:
        return "verifier gate triggered"
    parts: List[str] = []
    for item in triggers[:3]:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "UNKNOWN")
        detail = str(item.get("detail") or "").strip()
        if detail:
            parts.append(f"{code}: {detail}")
        else:
            parts.append(code)
    summary = " | ".join(parts) if parts else "verifier gate triggered"
    if len(summary) > 400:
        summary = summary[:397] + "..."
    return summary


def resolve_ids(
    source: Dict[str, Any],
    explicit_task_id: str,
    explicit_team_id: str,
) -> Dict[str, Optional[str]]:
    task_id, task_id_source = first_string(
        [
            ("--task-id", explicit_task_id),
            ("input.task_id", nested_get(source, ["input", "task_id"])),
            ("gate_result.checks.task_id", nested_get(source, ["gate_result", "checks", "task_id"])),
            ("verifier_result.parsed_json.task_id", nested_get(source, ["verifier_result", "parsed_json", "task_id"])),
        ]
    )
    team_id, team_id_source = first_string(
        [
            ("--team-id", explicit_team_id),
            ("input.team_id", nested_get(source, ["input", "team_id"])),
            ("gate_result.checks.team_id", nested_get(source, ["gate_result", "checks", "team_id"])),
            ("verifier_result.parsed_json.team_id", nested_get(source, ["verifier_result", "parsed_json", "team_id"])),
        ]
    )
    return {
        "task_id": task_id,
        "task_id_source": task_id_source,
        "team_id": team_id,
        "team_id_source": team_id_source,
    }


def resolve_upstream_context(source: Dict[str, Any]) -> Dict[str, Optional[Any]]:
    post_step_path = nested_get(source, ["input", "input_json"])
    post_step_json, post_step_resolved_path = read_optional_json(post_step_path if isinstance(post_step_path, str) else "")

    task_update_path = None
    task_update_json = None
    task_update_resolved_path = None
    session_path = None
    session_json = None
    session_resolved_path = None

    if isinstance(post_step_json, dict):
        candidate = nested_get(post_step_json, ["input", "input_json"])
        if isinstance(candidate, str):
            task_update_path = candidate
            task_update_json, task_update_resolved_path = read_optional_json(candidate)

    if isinstance(task_update_json, dict):
        candidate = nested_get(task_update_json, ["input", "input_json"])
        if isinstance(candidate, str):
            session_path = candidate
            session_json, session_resolved_path = read_optional_json(candidate)

    return {
        "post_step_path": post_step_resolved_path,
        "post_step_json": post_step_json,
        "task_update_path": task_update_resolved_path,
        "task_update_json": task_update_json,
        "session_path": session_resolved_path,
        "session_json": session_json,
    }


def resolve_from_member_id(
    explicit_from_member_id: str,
    source: Dict[str, Any],
    upstream: Dict[str, Optional[Any]],
) -> Tuple[Optional[str], Optional[str]]:
    task_update_json = upstream.get("task_update_json")
    session_json = upstream.get("session_json")
    return first_string(
        [
            ("--from-member-id", explicit_from_member_id),
            ("input.from_member_id", nested_get(source, ["input", "from_member_id"])),
            ("verifier_result.parsed_json.from_member_id", nested_get(source, ["verifier_result", "parsed_json", "from_member_id"])),
            ("task_update.input.from_member_id", nested_get(task_update_json, ["input", "from_member_id"]) if isinstance(task_update_json, dict) else None),
            ("session.ids.leader_id", nested_get(session_json, ["ids", "leader_id"]) if isinstance(session_json, dict) else None),
            (
                "session.next.followup_send_message_example.from_member_id",
                nested_get(session_json, ["next", "followup_send_message_example", "from_member_id"]) if isinstance(session_json, dict) else None,
            ),
        ]
    )


def run_task_update_notify(
    python_cmd: str,
    script_path: str,
    strict: bool,
    store_root: str,
    source_input_json: str,
    task_id: str,
    team_id: str,
    from_member_id: str,
    to_member_id: str,
    message_text: str,
    blocked_reason: str,
    task_idempotency_key: str,
    message_idempotency_key: str,
) -> Dict[str, Any]:
    cmd: List[str] = [python_cmd, script_path]
    if strict:
        cmd.append("--strict")
    if store_root:
        cmd.extend(["--store-root", store_root])
    if source_input_json:
        cmd.extend(["--input-json", source_input_json])
    cmd.extend(
        [
            "--task-id",
            task_id,
            "--team-id",
            team_id,
            "--state",
            "blocked",
            "--to-member-id",
            to_member_id,
            "--message-text",
            message_text,
            "--blocked-reason",
            blocked_reason,
        ]
    )
    if from_member_id:
        cmd.extend(["--from-member-id", from_member_id])
    if task_idempotency_key:
        cmd.extend(["--task-idempotency-key", task_idempotency_key])
    if message_idempotency_key:
        cmd.extend(["--message-idempotency-key", message_idempotency_key])

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
                parse_error = "task_update_notify_helper output is not a JSON object"
        except json.JSONDecodeError as error:
            parse_error = f"invalid task_update_notify_helper JSON output: {error}"
    else:
        parse_error = "empty task_update_notify_helper output"

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
        "task_update_notify_output": parsed,
        "stdout": text,
        "stderr": (proc.stderr or "").strip(),
        "ok": helper_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bridge helper: if verifier gate requires action, call task_update_notify_helper",
    )
    parser.add_argument("--input-json", required=True, help="verifier_gate_helper output json")
    parser.add_argument("--task-id", default="", help="explicit task_id override")
    parser.add_argument("--team-id", default="", help="explicit team_id override")
    parser.add_argument("--from-member-id", default="", help="optional explicit from_member_id override")
    parser.add_argument("--to-member-id", required=True, help="explicit notification recipient")
    parser.add_argument("--message-text", required=True, help="explicit notification text")
    parser.add_argument("--task-idempotency-key", default="")
    parser.add_argument("--message-idempotency-key", default="")
    parser.add_argument(
        "--python-cmd",
        default=os.environ.get("CODEX_BRIDGE_PYTHON_CMD", "python3"),
        help="python executable for calling task_update_notify_helper",
    )
    parser.add_argument(
        "--task-update-notify-script",
        default=os.environ.get(
            "CODEX_BRIDGE_TASK_UPDATE_NOTIFY_SCRIPT",
            str(REPO_ROOT / "poc" / "task_update_notify_helper.py"),
        ),
        help="task_update_notify_helper script path",
    )
    parser.add_argument("--store-root", default="")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    gate_input_path = Path(args.input_json)
    if not gate_input_path.exists():
        raise SystemExit(f"input json not found: {args.input_json}")

    source = parse_json_file(gate_input_path)
    gate_result = source.get("gate_result")
    if not isinstance(gate_result, dict):
        gate_result = {}
    requires_verifier = bool(gate_result.get("requires_verifier"))

    ids = resolve_ids(source=source, explicit_task_id=args.task_id, explicit_team_id=args.team_id)
    upstream = resolve_upstream_context(source)
    from_member_id, from_member_id_source = resolve_from_member_id(
        explicit_from_member_id=args.from_member_id,
        source=source,
        upstream=upstream,
    )

    blocked_reason = summarize_triggers(gate_result)
    bridge_result: Dict[str, Any]

    source_for_task_update_notify = upstream.get("task_update_path")
    if not isinstance(source_for_task_update_notify, str) or not source_for_task_update_notify:
        source_for_task_update_notify = nested_get(source, ["input", "input_json"])
    if not isinstance(source_for_task_update_notify, str):
        source_for_task_update_notify = ""

    if not requires_verifier:
        bridge_result = {
            "executed": False,
            "skipped_reason": "requires_verifier_false",
            "ok": True,
        }
    elif not ids.get("task_id") or not ids.get("team_id"):
        bridge_result = {
            "executed": False,
            "skipped_reason": "missing_task_or_team_id",
            "ok": False,
        }
    elif not from_member_id:
        bridge_result = {
            "executed": False,
            "skipped_reason": "missing_from_member_id",
            "ok": False,
        }
    else:
        bridge_result = run_task_update_notify(
            python_cmd=args.python_cmd,
            script_path=args.task_update_notify_script,
            strict=args.strict,
            store_root=args.store_root,
            source_input_json=source_for_task_update_notify,
            task_id=str(ids["task_id"]),
            team_id=str(ids["team_id"]),
            from_member_id=from_member_id,
            to_member_id=args.to_member_id,
            message_text=args.message_text,
            blocked_reason=blocked_reason,
            task_idempotency_key=args.task_idempotency_key,
            message_idempotency_key=args.message_idempotency_key,
        )

    helper_ok = bool(bridge_result.get("ok"))
    output = {
        "ts": utc_now_iso(),
        "helper": "bridge_helper",
        "mode": "strict" if args.strict else "fail-open",
        "ok": helper_ok,
        "input": {
            "input_json": args.input_json,
            "task_id": ids.get("task_id"),
            "task_id_source": ids.get("task_id_source"),
            "team_id": ids.get("team_id"),
            "team_id_source": ids.get("team_id_source"),
            "from_member_id": from_member_id,
            "from_member_id_source": from_member_id_source,
            "to_member_id": args.to_member_id,
            "message_text": args.message_text,
            "blocked_state": "blocked",
            "blocked_reason": blocked_reason,
            "task_idempotency_key": args.task_idempotency_key or None,
            "message_idempotency_key": args.message_idempotency_key or None,
            "task_update_notify_script": args.task_update_notify_script,
            "store_root": args.store_root or None,
        },
        "gate_result": gate_result,
        "bridge_result": bridge_result,
        "upstream_context": {
            "post_step_path": upstream.get("post_step_path"),
            "task_update_path": upstream.get("task_update_path"),
            "session_path": upstream.get("session_path"),
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
