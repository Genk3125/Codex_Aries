#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ALLOWED_STOP_CONDITIONS = {
    "success",
    "max_retries",
    "strict_failure",
    "manual_stop",
    "escalated",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_stop_conditions(text: str) -> List[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    conditions = []
    for raw in text.split(","):
        item = raw.strip()
        if not item:
            continue
        if item not in ALLOWED_STOP_CONDITIONS:
            allowed = ", ".join(sorted(ALLOWED_STOP_CONDITIONS))
            raise ValueError(f"unknown stop_condition: {item} (allowed: {allowed})")
        if item not in conditions:
            conditions.append(item)
    return conditions


def default_state() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "attempt_count": 0,
        "consecutive_failures": 0,
        "manual_stop": False,
        "last_ok": None,
        "last_decision": None,
        "last_reasons": [],
        "updated_at": None,
    }


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return default_state()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("loop guard state must be a JSON object")
    state = default_state()
    state.update(data)
    return state


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def evaluate_guard(
    run_ok: bool,
    strict: bool,
    state: Dict[str, Any],
    max_retries: int,
    escalate_after_n: int,
    stop_conditions: List[str],
    recovery_playbook_path: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    previous_attempt = int(state.get("attempt_count", 0) or 0)
    previous_failures = int(state.get("consecutive_failures", 0) or 0)
    manual_stop = bool(state.get("manual_stop", False))

    attempt_count = previous_attempt + 1
    consecutive_failures = 0 if run_ok else previous_failures + 1
    escalation_triggered = (not run_ok) and consecutive_failures >= escalate_after_n

    stop_reasons: List[str] = []
    if manual_stop and "manual_stop" in stop_conditions:
        stop_reasons.append("manual_stop")
    if run_ok and "success" in stop_conditions:
        stop_reasons.append("success")
    if strict and (not run_ok) and "strict_failure" in stop_conditions:
        stop_reasons.append("strict_failure")
    if attempt_count >= max_retries and "max_retries" in stop_conditions:
        stop_reasons.append("max_retries")
    if escalation_triggered and "escalated" in stop_conditions:
        stop_reasons.append("escalated")

    if stop_reasons:
        decision = "stop"
    elif escalation_triggered:
        decision = "escalate"
    else:
        decision = "continue"

    if decision == "continue":
        next_action = "Continue only with a new run request; no automatic retry is performed."
    elif decision == "escalate":
        next_action = "Escalate per recovery-playbook section 3.3 with evidence attached."
    else:
        next_action = "Stop the sequence and require operator review before next run."

    guard_result = {
        "enabled": True,
        "ts": utc_now_iso(),
        "decision": decision,
        "attempt_count": attempt_count,
        "consecutive_failures": consecutive_failures,
        "max_retries": max_retries,
        "escalate_after_n": escalate_after_n,
        "escalation_triggered": escalation_triggered,
        "stop_condition": stop_conditions,
        "stop_reasons": stop_reasons,
        "strict_mode": strict,
        "run_ok": run_ok,
        "recovery_playbook_ref": recovery_playbook_path,
        "note": "Guard only decides continue/stop/escalate. It does not run retries or implement fixes.",
        "next_action_hint": next_action,
    }

    next_state = dict(state)
    next_state.update(
        {
            "schema_version": 1,
            "attempt_count": attempt_count,
            "consecutive_failures": consecutive_failures,
            "last_ok": run_ok,
            "last_decision": decision,
            "last_reasons": stop_reasons,
            "updated_at": utc_now_iso(),
        }
    )
    return guard_result, next_state


def evaluate_preflight_guard(
    strict: bool,
    state: Dict[str, Any],
    max_retries: int,
    stop_conditions: List[str],
    recovery_playbook_path: str,
) -> Dict[str, Any]:
    attempt_count = int(state.get("attempt_count", 0) or 0)
    manual_stop = bool(state.get("manual_stop", False))
    last_decision = str(state.get("last_decision") or "")

    stop_reasons: List[str] = []
    if manual_stop and "manual_stop" in stop_conditions:
        stop_reasons.append("manual_stop")
    if attempt_count >= max_retries and "max_retries" in stop_conditions:
        stop_reasons.append("max_retries")
    if last_decision == "stop":
        stop_reasons.append("already_stopped")

    decision = "stop" if stop_reasons else "allow"
    if decision == "allow":
        next_action = "Run is allowed to start; post-run guard will evaluate outcome."
    else:
        next_action = "Run must not start; operator review is required before retry."

    return {
        "enabled": True,
        "ts": utc_now_iso(),
        "decision": decision,
        "attempt_count": attempt_count,
        "max_retries": max_retries,
        "stop_condition": stop_conditions,
        "stop_reasons": stop_reasons,
        "strict_mode": strict,
        "state_last_decision": last_decision or None,
        "recovery_playbook_ref": recovery_playbook_path,
        "note": "Preflight guard decides run start eligibility only.",
        "next_action_hint": next_action,
    }
