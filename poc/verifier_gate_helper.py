#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
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


def resolve_task_id(source: Dict[str, Any], explicit_task_id: str) -> Tuple[Optional[str], Optional[str]]:
    return first_string(
        [
            ("--task-id", explicit_task_id),
            ("input.task_id", nested_get(source, ["input", "task_id"])),
            ("task_get.envelope.args.task_id", nested_get(source, ["task_get", "envelope", "args", "task_id"])),
            ("task_get.envelope.result.task_id", nested_get(source, ["task_get", "envelope", "result", "task_id"])),
            ("next.task_update_notify_example.task_id", nested_get(source, ["next", "task_update_notify_example", "task_id"])),
        ]
    )


def resolve_team_id(source: Dict[str, Any], explicit_team_id: str) -> Tuple[Optional[str], Optional[str]]:
    result_team_id = nested_get(source, ["message_list", "envelope", "result", "messages"])
    first_message_team_id = None
    if isinstance(result_team_id, list) and result_team_id:
        candidate = result_team_id[0]
        if isinstance(candidate, dict):
            first_message_team_id = candidate.get("team_id")
    return first_string(
        [
            ("--team-id", explicit_team_id),
            ("input.team_id", nested_get(source, ["input", "team_id"])),
            ("message_list.envelope.args.team_id", nested_get(source, ["message_list", "envelope", "args", "team_id"])),
            ("first_message.team_id", first_message_team_id),
            ("task_get.envelope.result.team_id", nested_get(source, ["task_get", "envelope", "result", "team_id"])),
            ("next.task_update_notify_example.team_id", nested_get(source, ["next", "task_update_notify_example", "team_id"])),
        ]
    )


def add_trigger(triggers: List[Dict[str, Any]], code: str, detail: str, severity: str = "medium") -> None:
    triggers.append(
        {
            "code": code,
            "severity": severity,
            "detail": detail,
        }
    )


def scan_message_delivery(source: Dict[str, Any]) -> Dict[str, Any]:
    messages = nested_get(source, ["message_list", "envelope", "result", "messages"])
    if not isinstance(messages, list):
        return {
            "messages_scanned": 0,
            "problematic_count": 0,
            "problematic": [],
        }

    problematic: List[Dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        message_id = str(message.get("message_id") or "")
        top_status = str(message.get("status") or "").lower()
        if top_status in {"failed", "pending"}:
            problematic.append(
                {
                    "message_id": message_id,
                    "scope": "message",
                    "state": top_status,
                    "recipient": None,
                }
            )
        delivery = message.get("delivery")
        if not isinstance(delivery, dict):
            continue
        for recipient_id, recipient_state in delivery.items():
            if not isinstance(recipient_state, dict):
                continue
            state = str(recipient_state.get("state") or "").lower()
            if state in {"failed", "pending"}:
                problematic.append(
                    {
                        "message_id": message_id,
                        "scope": "delivery",
                        "state": state,
                        "recipient": recipient_id,
                    }
                )
    return {
        "messages_scanned": len(messages),
        "problematic_count": len(problematic),
        "problematic": problematic,
    }


def build_gate_result(
    source: Dict[str, Any],
    resolved_task_id: Optional[str],
    task_id_source: Optional[str],
    resolved_team_id: Optional[str],
    team_id_source: Optional[str],
    expected_task_state: str,
) -> Dict[str, Any]:
    triggers: List[Dict[str, Any]] = []

    reconcile_ok = bool(nested_get(source, ["reconcile", "ok"]))
    task_get_ok = bool(nested_get(source, ["task_get", "ok"]))
    message_list_ok = bool(nested_get(source, ["message_list", "ok"]))
    observed_task_state = nested_get(source, ["task_get", "envelope", "result", "state"])

    if not reconcile_ok:
        add_trigger(triggers, "RECONCILE_FAILED", "reconcile step did not succeed", "high")
    if not task_get_ok:
        add_trigger(triggers, "TASK_GET_FAILED", "task_get step did not succeed", "high")
    if not message_list_ok:
        add_trigger(triggers, "MESSAGE_LIST_FAILED", "message_list step did not succeed", "high")

    if not resolved_task_id:
        add_trigger(triggers, "MISSING_TASK_ID", "task_id could not be resolved from input JSON or --task-id", "high")
    if not resolved_team_id:
        add_trigger(triggers, "MISSING_TEAM_ID", "team_id could not be resolved from input JSON or --team-id", "high")

    if expected_task_state:
        if not isinstance(observed_task_state, str) or not observed_task_state.strip():
            add_trigger(
                triggers,
                "TASK_STATE_UNAVAILABLE",
                "expected task state was provided but observed task state is unavailable",
                "medium",
            )
        elif observed_task_state != expected_task_state:
            add_trigger(
                triggers,
                "TASK_STATE_MISMATCH",
                f"expected state '{expected_task_state}' but observed '{observed_task_state}'",
                "medium",
            )

    message_scan = scan_message_delivery(source)
    if message_scan["problematic_count"] > 0:
        add_trigger(
            triggers,
            "MESSAGE_DELIVERY_PENDING_OR_FAILED",
            f"{message_scan['problematic_count']} message or recipient deliveries are pending/failed",
            "medium",
        )

    return {
        "ts": utc_now_iso(),
        "requires_verifier": len(triggers) > 0,
        "trigger_count": len(triggers),
        "trigger_codes": [item["code"] for item in triggers],
        "triggers": triggers,
        "checks": {
            "reconcile_ok": reconcile_ok,
            "task_get_ok": task_get_ok,
            "message_list_ok": message_list_ok,
            "message_scan": message_scan,
            "expected_task_state": expected_task_state or None,
            "observed_task_state": observed_task_state if isinstance(observed_task_state, str) else None,
            "task_id": resolved_task_id,
            "task_id_source": task_id_source,
            "team_id": resolved_team_id,
            "team_id_source": team_id_source,
        },
        "note": "Gate result is only a trigger decision. Final PASS/PARTIAL/FAIL must come from verifier.",
    }


def extract_verdict(text: str) -> Optional[str]:
    match = re.search(r"\b(PASS|PARTIAL|FAIL)\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).upper()


def run_verifier(
    verifier_cmd: str,
    payload: Dict[str, Any],
    strict: bool,
    env: Dict[str, str],
    timeout_sec: int,
) -> Dict[str, Any]:
    cmd = shlex.split(verifier_cmd)
    if not cmd:
        return {
            "executed": False,
            "error": {"code": "EMPTY_VERIFIER_CMD", "message": "verifier command is empty"},
        }

    payload_text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        process = subprocess.run(
            cmd,
            input=payload_text,
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "executed": True,
            "command": cmd,
            "exit_code": None,
            "reported_verdict": None,
            "stdout": (error.stdout or "").strip() if isinstance(error.stdout, str) else "",
            "stderr": (error.stderr or "").strip() if isinstance(error.stderr, str) else "",
            "parsed_json": None,
            "ok": False,
            "error": {
                "code": "VERIFIER_TIMEOUT",
                "message": f"verifier command timed out after {timeout_sec}s",
            },
        }
    stdout_text = (process.stdout or "").strip()
    stderr_text = (process.stderr or "").strip()
    parsed_json = None
    if stdout_text:
        try:
            parsed = json.loads(stdout_text)
            if isinstance(parsed, dict):
                parsed_json = parsed
        except json.JSONDecodeError:
            parsed_json = None
    combined_text = "\n".join([part for part in [stdout_text, stderr_text] if part]).strip()
    reported_verdict = extract_verdict(combined_text)

    result = {
        "executed": True,
        "command": cmd,
        "exit_code": process.returncode,
        "reported_verdict": reported_verdict,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "parsed_json": parsed_json,
    }

    # Exit code convention: 0=PASS, 1=FAIL, 2=PARTIAL, 3+=UNKNOWN
    if process.returncode == 0:
        result["ok"] = True
        result["exit_code_meaning"] = "PASS"
    elif process.returncode == 1:
        result["ok"] = False
        result["exit_code_meaning"] = "FAIL"
    elif process.returncode == 2:
        # PARTIAL: ok in fail-open, not ok in strict
        result["ok"] = not strict
        result["exit_code_meaning"] = "PARTIAL"
    else:
        # 3+ = verifier itself is broken
        result["ok"] = False
        result["exit_code_meaning"] = "UNKNOWN (verifier error)"

    # reported_verdict override: if strict and verdict says PARTIAL/FAIL, force not ok
    if strict and reported_verdict in {"PARTIAL", "FAIL"}:
        result["ok"] = False
    return result


def build_verifier_next(
    gate_result: Dict[str, Any],
    source_input_path: str,
    verifier_contract_path: str,
) -> Dict[str, Any]:
    trigger_codes = gate_result.get("trigger_codes", [])
    return {
        "required": bool(gate_result.get("requires_verifier")),
        "reason_codes": trigger_codes,
        "input_json": source_input_path or None,
        "verifier_contract": verifier_contract_path,
        "hint": "Run verifier with the gate triggers as context and return contract-formatted PASS/PARTIAL/FAIL.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Thin verifier gate helper: checks post-step output and conditionally runs verifier",
    )
    parser.add_argument("--input-json", required=True, help="post_step_check_helper output json")
    parser.add_argument("--task-id", default="", help="explicit task_id override")
    parser.add_argument("--team-id", default="", help="explicit team_id override")
    parser.add_argument("--expected-task-state", default="", help="optional expected task state for mismatch check")
    parser.add_argument(
        "--verifier-cmd",
        default=os.environ.get("CODEX_VERIFIER_GATE_CMD", ""),
        help="optional verifier command; when omitted, helper emits verifier_next only",
    )
    parser.add_argument("--verifier-timeout-sec", type=int, default=180, help="timeout for verifier command")
    parser.add_argument(
        "--verifier-contract-path",
        default=str(REPO_ROOT / "verifier-contract.md"),
        help="verifier contract reference",
    )
    parser.add_argument(
        "--computer-use-evidence-json",
        default="",
        help="optional computer_use_helper output json path; forwarded to verifier env",
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    if not input_path.exists():
        raise SystemExit(f"input json not found: {args.input_json}")
    source = parse_json_file(input_path)

    resolved_task_id, task_id_source = resolve_task_id(source, args.task_id)
    resolved_team_id, team_id_source = resolve_team_id(source, args.team_id)
    gate_result = build_gate_result(
        source=source,
        resolved_task_id=resolved_task_id,
        task_id_source=task_id_source,
        resolved_team_id=resolved_team_id,
        team_id_source=team_id_source,
        expected_task_state=args.expected_task_state,
    )

    verifier_result: Optional[Dict[str, Any]] = None
    verifier_next: Optional[Dict[str, Any]] = None

    if gate_result["requires_verifier"]:
        if args.verifier_cmd:
            verifier_payload = {
                "ts": utc_now_iso(),
                "source_helper": str(source.get("helper") or "unknown"),
                "source_input_json": args.input_json,
                "task_id": resolved_task_id,
                "team_id": resolved_team_id,
                "expected_task_state": args.expected_task_state or None,
                "gate_result": gate_result,
                "verifier_contract_path": args.verifier_contract_path,
                "computer_use_evidence_json": args.computer_use_evidence_json or None,
            }
            verifier_env = os.environ.copy()
            verifier_env["VERIFIER_GATE_MODE"] = "strict" if args.strict else "fail-open"
            verifier_env["VERIFIER_GATE_STRICT"] = "1" if args.strict else "0"
            verifier_env["VERIFIER_GATE_INPUT_JSON"] = args.input_json
            verifier_env["VERIFIER_GATE_TASK_ID"] = resolved_task_id or ""
            verifier_env["VERIFIER_GATE_TEAM_ID"] = resolved_team_id or ""
            verifier_env["VERIFIER_GATE_TRIGGER_CODES"] = json.dumps(gate_result["trigger_codes"], ensure_ascii=False)
            verifier_env["VERIFIER_GATE_COMPUTER_USE_EVIDENCE_JSON"] = args.computer_use_evidence_json or ""
            verifier_result = run_verifier(
                verifier_cmd=args.verifier_cmd,
                payload=verifier_payload,
                strict=args.strict,
                env=verifier_env,
                timeout_sec=args.verifier_timeout_sec,
            )
        else:
            verifier_next = build_verifier_next(
                gate_result=gate_result,
                source_input_path=args.input_json,
                verifier_contract_path=args.verifier_contract_path,
            )
    else:
        verifier_next = {
            "required": False,
            "reason_codes": [],
            "input_json": args.input_json,
            "hint": "No gate trigger was detected. Verifier run is optional.",
        }

    if verifier_result is not None:
        helper_ok = bool(verifier_result.get("ok"))
    else:
        helper_ok = not gate_result["requires_verifier"]

    output: Dict[str, Any] = {
        "ts": utc_now_iso(),
        "helper": "verifier_gate_helper",
        "mode": "strict" if args.strict else "fail-open",
        "ok": helper_ok,
        "input": {
            "input_json": args.input_json,
            "task_id": resolved_task_id,
            "task_id_source": task_id_source,
            "team_id": resolved_team_id,
            "team_id_source": team_id_source,
            "expected_task_state": args.expected_task_state or None,
            "verifier_cmd": args.verifier_cmd or None,
            "computer_use_evidence_json": args.computer_use_evidence_json or None,
        },
        "gate_result": gate_result,
    }
    if verifier_result is not None:
        output["verifier_result"] = verifier_result
    if verifier_next is not None:
        output["verifier_next"] = verifier_next

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
