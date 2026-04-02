#!/usr/bin/env python3
"""Thin notification helper: format guard stop_reasons as structured notifications.

This is a best-effort notification layer. All failures are swallowed (fail-open).
It does NOT send notifications to external services — it writes structured
text to stderr and optionally to a file.
"""
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


# --- Stop reason → notification mapping ---

REASON_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "manual_stop": {
        "severity": "high",
        "action_required": True,
        "message": "Manual stop detected — operator review required before resuming.",
        "suggested_next": "Review stop reason and decide: resume or keep stopped.",
    },
    "max_retries": {
        "severity": "high",
        "action_required": True,
        "message": "Maximum retries reached — escalation required.",
        "suggested_next": "Prepare escalation package with failure evidence.",
    },
    "strict_failure": {
        "severity": "high",
        "action_required": True,
        "message": "Strict mode failure — run halted, evidence needs fixation.",
        "suggested_next": "Fix evidence, run verifier read-only check, prepare minimal fix.",
    },
    "escalated": {
        "severity": "critical",
        "action_required": True,
        "message": "Consecutive failures triggered escalation.",
        "suggested_next": "Route to coordinator with hypothesis and evidence.",
    },
    "success": {
        "severity": "info",
        "action_required": False,
        "message": "Run completed successfully — closeout.",
        "suggested_next": "Record result, update baseline if needed.",
    },
    "already_stopped": {
        "severity": "medium",
        "action_required": True,
        "message": "Guard was already in stopped state from a previous run.",
        "suggested_next": "Review previous stop reason before clearing.",
    },
}

DEFAULT_TEMPLATE: Dict[str, Any] = {
    "severity": "medium",
    "action_required": True,
    "message": "Unknown stop reason detected.",
    "suggested_next": "Classify this reason and decide next action.",
}


def format_notification(
    guard_name: str,
    verdict: str,
    reason: str,
    ts: str,
) -> str:
    template = REASON_TEMPLATES.get(reason, DEFAULT_TEMPLATE)
    lines = [
        f"[NOTIFY][{guard_name}] {verdict}",
        f"  reason: {reason}",
        f"  severity: {template['severity']}",
        f"  timestamp: {ts}",
        f"  action_required: {'yes' if template['action_required'] else 'no'}",
        f"  message: {template['message']}",
        f"  suggested_next: {template['suggested_next']}",
    ]
    return "\n".join(lines)


def extract_notifications(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract guard results from orchestrator or compact_state JSON."""
    notifications: List[Dict[str, Any]] = []
    ts = source.get("ts") or utc_now_iso()

    # From orchestrator JSON
    for guard_key, guard_name in [
        ("preflight_guard", "preflight_guard"),
        ("guard", "post_run_guard"),
    ]:
        guard = source.get(guard_key)
        if not isinstance(guard, dict):
            continue
        decision = guard.get("decision")
        stop_reasons = guard.get("stop_reasons", [])
        if isinstance(stop_reasons, list) and stop_reasons:
            for reason in stop_reasons:
                if isinstance(reason, str) and reason.strip():
                    notifications.append({
                        "guard_name": guard_name,
                        "verdict": f"STOP ({decision})" if decision else "STOP",
                        "reason": reason.strip(),
                        "ts": ts,
                    })
        elif decision == "continue":
            # Only emit continue notification in verbose mode (handled by caller)
            pass

    # From compact_state JSON
    cs = source.get("compact_state")
    if isinstance(cs, dict):
        stop_reasons = cs.get("stop_reasons", [])
        status = cs.get("current_status", "")
        if isinstance(stop_reasons, list) and stop_reasons:
            for reason in stop_reasons:
                if isinstance(reason, str) and reason.strip():
                    notifications.append({
                        "guard_name": "compact_state",
                        "verdict": f"STOP ({status})",
                        "reason": reason.strip(),
                        "ts": ts,
                    })
        elif status.startswith("failed"):
            notifications.append({
                "guard_name": "compact_state",
                "verdict": f"FAILED ({status})",
                "reason": "helper_failure",
                "ts": ts,
            })

    return notifications


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Thin notification helper: format guard stop_reasons as structured stderr notifications",
    )
    parser.add_argument("--input-json", required=True, help="orchestrator or compact_state output json")
    parser.add_argument("--output-file", default="", help="optional file to write notifications to")
    parser.add_argument("--output-json", default="", help="output json with notification log")
    parser.add_argument("--verbose", action="store_true", help="also emit 'continue' notifications")
    args = parser.parse_args()

    notifications: List[Dict[str, Any]] = []
    formatted: List[str] = []
    ok = True

    try:
        source_path = Path(args.input_json)
        if not source_path.exists():
            raise ValueError(f"input json not found: {args.input_json}")
        source = parse_json_file(source_path)
        notifications = extract_notifications(source)

        for notif in notifications:
            text = format_notification(
                guard_name=notif["guard_name"],
                verdict=notif["verdict"],
                reason=notif["reason"],
                ts=notif["ts"],
            )
            formatted.append(text)
            # Always write to stderr (the primary notification channel)
            print(text, file=sys.stderr)

        if args.output_file:
            out_path = Path(args.output_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("\n\n".join(formatted) + "\n" if formatted else "(no notifications)\n", encoding="utf-8")

    except Exception as error:
        # fail-open: notification errors never stop the pipeline
        ok = False
        print(f"[NOTIFY][error] notification failed: {error}", file=sys.stderr)

    output = {
        "ts": utc_now_iso(),
        "helper": "notify_helper",
        "ok": ok,
        "notification_count": len(notifications),
        "notifications": notifications,
        "formatted_count": len(formatted),
        "note": "Best-effort notification only. Failures are swallowed.",
    }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")

    # Always exit 0 — fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
