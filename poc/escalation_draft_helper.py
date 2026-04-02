#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
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


def first_string(values: Sequence[Any]) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def mode_from_inputs(orchestrator: Dict[str, Any], recovery: Dict[str, Any], strict_flag: bool) -> str:
    mode = first_string([orchestrator.get("mode"), recovery.get("mode")])
    if mode in {"strict", "fail-open"}:
        return mode
    return "strict" if strict_flag else "fail-open"


def normalize_stop_reason_details(recovery: Dict[str, Any]) -> List[Dict[str, str]]:
    summary = recovery.get("guard_summary")
    if not isinstance(summary, dict):
        return []
    raw = summary.get("stop_reason_details")
    if not isinstance(raw, list):
        return []
    normalized: List[Dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        reason = item.get("reason")
        source = item.get("source")
        if not isinstance(reason, str) or not reason.strip():
            continue
        if not isinstance(source, str) or not source.strip():
            source = "unknown"
        normalized.append({"reason": reason.strip(), "source": source.strip()})
    return normalized


def unique_stop_reasons(details: List[Dict[str, str]]) -> List[str]:
    reasons: List[str] = []
    for item in details:
        reason = item["reason"]
        if reason not in reasons:
            reasons.append(reason)
    return reasons


def branch_requires_escalation(branch: Dict[str, Any]) -> bool:
    branch_id = branch.get("branch_id")
    if isinstance(branch_id, str) and branch_id in {
        "max-retries-escalate",
        "escalated-review",
        "unknown-reason-review",
    }:
        return True

    playbook_ref = branch.get("playbook_ref")
    if isinstance(playbook_ref, dict):
        sections = playbook_ref.get("sections")
        if isinstance(sections, list):
            for section in sections:
                if isinstance(section, str) and section.strip() == "3.3 Escalate":
                    return True
    return False


def resolve_escalation_branches(recovery: Dict[str, Any]) -> List[Dict[str, Any]]:
    recovery_next = recovery.get("recovery_next")
    if not isinstance(recovery_next, dict):
        return []
    branches = recovery_next.get("branches")
    if not isinstance(branches, list):
        return []
    results: List[Dict[str, Any]] = []
    for item in branches:
        if not isinstance(item, dict):
            continue
        if branch_requires_escalation(item):
            results.append(item)
    return results


def stringify_command(command: Any) -> Optional[str]:
    if isinstance(command, list) and all(isinstance(item, str) for item in command):
        return shlex.join(command)
    if isinstance(command, str) and command.strip():
        return command.strip()
    return None


def collect_executed_commands(orchestrator: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = orchestrator.get("results")
    if not isinstance(results, dict):
        return []
    commands: List[Dict[str, Any]] = []
    for step_name, step in results.items():
        if not isinstance(step_name, str) or not isinstance(step, dict):
            continue
        if not bool(step.get("executed")):
            continue
        rendered = stringify_command(step.get("command"))
        if not rendered:
            continue
        commands.append({"step": step_name, "command": rendered})
    return commands


def summarize_step_output(step_name: str, step: Dict[str, Any], stderr_chars: int) -> Dict[str, Any]:
    executed = bool(step.get("executed"))
    if not executed:
        return {
            "step": step_name,
            "status": "skipped",
            "ok": True,
            "detail": step.get("skipped_reason"),
        }

    ok = bool(step.get("ok"))
    status = "ok" if ok else "failed"
    stderr_text = step.get("stderr")
    if not isinstance(stderr_text, str):
        stderr_text = ""
    parse_error_stdout = step.get("parse_error_stdout")
    parse_error_file = step.get("parse_error_file")
    return {
        "step": step_name,
        "status": status,
        "ok": ok,
        "exit_code": step.get("exit_code"),
        "operation_ok": step.get("operation_ok"),
        "parse_error_stdout": parse_error_stdout if isinstance(parse_error_stdout, str) else None,
        "parse_error_file": parse_error_file if isinstance(parse_error_file, str) else None,
        "stderr_excerpt": stderr_text[:stderr_chars] if stderr_text else None,
    }


def summarize_actual_outputs(orchestrator: Dict[str, Any], stderr_chars: int) -> Dict[str, Any]:
    results = orchestrator.get("results")
    if not isinstance(results, dict):
        return {
            "failed_count": 0,
            "skipped_count": 0,
            "step_summaries": [],
        }

    step_summaries: List[Dict[str, Any]] = []
    failed_count = 0
    skipped_count = 0
    for step_name, step in results.items():
        if not isinstance(step_name, str) or not isinstance(step, dict):
            continue
        summary = summarize_step_output(step_name, step, stderr_chars)
        if summary["status"] == "failed":
            failed_count += 1
        if summary["status"] == "skipped":
            skipped_count += 1
        step_summaries.append(summary)
    return {
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "step_summaries": step_summaries,
    }


def find_failed_step(orchestrator: Dict[str, Any], stop_reason_details: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    results = orchestrator.get("results")
    if isinstance(results, dict):
        for step_name, step in results.items():
            if not isinstance(step_name, str) or not isinstance(step, dict):
                continue
            if bool(step.get("executed")) and not bool(step.get("ok")):
                return {
                    "step": step_name,
                    "detail": "helper_step_failed",
                    "exit_code": step.get("exit_code"),
                }

    preflight = orchestrator.get("preflight_guard")
    if isinstance(preflight, dict) and preflight.get("decision") == "stop":
        return {"step": "preflight_guard", "detail": "preflight_stop", "exit_code": None}

    post_guard = orchestrator.get("guard")
    if isinstance(post_guard, dict) and post_guard.get("decision") == "stop":
        return {"step": "post_run_guard", "detail": "post_run_stop", "exit_code": None}

    if stop_reason_details:
        return {"step": "guard_stop_reason", "detail": stop_reason_details[0]["reason"], "exit_code": None}
    return None


def collect_suggested_actions(escalation_branches: List[Dict[str, Any]]) -> Dict[str, Any]:
    branch_ids: List[str] = []
    action_items: List[str] = []
    refs: List[Dict[str, Any]] = []

    for branch in escalation_branches:
        branch_id = branch.get("branch_id")
        if isinstance(branch_id, str) and branch_id not in branch_ids:
            branch_ids.append(branch_id)

        playbook_ref = branch.get("playbook_ref")
        if isinstance(playbook_ref, dict):
            refs.append(
                {
                    "path": playbook_ref.get("path"),
                    "sections": playbook_ref.get("sections"),
                }
            )

        template = branch.get("template")
        if isinstance(template, dict):
            next_actions = template.get("next_actions")
            if isinstance(next_actions, list):
                for item in next_actions:
                    if isinstance(item, str) and item not in action_items:
                        action_items.append(item)

    return {
        "branch_ids": branch_ids,
        "playbook_refs": refs,
        "action_items": action_items,
        "handoff_template": {
            "required_fields": [
                "executed_commands",
                "actual_outputs_summary",
                "failed_step",
                "stop_reasons",
                "suggested_next_action",
            ],
            "note": "Draft fields only. Coordinator/verifier decide final handling.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Thin helper: build escalation attachment draft from orchestrator + recovery-next outputs",
    )
    parser.add_argument("--orchestrator-json", required=True)
    parser.add_argument("--recovery-json", required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--stderr-chars", type=int, default=240)
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    ok = True
    output: Dict[str, Any]
    try:
        orchestrator_path = Path(args.orchestrator_json)
        recovery_path = Path(args.recovery_json)
        if not orchestrator_path.exists():
            raise ValueError(f"orchestrator json not found: {args.orchestrator_json}")
        if not recovery_path.exists():
            raise ValueError(f"recovery json not found: {args.recovery_json}")

        orchestrator = parse_json_file(orchestrator_path)
        recovery = parse_json_file(recovery_path)
        mode = mode_from_inputs(orchestrator, recovery, args.strict)
        stop_reason_details = normalize_stop_reason_details(recovery)
        stop_reasons = unique_stop_reasons(stop_reason_details)
        escalation_branches = resolve_escalation_branches(recovery)

        if not escalation_branches:
            output = {
                "ts": utc_now_iso(),
                "helper": "escalation_draft_helper",
                "mode": mode,
                "ok": True,
                "input": {
                    "orchestrator_json": str(orchestrator_path),
                    "recovery_json": str(recovery_path),
                },
                "escalation_draft": {
                    "required": False,
                    "executed": False,
                    "skipped_reason": "no_escalation_branch",
                    "stop_reasons": stop_reasons,
                    "note": "Recovery mapping indicates no escalation branch. Draft generation is skipped.",
                },
            }
        else:
            executed_commands = collect_executed_commands(orchestrator)
            actual_outputs = summarize_actual_outputs(orchestrator, max(40, args.stderr_chars))
            failed_step = find_failed_step(orchestrator, stop_reason_details)
            suggested_next_action = collect_suggested_actions(escalation_branches)

            output = {
                "ts": utc_now_iso(),
                "helper": "escalation_draft_helper",
                "mode": mode,
                "ok": True,
                "input": {
                    "orchestrator_json": str(orchestrator_path),
                    "recovery_json": str(recovery_path),
                },
                "escalation_draft": {
                    "required": True,
                    "executed": True,
                    "failed_step": failed_step,
                    "stop_reasons": stop_reasons,
                    "stop_reason_details": stop_reason_details,
                    "executed_commands": executed_commands,
                    "actual_outputs": actual_outputs,
                    "suggested_next_action": suggested_next_action,
                    "note": "Material preparation only. No retry, no verdict, no side-effect operations.",
                },
            }
    except Exception as error:
        ok = False
        output = {
            "ts": utc_now_iso(),
            "helper": "escalation_draft_helper",
            "mode": "strict" if args.strict else "fail-open",
            "ok": False,
            "error": {
                "code": "ESCALATION_DRAFT_FAILED",
                "message": str(error),
            },
            "escalation_draft": {
                "required": False,
                "executed": False,
                "stop_reasons": [],
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
