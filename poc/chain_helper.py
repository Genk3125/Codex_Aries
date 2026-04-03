#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
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
            ("post_check_result.post_step_check_output.input.task_id", nested_get(source, ["post_check_result", "post_step_check_output", "input", "task_id"])),
            ("bridge_result.task_update_notify_output.input.task_id", nested_get(source, ["bridge_result", "task_update_notify_output", "input", "task_id"])),
            ("bridge_result.task_update_notify_output.task_update.envelope.result.task_id", nested_get(source, ["bridge_result", "task_update_notify_output", "task_update", "envelope", "result", "task_id"])),
            ("bridge_result.task_update_notify_output.task_update.envelope.args.task_id", nested_get(source, ["bridge_result", "task_update_notify_output", "task_update", "envelope", "args", "task_id"])),
            ("gate_result.checks.task_id", nested_get(source, ["gate_result", "checks", "task_id"])),
        ]
    )


def resolve_team_id(source: Dict[str, Any], explicit_team_id: str) -> Tuple[Optional[str], Optional[str]]:
    return first_string(
        [
            ("--team-id", explicit_team_id),
            ("input.team_id", nested_get(source, ["input", "team_id"])),
            ("post_check_result.post_step_check_output.input.team_id", nested_get(source, ["post_check_result", "post_step_check_output", "input", "team_id"])),
            ("bridge_result.task_update_notify_output.input.team_id", nested_get(source, ["bridge_result", "task_update_notify_output", "input", "team_id"])),
            ("bridge_result.task_update_notify_output.task_update.envelope.result.team_id", nested_get(source, ["bridge_result", "task_update_notify_output", "task_update", "envelope", "result", "team_id"])),
            ("bridge_result.task_update_notify_output.task_update.envelope.args.team_id", nested_get(source, ["bridge_result", "task_update_notify_output", "task_update", "envelope", "args", "team_id"])),
            ("gate_result.checks.team_id", nested_get(source, ["gate_result", "checks", "team_id"])),
        ]
    )


def build_fallback_post_check_payload(
    task_id: Optional[str],
    team_id: Optional[str],
    post_check_result: Dict[str, Any],
) -> Dict[str, Any]:
    skipped_reason = post_check_result.get("skipped_reason")
    parse_error = post_check_result.get("parse_error")
    detail_parts = []
    if isinstance(skipped_reason, str) and skipped_reason:
        detail_parts.append(f"skipped_reason={skipped_reason}")
    if isinstance(parse_error, str) and parse_error:
        detail_parts.append(f"parse_error={parse_error}")
    detail_text = "; ".join(detail_parts) if detail_parts else "post_check_result.ok=false without structured post-check output"

    return {
        "ts": utc_now_iso(),
        "helper": "post_step_check_helper",
        "mode": "fail-open",
        "ok": False,
        "input": {
            "input_json": None,
            "task_id": task_id,
            "task_id_source": "chain_helper_fallback",
            "team_id": team_id,
            "team_id_source": "chain_helper_fallback",
        },
        "reconcile": {
            "executed": False,
            "ok": False,
            "skipped_reason": "chain_helper_fallback_from_loopback_failure",
            "detail": detail_text,
        },
        "task_get": {
            "executed": False,
            "ok": False,
            "skipped_reason": "chain_helper_fallback_from_loopback_failure",
            "detail": detail_text,
        },
        "message_list": {
            "executed": False,
            "ok": False,
            "skipped_reason": "chain_helper_fallback_from_loopback_failure",
            "detail": detail_text,
        },
    }


def write_temp_json(payload: Dict[str, Any]) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".json", prefix="chain-helper-post-check-", delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        return handle.name


def run_verifier_gate(
    python_cmd: str,
    script_path: str,
    strict: bool,
    gate_input_json: str,
    task_id: Optional[str],
    team_id: Optional[str],
    verifier_cmd: str,
    expected_task_state: str,
    verifier_timeout_sec: int,
    verifier_contract_path: str,
    computer_use_evidence_json: str,
) -> Dict[str, Any]:
    cmd: List[str] = [python_cmd, script_path]
    if strict:
        cmd.append("--strict")
    cmd.extend(["--input-json", gate_input_json])
    if task_id:
        cmd.extend(["--task-id", task_id])
    if team_id:
        cmd.extend(["--team-id", team_id])
    if verifier_cmd:
        cmd.extend(["--verifier-cmd", verifier_cmd])
    if expected_task_state:
        cmd.extend(["--expected-task-state", expected_task_state])
    if verifier_timeout_sec > 0:
        cmd.extend(["--verifier-timeout-sec", str(verifier_timeout_sec)])
    if verifier_contract_path:
        cmd.extend(["--verifier-contract-path", verifier_contract_path])
    if computer_use_evidence_json:
        cmd.extend(["--computer-use-evidence-json", computer_use_evidence_json])

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
                parse_error = "verifier_gate_helper output is not a JSON object"
        except json.JSONDecodeError as error:
            parse_error = f"invalid verifier_gate_helper JSON output: {error}"
    else:
        parse_error = "empty verifier_gate_helper output"

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
        "verifier_gate_output": parsed,
        "stdout": text,
        "stderr": (proc.stderr or "").strip(),
        "ok": helper_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chain helper: run verifier_gate_helper only when loopback post-check looks suspicious",
    )
    parser.add_argument("--input-json", required=True, help="loopback_helper output json")
    parser.add_argument("--task-id", default="", help="explicit task_id override")
    parser.add_argument("--team-id", default="", help="explicit team_id override")
    parser.add_argument(
        "--python-cmd",
        default=os.environ.get("CODEX_CHAIN_PYTHON_CMD", "python3"),
        help="python executable for calling verifier_gate_helper",
    )
    parser.add_argument(
        "--verifier-gate-script",
        default=os.environ.get(
            "CODEX_CHAIN_VERIFIER_GATE_SCRIPT",
            str(REPO_ROOT / "poc" / "verifier_gate_helper.py"),
        ),
        help="verifier_gate_helper script path",
    )
    parser.add_argument("--verifier-cmd", default="", help="optional verifier command passthrough")
    parser.add_argument("--expected-task-state", default="", help="optional expected task state passthrough")
    parser.add_argument("--verifier-timeout-sec", type=int, default=180)
    parser.add_argument(
        "--verifier-contract-path",
        default=str(REPO_ROOT / "verifier-contract.md"),
    )
    parser.add_argument(
        "--computer-use-evidence-json",
        default="",
        help="optional computer_use_helper output json path passed through to verifier_gate_helper",
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    if not input_path.exists():
        raise SystemExit(f"input json not found: {args.input_json}")
    source = parse_json_file(input_path)

    post_check_result = source.get("post_check_result")
    if not isinstance(post_check_result, dict):
        post_check_result = {}

    post_executed = bool(post_check_result.get("executed"))
    post_ok = bool(post_check_result.get("ok"))

    task_id, task_id_source = resolve_task_id(source, args.task_id)
    team_id, team_id_source = resolve_team_id(source, args.team_id)

    verifier_gate_result: Dict[str, Any]
    gate_input_json_path: Optional[str] = None

    if not post_executed:
        verifier_gate_result = {
            "executed": False,
            "skipped_reason": "post_check_not_executed",
            "ok": True,
        }
    elif post_ok:
        verifier_gate_result = {
            "executed": False,
            "skipped_reason": "post_check_ok",
            "ok": True,
        }
    else:
        post_check_output = nested_get(source, ["post_check_result", "post_step_check_output"])
        if not isinstance(post_check_output, dict):
            post_check_output = build_fallback_post_check_payload(task_id=task_id, team_id=team_id, post_check_result=post_check_result)
        gate_input_json_path = write_temp_json(post_check_output)
        verifier_gate_result = run_verifier_gate(
            python_cmd=args.python_cmd,
            script_path=args.verifier_gate_script,
            strict=args.strict,
            gate_input_json=gate_input_json_path,
            task_id=task_id,
            team_id=team_id,
            verifier_cmd=args.verifier_cmd,
            expected_task_state=args.expected_task_state,
            verifier_timeout_sec=args.verifier_timeout_sec,
            verifier_contract_path=args.verifier_contract_path,
            computer_use_evidence_json=args.computer_use_evidence_json,
        )

    helper_ok = bool(verifier_gate_result.get("ok"))
    output = {
        "ts": utc_now_iso(),
        "helper": "chain_helper",
        "mode": "strict" if args.strict else "fail-open",
        "ok": helper_ok,
        "input": {
            "input_json": args.input_json,
            "task_id": task_id,
            "task_id_source": task_id_source,
            "team_id": team_id,
            "team_id_source": team_id_source,
            "verifier_gate_script": args.verifier_gate_script,
            "verifier_cmd": args.verifier_cmd or None,
            "expected_task_state": args.expected_task_state or None,
            "computer_use_evidence_json": args.computer_use_evidence_json or None,
        },
        "loopback_result": source,
        "verifier_gate_result": verifier_gate_result,
        "tmp": {
            "gate_input_json": gate_input_json_path,
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
