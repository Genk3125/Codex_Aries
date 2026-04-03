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


def estimate_tokens_from_text(text: str) -> int:
    return max(1, len(text) // 4)


def parse_json_file(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json object expected: {path}")
    return data


def to_unique_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    result: List[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def infer_status(orchestrator: Dict[str, Any], failed_step: Optional[str]) -> str:
    preflight = orchestrator.get("preflight_guard")
    if isinstance(preflight, dict) and preflight.get("decision") == "stop":
        return "stopped_preflight"
    guard = orchestrator.get("guard")
    if isinstance(guard, dict) and guard.get("decision") == "stop":
        return "stopped_post_run"
    if bool(orchestrator.get("ok")):
        return "ok"
    if failed_step:
        return "failed"
    return "partial"


def summarize_results(results: Dict[str, Any], max_commands: int = 10) -> Dict[str, Any]:
    executed_count = 0
    succeeded_count = 0
    failed_steps: List[str] = []
    skipped_steps: List[str] = []
    parse_error_steps: List[str] = []
    commands: List[Dict[str, str]] = []
    last_successful_step: Optional[str] = None
    failed_step_summary: Optional[Dict[str, Any]] = None

    for step_name, raw in results.items():
        if not isinstance(raw, dict):
            continue
        executed = bool(raw.get("executed"))
        ok = bool(raw.get("ok"))
        if executed:
            executed_count += 1
            if ok:
                succeeded_count += 1
                last_successful_step = step_name
            else:
                failed_steps.append(step_name)
                if failed_step_summary is None:
                    failed_step_summary = {
                        "step": step_name,
                        "exit_code": raw.get("exit_code"),
                        "detail": "helper_step_failed",
                    }
            command_raw = raw.get("command")
            if isinstance(command_raw, list) and all(isinstance(x, str) for x in command_raw):
                commands.append({"step": step_name, "command": " ".join(command_raw)})
            elif isinstance(command_raw, str) and command_raw.strip():
                commands.append({"step": step_name, "command": command_raw.strip()})
        else:
            skipped_steps.append(step_name)

        for key in ("parse_error_stdout", "parse_error_file", "parse_error"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                parse_error_steps.append(step_name)
                break

    shown_commands = commands[:max_commands]
    omitted = max(0, len(commands) - len(shown_commands))
    return {
        "last_successful_step": last_successful_step,
        "failed_step": failed_step_summary,
        "executed_commands_summary": {
            "count": len(commands),
            "items": shown_commands,
            "omitted_count": omitted,
        },
        "actual_outputs_summary": {
            "total_steps": len(results),
            "executed_steps": executed_count,
            "succeeded_steps": succeeded_count,
            "failed_steps": failed_steps,
            "skipped_steps": skipped_steps,
            "parse_error_steps": parse_error_steps,
        },
    }


def extract_ids(orchestrator: Dict[str, Any]) -> Dict[str, Optional[str]]:
    ids: Dict[str, Optional[str]] = {
        "team_id": None,
        "task_id": None,
        "member_id": None,
        "leader_id": None,
    }
    input_obj = orchestrator.get("input")
    if isinstance(input_obj, dict):
        member = input_obj.get("member_id")
        if isinstance(member, str) and member:
            ids["member_id"] = member

    results = orchestrator.get("results")
    if not isinstance(results, dict):
        return ids
    session = results.get("session_helper")
    if not isinstance(session, dict):
        return ids
    output = session.get("output")
    if not isinstance(output, dict):
        return ids
    raw_ids = output.get("ids")
    if not isinstance(raw_ids, dict):
        return ids
    for key in ids.keys():
        value = raw_ids.get(key)
        if isinstance(value, str) and value:
            ids[key] = value
    return ids


def collect_stop_reasons(orchestrator: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    preflight = orchestrator.get("preflight_guard")
    if isinstance(preflight, dict):
        for reason in to_unique_str_list(preflight.get("stop_reasons")):
            if reason not in reasons:
                reasons.append(reason)
    guard = orchestrator.get("guard")
    if isinstance(guard, dict):
        for reason in to_unique_str_list(guard.get("stop_reasons")):
            if reason not in reasons:
                reasons.append(reason)
    return reasons


def infer_next_action(orchestrator: Dict[str, Any], failed_step: Optional[Dict[str, Any]], stop_reasons: List[str]) -> Dict[str, Any]:
    guard = orchestrator.get("guard")
    if isinstance(guard, dict):
        hint = guard.get("next_action_hint")
        if isinstance(hint, str) and hint.strip():
            return {"type": "guard_hint", "hint": hint.strip(), "action_items": []}
    if "max_retries" in stop_reasons or "escalated" in stop_reasons:
        return {
            "type": "prepare_escalation",
            "hint": "Prepare escalation packet with commands, outputs, and next hypothesis.",
            "action_items": ["recovery_next_helper", "escalation_draft_helper", "handoff_helper"],
        }
    if failed_step:
        return {
            "type": "inspect_failure",
            "hint": "Inspect failed_step and collect minimal evidence before retry.",
            "action_items": ["check failed_step", "check stop_reasons", "decide strict or fail-open"],
        }
    return {
        "type": "proceed",
        "hint": "Run next task with current compact context.",
        "action_items": [],
    }


def read_latest_runs(runs_dir: Path, limit: int) -> List[Dict[str, Any]]:
    run_dirs = [path for path in runs_dir.glob("*") if path.is_dir() and (path / "orch.json").exists()]
    run_dirs.sort(key=lambda p: (p / "orch.json").stat().st_mtime, reverse=True)
    summaries: List[Dict[str, Any]] = []
    for run_dir in run_dirs[:limit]:
        orch_path = run_dir / "orch.json"
        try:
            orchestrator = parse_json_file(orch_path)
        except Exception:
            continue

        results = orchestrator.get("results")
        if not isinstance(results, dict):
            results = {}
        summarized = summarize_results(results)
        stop_reasons = collect_stop_reasons(orchestrator)
        current_status = infer_status(orchestrator, summarized.get("failed_step", {}).get("step") if isinstance(summarized.get("failed_step"), dict) else None)
        ids = extract_ids(orchestrator)
        next_action = infer_next_action(orchestrator, summarized.get("failed_step"), stop_reasons)

        artifact_candidates = [
            "orch.json",
            "compact.json",
            "compact.md",
            "context-compacted.json",
            "context-compacted.md",
            "recovery-next.json",
            "escalation-draft.json",
            "handoff.json",
            "handoff.md",
            "notify.json",
            "notify.txt",
        ]
        artifacts: Dict[str, str] = {}
        for filename in artifact_candidates:
            file_path = run_dir / filename
            if file_path.exists():
                artifacts[filename] = str(file_path)

        summaries.append(
            {
                "run_id": run_dir.name,
                "run_dir": str(run_dir),
                "orchestrator_json": str(orch_path),
                "compact_json": str(run_dir / "compact.json") if (run_dir / "compact.json").exists() else None,
                "current_status": current_status,
                "last_successful_step": summarized.get("last_successful_step"),
                "failed_step": summarized.get("failed_step"),
                "stop_reasons": stop_reasons,
                "next_action": next_action,
                "ids": ids,
                "executed_commands_summary": summarized.get("executed_commands_summary"),
                "actual_outputs_summary": summarized.get("actual_outputs_summary"),
                "artifacts": artifacts,
                "orch_size_bytes": orch_path.stat().st_size,
                "ts": orchestrator.get("ts"),
                "mode": orchestrator.get("mode"),
            }
        )
    return summaries


def prune_to_budget(output: Dict[str, Any], max_context_tokens: int) -> Dict[str, Any]:
    warnings: List[str] = []
    was_pruned = False
    while True:
        encoded = json.dumps(output, ensure_ascii=False)
        estimated = estimate_tokens_from_text(encoded)
        output["meta"]["estimated_tokens"] = estimated
        if estimated <= max_context_tokens:
            break

        was_pruned = True
        compact_state = output["compact_state"]
        commands = compact_state.get("executed_commands_summary", {}).get("items", [])
        evidence_runs = output.get("evidence_index", {}).get("runs", [])
        history = output.get("history", [])

        if isinstance(commands, list) and len(commands) > 3:
            commands.pop()
            continue
        if isinstance(evidence_runs, list) and len(evidence_runs) > 2:
            evidence_runs.pop()
            continue
        if isinstance(history, list) and len(history) > 2:
            history.pop()
            continue
        warnings.append("Context exceeded max token budget; no more optional fields can be pruned safely.")
        break

    if was_pruned:
        warnings.append("Compactor pruned optional evidence fields to fit token budget.")
    output["warnings"] = warnings
    output["meta"]["max_context_tokens"] = max_context_tokens
    output["meta"]["within_budget"] = output["meta"].get("estimated_tokens", 0) <= max_context_tokens
    return output


def render_markdown(output: Dict[str, Any]) -> str:
    compact = output.get("compact_state", {})
    evidence = output.get("evidence_index", {})
    lines: List[str] = []
    lines.append("# Context Compacted State")
    lines.append("")
    lines.append("## Current State")
    lines.append(f"- current_status: `{compact.get('current_status', 'unknown')}`")
    lines.append(f"- last_successful_step: `{compact.get('last_successful_step') or '(none)'}`")
    failed = compact.get("failed_step")
    if isinstance(failed, dict):
        lines.append(f"- failed_step: `{failed.get('step', 'unknown')}`")
    stop_reasons = compact.get("stop_reasons", [])
    if isinstance(stop_reasons, list) and stop_reasons:
        lines.append(f"- stop_reasons: {', '.join(stop_reasons)}")
    else:
        lines.append("- stop_reasons: none")
    lines.append("")
    lines.append("## Next Action")
    next_action = compact.get("next_action", {})
    lines.append(f"- type: `{next_action.get('type', 'unknown')}`")
    lines.append(f"- hint: {next_action.get('hint', '')}")
    items = next_action.get("action_items", [])
    if isinstance(items, list):
        for item in items:
            if isinstance(item, str) and item.strip():
                lines.append(f"  - {item}")
    lines.append("")
    lines.append("## IDs")
    ids = compact.get("ids", {})
    if isinstance(ids, dict):
        for key in ("team_id", "task_id", "member_id", "leader_id"):
            lines.append(f"- {key}: `{ids.get(key) or '(none)'}`")
    lines.append("")
    lines.append("## Evidence Index")
    runs = evidence.get("runs", [])
    if isinstance(runs, list) and runs:
        for item in runs:
            if not isinstance(item, dict):
                continue
            lines.append(f"- `{item.get('run_id', 'unknown')}` status=`{item.get('current_status', 'unknown')}` orch=`{item.get('orchestrator_json', '')}`")
    else:
        lines.append("- (no evidence runs)")
    lines.append("")
    meta = output.get("meta", {})
    lines.append("## Meta")
    lines.append(f"- estimated_tokens: {meta.get('estimated_tokens', 0)}")
    lines.append(f"- max_context_tokens: {meta.get('max_context_tokens', 0)}")
    lines.append(f"- within_budget: {meta.get('within_budget', False)}")
    warnings = output.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        lines.append("")
        lines.append("## Warnings")
        for warning in warnings:
            if isinstance(warning, str):
                lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact multiple run outputs into fixed minimal context state")
    parser.add_argument("--runs-dir", default="runs", help="Directory containing run folders")
    parser.add_argument("--max-context-tokens", type=int, default=4000, help="Token budget warning/prune threshold")
    parser.add_argument("--max-runs", type=int, default=12, help="How many latest runs to include in evidence index")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", default="")
    args = parser.parse_args()

    ok = True
    output: Dict[str, Any]
    try:
        runs_dir = Path(args.runs_dir)
        if not runs_dir.exists() or not runs_dir.is_dir():
            raise ValueError(f"runs dir not found: {runs_dir}")
        run_summaries = read_latest_runs(runs_dir=runs_dir, limit=max(1, args.max_runs))
        if not run_summaries:
            raise ValueError(f"no run directories with orch.json found under: {runs_dir}")

        latest = run_summaries[0]
        compact_state = {
            "current_status": latest["current_status"],
            "last_successful_step": latest["last_successful_step"],
            "failed_step": latest["failed_step"],
            "stop_reasons": latest["stop_reasons"],
            "executed_commands_summary": latest["executed_commands_summary"],
            "actual_outputs_summary": latest["actual_outputs_summary"],
            "next_action": latest["next_action"],
            "ids": latest["ids"],
        }
        evidence_runs = [
            {
                "run_id": item["run_id"],
                "current_status": item["current_status"],
                "failed_step": item["failed_step"],
                "stop_reasons": item["stop_reasons"],
                "orchestrator_json": item["orchestrator_json"],
                "artifacts": item["artifacts"],
                "orch_size_bytes": item["orch_size_bytes"],
            }
            for item in run_summaries
        ]

        output = {
            "ts": utc_now_iso(),
            "helper": "context_compactor",
            "ok": True,
            "input": {
                "runs_dir": str(runs_dir),
                "orchestrator_json": latest["orchestrator_json"],
                "latest_orchestrator_json": latest["orchestrator_json"],
                "latest_compact_json": latest["compact_json"],
            },
            "compact_state": compact_state,
            "evidence_index": {
                "run_count_included": len(evidence_runs),
                "runs": evidence_runs,
            },
            "history": [
                {
                    "run_id": item["run_id"],
                    "current_status": item["current_status"],
                    "last_successful_step": item["last_successful_step"],
                }
                for item in run_summaries
            ],
            "meta": {
                "schema_version": 1,
                "max_context_tokens": args.max_context_tokens,
                "estimated_tokens": 0,
                "within_budget": True,
            },
            "warnings": [],
        }
        output = prune_to_budget(output, max_context_tokens=max(100, args.max_context_tokens))
    except Exception as error:
        ok = False
        output = {
            "ts": utc_now_iso(),
            "helper": "context_compactor",
            "ok": False,
            "error": {"code": "CONTEXT_COMPACTION_FAILED", "message": str(error)},
            "compact_state": {
                "current_status": "unknown",
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
                "next_action": {"type": "inspect_failure", "hint": "Fix compactor input and rerun.", "action_items": []},
                "ids": {"team_id": None, "task_id": None, "member_id": None, "leader_id": None},
            },
            "evidence_index": {"run_count_included": 0, "runs": []},
            "history": [],
            "meta": {"schema_version": 1, "max_context_tokens": args.max_context_tokens, "estimated_tokens": 0, "within_budget": False},
            "warnings": [],
        }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    print(text)

    output_json_path = Path(args.output_json)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(text + "\n", encoding="utf-8")

    if args.output_markdown:
        markdown = render_markdown(output)
        output_md_path = Path(args.output_markdown)
        output_md_path.parent.mkdir(parents=True, exist_ok=True)
        output_md_path.write_text(markdown, encoding="utf-8")

    if args.strict and not ok:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
