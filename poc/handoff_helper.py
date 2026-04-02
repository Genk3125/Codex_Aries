#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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


def pick_mode(payload: Dict[str, Any], strict_flag: bool) -> str:
    if strict_flag:
        return "strict"
    mode = payload.get("mode")
    if isinstance(mode, str) and mode in {"strict", "fail-open"}:
        return mode
    return "fail-open"


def to_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            text = item.strip()
            if text not in result:
                result.append(text)
    return result


def summarize_outputs(actual_outputs: Any) -> Dict[str, Any]:
    if not isinstance(actual_outputs, dict):
        return {
            "failed_count": 0,
            "skipped_count": 0,
            "step_count": 0,
            "failed_steps": [],
        }
    step_summaries = actual_outputs.get("step_summaries")
    failed_steps: List[str] = []
    if isinstance(step_summaries, list):
        for item in step_summaries:
            if not isinstance(item, dict):
                continue
            if item.get("status") == "failed":
                step = item.get("step")
                if isinstance(step, str) and step not in failed_steps:
                    failed_steps.append(step)
    return {
        "failed_count": int(actual_outputs.get("failed_count", 0) or 0),
        "skipped_count": int(actual_outputs.get("skipped_count", 0) or 0),
        "step_count": len(step_summaries) if isinstance(step_summaries, list) else 0,
        "failed_steps": failed_steps,
    }


def build_summary(failed_step: Any, stop_reasons: List[str], suggested_next_action: Any) -> str:
    failed_step_name = "unknown"
    if isinstance(failed_step, dict):
        candidate = failed_step.get("step")
        if isinstance(candidate, str) and candidate.strip():
            failed_step_name = candidate.strip()
    branch_ids = []
    if isinstance(suggested_next_action, dict):
        branch_ids = to_str_list(suggested_next_action.get("branch_ids"))
    reasons_text = ", ".join(stop_reasons) if stop_reasons else "none"
    branches_text = ", ".join(branch_ids) if branch_ids else "none"
    return f"Escalation handoff draft. failed_step={failed_step_name}; stop_reasons={reasons_text}; branches={branches_text}."


def build_verifier_draft(
    summary: str,
    failed_step: Any,
    stop_reasons: List[str],
    executed_commands: Any,
    actual_outputs_summary: Dict[str, Any],
    suggested_next_action: Any,
) -> Dict[str, Any]:
    return {
        "target": "verifier",
        "title": "Verifier Read-Only Check Request",
        "summary": summary,
        "scope": "Read-only verification only. Do not apply fixes.",
        "failed_step": failed_step,
        "stop_reasons": stop_reasons,
        "executed_commands": executed_commands,
        "actual_outputs_summary": actual_outputs_summary,
        "suggested_next_action": suggested_next_action,
    }


def build_coordinator_draft(
    summary: str,
    failed_step: Any,
    stop_reasons: List[str],
    executed_commands: Any,
    actual_outputs_summary: Dict[str, Any],
    suggested_next_action: Any,
) -> Dict[str, Any]:
    return {
        "target": "coordinator",
        "title": "Coordinator Escalation Packet",
        "summary": summary,
        "scope": "Decide next implementation strategy and handoff sequencing.",
        "failed_step": failed_step,
        "stop_reasons": stop_reasons,
        "executed_commands": executed_commands,
        "actual_outputs_summary": actual_outputs_summary,
        "suggested_next_action": suggested_next_action,
    }


def write_markdown(path: Path, verifier: Dict[str, Any], coordinator: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Handoff Draft")
    lines.append("")
    lines.append("## Verifier")
    lines.append(f"- title: {verifier.get('title')}")
    lines.append(f"- summary: {verifier.get('summary')}")
    lines.append("")
    lines.append("## Coordinator")
    lines.append(f"- title: {coordinator.get('title')}")
    lines.append(f"- summary: {coordinator.get('summary')}")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Thin helper: build verifier/coordinator handoff draft from escalation draft JSON",
    )
    parser.add_argument("--escalation-draft-json", required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-markdown", default="")
    args = parser.parse_args()

    ok = True
    output: Dict[str, Any]
    try:
        source_path = Path(args.escalation_draft_json)
        if not source_path.exists():
            raise ValueError(f"escalation draft json not found: {args.escalation_draft_json}")
        source = parse_json_file(source_path)
        mode = pick_mode(source, args.strict)

        escalation_draft = source.get("escalation_draft")
        if not isinstance(escalation_draft, dict):
            raise ValueError("escalation_draft section is missing")

        required = bool(escalation_draft.get("required"))
        executed = bool(escalation_draft.get("executed"))

        if not required or not executed:
            output = {
                "ts": utc_now_iso(),
                "helper": "handoff_helper",
                "mode": mode,
                "ok": True,
                "input": {
                    "escalation_draft_json": str(source_path),
                },
                "handoff": {
                    "required": False,
                    "executed": False,
                    "skipped_reason": escalation_draft.get("skipped_reason") or "handoff_not_required",
                    "summary": "Escalation is not required, so handoff draft generation is skipped.",
                    "failed_step": escalation_draft.get("failed_step"),
                    "stop_reasons": to_str_list(escalation_draft.get("stop_reasons")),
                    "executed_commands": escalation_draft.get("executed_commands") or [],
                    "actual_outputs_summary": summarize_outputs(escalation_draft.get("actual_outputs")),
                    "suggested_next_action": escalation_draft.get("suggested_next_action") or {},
                    "verifier_draft": None,
                    "coordinator_draft": None,
                    "note": "Formatting only. No send, no retry, no runtime operations.",
                },
            }
        else:
            failed_step = escalation_draft.get("failed_step")
            stop_reasons = to_str_list(escalation_draft.get("stop_reasons"))
            executed_commands = escalation_draft.get("executed_commands") if isinstance(escalation_draft.get("executed_commands"), list) else []
            actual_outputs_summary = summarize_outputs(escalation_draft.get("actual_outputs"))
            suggested_next_action = escalation_draft.get("suggested_next_action") if isinstance(escalation_draft.get("suggested_next_action"), dict) else {}
            summary = build_summary(failed_step, stop_reasons, suggested_next_action)

            verifier_draft = build_verifier_draft(
                summary=summary,
                failed_step=failed_step,
                stop_reasons=stop_reasons,
                executed_commands=executed_commands,
                actual_outputs_summary=actual_outputs_summary,
                suggested_next_action=suggested_next_action,
            )
            coordinator_draft = build_coordinator_draft(
                summary=summary,
                failed_step=failed_step,
                stop_reasons=stop_reasons,
                executed_commands=executed_commands,
                actual_outputs_summary=actual_outputs_summary,
                suggested_next_action=suggested_next_action,
            )

            if args.output_markdown:
                write_markdown(Path(args.output_markdown), verifier_draft, coordinator_draft)

            output = {
                "ts": utc_now_iso(),
                "helper": "handoff_helper",
                "mode": mode,
                "ok": True,
                "input": {
                    "escalation_draft_json": str(source_path),
                },
                "handoff": {
                    "required": True,
                    "executed": True,
                    "summary": summary,
                    "failed_step": failed_step,
                    "stop_reasons": stop_reasons,
                    "executed_commands": executed_commands,
                    "actual_outputs_summary": actual_outputs_summary,
                    "suggested_next_action": suggested_next_action,
                    "verifier_draft": verifier_draft,
                    "coordinator_draft": coordinator_draft,
                    "note": "Formatting only. Final decisions remain with verifier/coordinator.",
                },
            }
    except Exception as error:
        ok = False
        output = {
            "ts": utc_now_iso(),
            "helper": "handoff_helper",
            "mode": "strict" if args.strict else "fail-open",
            "ok": False,
            "error": {
                "code": "HANDOFF_DRAFT_FAILED",
                "message": str(error),
            },
            "handoff": {
                "required": False,
                "executed": False,
                "summary": None,
                "failed_step": None,
                "stop_reasons": [],
                "executed_commands": [],
                "actual_outputs_summary": {
                    "failed_count": 0,
                    "skipped_count": 0,
                    "step_count": 0,
                    "failed_steps": [],
                },
                "suggested_next_action": {},
                "verifier_draft": None,
                "coordinator_draft": None,
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
