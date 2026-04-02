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

    # --- Verifier Section ---
    lines.append("---")
    lines.append("")
    lines.append("## Verifier: Read-Only Check Request")
    lines.append("")

    # 1) Verification Result
    lines.append("### Verification Result")
    failed_step = verifier.get("failed_step")
    stop_reasons = verifier.get("stop_reasons", [])
    if failed_step and isinstance(failed_step, dict):
        step_name = failed_step.get("step", "unknown")
        lines.append(f"PARTIAL")
        lines.append(f"Escalation triggered at `{step_name}`. stop_reasons: {', '.join(stop_reasons) if stop_reasons else 'none'}.")
    else:
        lines.append("PARTIAL")
        lines.append(f"Escalation handoff generated. stop_reasons: {', '.join(stop_reasons) if stop_reasons else 'none'}.")
    lines.append("")

    # 2) Executed Commands
    lines.append("### Executed Commands")
    executed_commands = verifier.get("executed_commands", [])
    if executed_commands and isinstance(executed_commands, list):
        for cmd in executed_commands:
            if isinstance(cmd, dict):
                lines.append(f"- command: `{cmd.get('command', 'N/A')}`")
                lines.append(f"  cwd: `{cmd.get('cwd', 'N/A')}`")
                lines.append(f"  exit_code: `{cmd.get('exit_code', 'N/A')}`")
                lines.append(f"  purpose: `{cmd.get('purpose', 'N/A')}`")
            elif isinstance(cmd, str):
                lines.append(f"- command: `{cmd}`")
    else:
        lines.append("None (commands not captured in escalation draft)")
    lines.append("")

    # 3) Actual Output (Evidence)
    lines.append("### Actual Output (Evidence)")
    outputs_summary = verifier.get("actual_outputs_summary", {})
    if outputs_summary and isinstance(outputs_summary, dict):
        failed_count = outputs_summary.get("failed_count", 0)
        step_count = outputs_summary.get("step_count", 0)
        skipped_count = outputs_summary.get("skipped_count", 0)
        failed_steps_list = outputs_summary.get("failed_steps", [])
        lines.append(f"- total_steps: {step_count}")
        lines.append(f"- failed_count: {failed_count}")
        lines.append(f"- skipped_count: {skipped_count}")
        if failed_steps_list:
            lines.append(f"- failed_steps: {', '.join(f'`{s}`' for s in failed_steps_list)}")
    else:
        lines.append("None (output summary not available)")
    lines.append("")

    # 4) Unverified Items
    lines.append("### Unverified Items")
    lines.append("- item: `full runtime reconcile`")
    lines.append("  reason: `escalation path — verifier has not run independent check yet`")
    lines.append("  what_is_needed_to_verify: `verifier runs read-only checks against runtime state`")
    lines.append("")

    # 5) Residual Risks
    lines.append("### Residual Risks")
    if stop_reasons:
        for reason in stop_reasons:
            lines.append(f"- `{reason}` (severity: Medium)")
    else:
        lines.append("None")
    lines.append("")

    # 6) Next Actions
    lines.append("### Next Actions")
    suggested = verifier.get("suggested_next_action", {})
    if isinstance(suggested, dict):
        action_items = suggested.get("action_items", [])
        branch_ids = suggested.get("branch_ids", [])
        if action_items and isinstance(action_items, list):
            for i, item in enumerate(action_items, 1):
                lines.append(f"{i}. {item}")
        elif branch_ids and isinstance(branch_ids, list):
            for i, bid in enumerate(branch_ids, 1):
                lines.append(f"{i}. Follow branch: `{bid}`")
        else:
            lines.append("1. Run verifier read-only check")
            lines.append("2. Report PASS/PARTIAL/FAIL to coordinator")
    else:
        lines.append("1. Run verifier read-only check")
        lines.append("2. Report PASS/PARTIAL/FAIL to coordinator")
    lines.append("")

    # --- Coordinator Section ---
    lines.append("---")
    lines.append("")
    lines.append("## Coordinator: Escalation Packet")
    lines.append("")
    lines.append(f"- **summary**: {coordinator.get('summary', 'N/A')}")
    lines.append(f"- **scope**: {coordinator.get('scope', 'N/A')}")
    if failed_step and isinstance(failed_step, dict):
        lines.append(f"- **failed_step**: `{failed_step.get('step', 'unknown')}`")
    lines.append(f"- **stop_reasons**: {', '.join(stop_reasons) if stop_reasons else 'none'}")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Thin helper: build verifier/coordinator handoff draft from escalation draft JSON",
    )
    parser.add_argument("--escalation-draft-json", default="")
    parser.add_argument("--from-compact", default="", help="compact_state_helper output json; synthesizes escalation draft from compact state")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-markdown", default="")
    args = parser.parse_args()

    ok = True
    output: Dict[str, Any]
    try:
        # Resolve input: --from-compact synthesizes escalation_draft from compact state
        if args.from_compact:
            compact_path = Path(args.from_compact)
            if not compact_path.exists():
                raise ValueError(f"compact json not found: {args.from_compact}")
            compact = parse_json_file(compact_path)
            cs = compact.get("compact_state", {})
            # Synthesize an escalation_draft from compact_state fields
            source = {
                "mode": compact.get("mode", "fail-open"),
                "escalation_draft": {
                    "required": cs.get("current_status", "").startswith("failed") or bool(cs.get("stop_reasons")),
                    "executed": True,
                    "failed_step": cs.get("failed_step"),
                    "stop_reasons": cs.get("stop_reasons", []),
                    "executed_commands": cs.get("executed_commands_summary", {}).get("items", []),
                    "actual_outputs": {
                        "step_summaries": [
                            {"step": s, "status": "failed"}
                            for s in cs.get("actual_outputs_summary", {}).get("failed_steps", [])
                        ],
                        "failed_count": len(cs.get("actual_outputs_summary", {}).get("failed_steps", [])),
                        "skipped_count": len(cs.get("actual_outputs_summary", {}).get("skipped_steps", [])),
                    },
                    "suggested_next_action": {
                        "action_items": cs.get("next_action", {}).get("action_items", []),
                    },
                },
            }
            source_path = compact_path
        elif args.escalation_draft_json:
            source_path = Path(args.escalation_draft_json)
            if not source_path.exists():
                raise ValueError(f"escalation draft json not found: {args.escalation_draft_json}")
            source = parse_json_file(source_path)
        else:
            raise ValueError("either --escalation-draft-json or --from-compact is required")
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
