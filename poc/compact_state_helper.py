#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

DEFAULT_STEP_ORDER = [
    "session_helper",
    "task_update_notify_helper",
    "post_step_check_helper",
    "verifier_gate_helper",
    "bridge_helper",
    "loopback_helper",
    "chain_helper",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_json_file(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("input json must be an object")
    return data


def to_unique_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            text = item.strip()
            if text not in result:
                result.append(text)
    return result


def pick_mode(orchestrator: Dict[str, Any], handoff: Optional[Dict[str, Any]], strict_flag: bool) -> str:
    if strict_flag:
        return "strict"
    mode = orchestrator.get("mode")
    if isinstance(mode, str) and mode in {"strict", "fail-open"}:
        return mode
    if isinstance(handoff, dict):
        mode2 = handoff.get("mode")
        if isinstance(mode2, str) and mode2 in {"strict", "fail-open"}:
            return mode2
    return "fail-open"


def render_command(command: Any, max_chars: int) -> Optional[str]:
    if isinstance(command, list) and all(isinstance(item, str) for item in command):
        text = shlex.join(command)
    elif isinstance(command, str) and command.strip():
        text = command.strip()
    else:
        return None
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def ordered_step_names(results: Dict[str, Any]) -> List[str]:
    names = [name for name in DEFAULT_STEP_ORDER if name in results]
    for name in results.keys():
        if isinstance(name, str) and name not in names:
            names.append(name)
    return names


def summarize_results(results: Dict[str, Any], max_commands: int, max_command_chars: int) -> Dict[str, Any]:
    step_names = ordered_step_names(results)
    last_successful_step: Optional[str] = None
    failed_step: Optional[Dict[str, Any]] = None
    failed_steps: List[str] = []
    skipped_steps: List[str] = []
    parse_error_steps: List[str] = []
    commands: List[Dict[str, str]] = []
    executed_count = 0
    succeeded_count = 0

    for step_name in step_names:
        raw_step = results.get(step_name)
        if not isinstance(raw_step, dict):
            continue

        executed = bool(raw_step.get("executed"))
        ok = bool(raw_step.get("ok"))

        if executed:
            executed_count += 1
            if ok:
                succeeded_count += 1
                last_successful_step = step_name
            else:
                failed_steps.append(step_name)
                if failed_step is None:
                    failed_step = {
                        "step": step_name,
                        "exit_code": raw_step.get("exit_code"),
                        "detail": "helper_step_failed",
                    }

            command_text = render_command(raw_step.get("command"), max_command_chars)
            if command_text is not None:
                commands.append({"step": step_name, "command": command_text})
        else:
            skipped_steps.append(step_name)

        parse_error_stdout = raw_step.get("parse_error_stdout")
        parse_error_file = raw_step.get("parse_error_file")
        parse_error = raw_step.get("parse_error")
        if any(isinstance(item, str) and item.strip() for item in [parse_error_stdout, parse_error_file, parse_error]):
            parse_error_steps.append(step_name)

    command_count = len(commands)
    shown_commands = commands[: max(0, max_commands)]
    omitted_count = max(0, command_count - len(shown_commands))

    return {
        "last_successful_step": last_successful_step,
        "failed_step": failed_step,
        "executed_commands_summary": {
            "count": command_count,
            "items": shown_commands,
            "omitted_count": omitted_count,
        },
        "actual_outputs_summary": {
            "total_steps": len(step_names),
            "executed_steps": executed_count,
            "succeeded_steps": succeeded_count,
            "failed_steps": failed_steps,
            "skipped_steps": skipped_steps,
            "parse_error_steps": parse_error_steps,
        },
    }


def extract_ids(orchestrator: Dict[str, Any]) -> Dict[str, Optional[str]]:
    results = orchestrator.get("results")
    session_output = None
    if isinstance(results, dict):
        session_step = results.get("session_helper")
        if isinstance(session_step, dict):
            candidate = session_step.get("output")
            if isinstance(candidate, dict):
                session_output = candidate

    ids: Dict[str, Optional[str]] = {
        "team_id": None,
        "task_id": None,
        "member_id": None,
        "leader_id": None,
    }

    input_obj = orchestrator.get("input")
    if isinstance(input_obj, dict):
        member_id = input_obj.get("member_id")
        if isinstance(member_id, str) and member_id.strip():
            ids["member_id"] = member_id.strip()

    if isinstance(session_output, dict):
        raw_ids = session_output.get("ids")
        if isinstance(raw_ids, dict):
            for key in ["team_id", "task_id", "member_id", "leader_id"]:
                value = raw_ids.get(key)
                if isinstance(value, str) and value.strip():
                    ids[key] = value.strip()
    return ids


def collect_stop_reasons(orchestrator: Dict[str, Any], handoff: Optional[Dict[str, Any]]) -> List[str]:
    stop_reasons: List[str] = []
    preflight = orchestrator.get("preflight_guard")
    if isinstance(preflight, dict):
        for reason in to_unique_str_list(preflight.get("stop_reasons")):
            if reason not in stop_reasons:
                stop_reasons.append(reason)
    post_run = orchestrator.get("guard")
    if isinstance(post_run, dict):
        for reason in to_unique_str_list(post_run.get("stop_reasons")):
            if reason not in stop_reasons:
                stop_reasons.append(reason)
    if isinstance(handoff, dict):
        handoff_obj = handoff.get("handoff")
        if isinstance(handoff_obj, dict):
            for reason in to_unique_str_list(handoff_obj.get("stop_reasons")):
                if reason not in stop_reasons:
                    stop_reasons.append(reason)
    return stop_reasons


def compute_current_status(
    orchestrator: Dict[str, Any],
    failed_step: Optional[Dict[str, Any]],
    handoff: Optional[Dict[str, Any]],
) -> str:
    preflight = orchestrator.get("preflight_guard")
    post_run = orchestrator.get("guard")
    orchestrator_ok = bool(orchestrator.get("ok"))

    status = "partial"
    if isinstance(preflight, dict) and preflight.get("decision") == "stop":
        status = "stopped_preflight"
    elif isinstance(post_run, dict) and post_run.get("decision") == "stop":
        status = "stopped_post_run"
    elif failed_step is not None:
        status = "failed"
    elif orchestrator_ok:
        status = "ok"

    if isinstance(handoff, dict):
        handoff_obj = handoff.get("handoff")
        if isinstance(handoff_obj, dict) and bool(handoff_obj.get("required")) and bool(handoff_obj.get("executed")):
            status = f"{status}_handoff_ready"
    return status


def infer_next_action(
    current_status: str,
    stop_reasons: List[str],
    handoff: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if isinstance(handoff, dict):
        handoff_obj = handoff.get("handoff")
        if isinstance(handoff_obj, dict) and bool(handoff_obj.get("required")) and bool(handoff_obj.get("executed")):
            suggested = handoff_obj.get("suggested_next_action")
            action_items: List[str] = []
            if isinstance(suggested, dict):
                action_items = to_unique_str_list(suggested.get("action_items"))
            return {
                "type": "handoff_ready",
                "hint": "Use verifier_draft/coordinator_draft from handoff output for manual handoff.",
                "action_items": action_items,
            }

    if "max_retries" in stop_reasons or "escalated" in stop_reasons:
        return {
            "type": "prepare_escalation",
            "hint": "Run escalation flow and prepare coordinator/verifier packet before next run.",
            "action_items": [
                "run recovery_next_helper",
                "run escalation_draft_helper",
                "optionally run handoff_helper",
            ],
        }
    if "manual_stop" in stop_reasons:
        return {
            "type": "manual_review",
            "hint": "Operator review is required before clearing manual_stop.",
            "action_items": ["review stop reason", "decide resume or keep stopped"],
        }
    if current_status.startswith("failed") or current_status.startswith("partial"):
        return {
            "type": "inspect_failure",
            "hint": "Inspect failed_step and summarize evidence before the next attempt.",
            "action_items": ["check compact_state.failed_step", "collect minimal evidence"],
        }
    return {
        "type": "proceed",
        "hint": "Proceed to the next task or finalize this run.",
        "action_items": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Thin helper: compact orchestrator/handoff outputs into minimal next-turn state",
    )
    parser.add_argument("--orchestrator-json", required=True)
    parser.add_argument("--handoff-json", default="")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--max-commands", type=int, default=6)
    parser.add_argument("--max-command-chars", type=int, default=180)
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    ok = True
    output: Dict[str, Any]
    try:
        orchestrator_path = Path(args.orchestrator_json)
        if not orchestrator_path.exists():
            raise ValueError(f"orchestrator json not found: {args.orchestrator_json}")
        orchestrator = parse_json_file(orchestrator_path)

        handoff: Optional[Dict[str, Any]] = None
        if args.handoff_json:
            handoff_path = Path(args.handoff_json)
            if not handoff_path.exists():
                raise ValueError(f"handoff json not found: {args.handoff_json}")
            handoff = parse_json_file(handoff_path)
        else:
            handoff_path = None

        mode = pick_mode(orchestrator, handoff, args.strict)
        results = orchestrator.get("results")
        if not isinstance(results, dict):
            raise ValueError("orchestrator results section is missing")

        step_summary = summarize_results(
            results=results,
            max_commands=max(0, int(args.max_commands)),
            max_command_chars=max(60, int(args.max_command_chars)),
        )
        stop_reasons = collect_stop_reasons(orchestrator, handoff)
        failed_step = step_summary["failed_step"]
        if failed_step is None and isinstance(handoff, dict):
            handoff_obj = handoff.get("handoff")
            if isinstance(handoff_obj, dict) and isinstance(handoff_obj.get("failed_step"), dict):
                failed_step = handoff_obj["failed_step"]
        current_status = compute_current_status(orchestrator, failed_step, handoff)
        next_action = infer_next_action(current_status, stop_reasons, handoff)
        ids = extract_ids(orchestrator)

        output = {
            "ts": utc_now_iso(),
            "helper": "compact_state_helper",
            "mode": mode,
            "ok": True,
            "input": {
                "orchestrator_json": str(orchestrator_path),
                "handoff_json": str(handoff_path) if handoff_path is not None else None,
            },
            "compact_state": {
                "current_status": current_status,
                "last_successful_step": step_summary["last_successful_step"],
                "failed_step": failed_step,
                "stop_reasons": stop_reasons,
                "executed_commands_summary": step_summary["executed_commands_summary"],
                "actual_outputs_summary": step_summary["actual_outputs_summary"],
                "next_action": next_action,
                "ids": ids,
                "meta": {
                    "run_id": orchestrator.get("run_id"),
                    "flow_mode": orchestrator.get("flow_mode"),
                    "single_pass": bool(orchestrator.get("single_pass", False)),
                },
                "note": "Compacted state only. No detailed logs, no runtime execution, no judgment replacement.",
            },
        }
    except Exception as error:
        ok = False
        output = {
            "ts": utc_now_iso(),
            "helper": "compact_state_helper",
            "mode": "strict" if args.strict else "fail-open",
            "ok": False,
            "error": {
                "code": "COMPACT_STATE_FAILED",
                "message": str(error),
            },
            "compact_state": {
                "current_status": "unavailable",
                "last_successful_step": None,
                "failed_step": None,
                "stop_reasons": [],
                "executed_commands_summary": {"count": 0, "items": [], "omitted_count": 0},
                "actual_outputs_summary": {
                    "total_steps": 0,
                    "executed_steps": 0,
                    "succeeded_steps": 0,
                    "failed_steps": [],
                    "skipped_steps": [],
                    "parse_error_steps": [],
                },
                "next_action": {"type": "none", "hint": "fix compact helper input first", "action_items": []},
                "ids": {"team_id": None, "task_id": None, "member_id": None, "leader_id": None},
                "meta": {"run_id": None, "flow_mode": None, "single_pass": None},
            },
        }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")

    if args.strict and not ok:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
