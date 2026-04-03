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
from typing import Any, Dict, List, Optional

from loop_guard import (
    evaluate_guard,
    evaluate_preflight_guard,
    load_state,
    parse_stop_conditions,
    save_state,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_step_output_path(work_dir: Path, step_name: str) -> Path:
    return work_dir / f"{step_name}.json"


def parse_json_text(text: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    stripped = text.strip()
    if not stripped:
        return None, "empty helper output"
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as error:
        return None, f"invalid helper JSON output: {error}"
    if not isinstance(parsed, dict):
        return None, "helper output is not a JSON object"
    return parsed, None


def build_cmd(
    python_cmd: str,
    script_path: str,
    strict: bool,
    store_root: str,
    args: List[str],
) -> List[str]:
    cmd = [python_cmd, script_path]
    if strict:
        cmd.append("--strict")
    if store_root:
        cmd.extend(["--store-root", store_root])
    cmd.extend(args)
    return cmd


def run_helper_step(
    step_name: str,
    cmd: List[str],
    expected_output_json: Path,
) -> Dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=os.environ.copy())
    stdout_text = (proc.stdout or "").strip()
    stderr_text = (proc.stderr or "").strip()

    parsed_from_stdout, parse_error = parse_json_text(stdout_text)
    parsed_from_file = None
    file_error = None
    if expected_output_json.exists():
        try:
            raw = expected_output_json.read_text(encoding="utf-8")
            parsed_from_file, file_error = parse_json_text(raw)
        except Exception as error:
            file_error = f"failed reading output file: {error}"

    output_obj = parsed_from_file or parsed_from_stdout
    operation_ok = None
    if isinstance(output_obj, dict):
        operation_ok = bool(output_obj.get("ok"))
    step_ok = proc.returncode == 0 and output_obj is not None and operation_ok is True

    return {
        "executed": True,
        "step": step_name,
        "command": cmd,
        "exit_code": proc.returncode,
        "ok": step_ok,
        "operation_ok": operation_ok,
        "output_json_path": str(expected_output_json),
        "parse_error_stdout": parse_error,
        "parse_error_file": file_error,
        "stderr": stderr_text,
        "output": output_obj,
    }


def skipped_step(step_name: str, reason: str) -> Dict[str, Any]:
    return {
        "executed": False,
        "step": step_name,
        "ok": True,
        "skipped_reason": reason,
    }


def all_orchestrator_steps() -> List[str]:
    return [
        "session_helper",
        "task_update_notify_helper",
        "post_step_check_helper",
        "computer_use_helper",
        "verifier_gate_helper",
        "bridge_helper",
        "loopback_helper",
        "chain_helper",
    ]


def pick_task_id(results: Dict[str, Dict[str, Any]]) -> Optional[str]:
    session_output = (results.get("session_helper") or {}).get("output")
    if isinstance(session_output, dict):
        ids = session_output.get("ids")
        if isinstance(ids, dict):
            task_id = ids.get("task_id")
            if isinstance(task_id, str) and task_id:
                return task_id
    return None


def pick_team_id(results: Dict[str, Dict[str, Any]]) -> Optional[str]:
    session_output = (results.get("session_helper") or {}).get("output")
    if isinstance(session_output, dict):
        ids = session_output.get("ids")
        if isinstance(ids, dict):
            team_id = ids.get("team_id")
            if isinstance(team_id, str) and team_id:
                return team_id
    return None


def pick_from_member_id(results: Dict[str, Dict[str, Any]]) -> Optional[str]:
    session_output = (results.get("session_helper") or {}).get("output")
    if isinstance(session_output, dict):
        ids = session_output.get("ids")
        if isinstance(ids, dict):
            leader_id = ids.get("leader_id")
            if isinstance(leader_id, str) and leader_id:
                return leader_id
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-shot thin orchestrator: run existing helpers once in sequence",
    )
    parser.add_argument("--team-name", required=True)
    parser.add_argument("--member-id", required=True)
    parser.add_argument("--task-title", required=True)
    parser.add_argument("--bootstrap-message", required=True)
    parser.add_argument("--notify-member-id", default="")
    parser.add_argument("--task-update-state", default="in_progress")
    parser.add_argument("--task-update-message", default="task moved to in_progress")
    parser.add_argument("--task-update-result-reference", default="")
    parser.add_argument("--task-update-blocked-reason", default="")
    parser.add_argument("--gate-expected-task-state", default="")
    parser.add_argument("--bridge-message", default="verifier gate triggered; task moved to blocked")
    parser.add_argument("--computer-use-url", default="")
    parser.add_argument(
        "--computer-use-operation",
        choices=["screenshot", "extract_text", "both"],
        default="both",
    )
    parser.add_argument("--computer-use-timeout-sec", type=int, default=20)
    parser.add_argument("--computer-use-timeout-ms", type=int, default=15000)
    parser.add_argument("--computer-use-output-dir", default="")
    parser.add_argument("--computer-use-screenshot-path", default="")
    parser.add_argument("--flow-mode", choices=["gate", "chain"], default="chain")
    parser.add_argument("--verifier-cmd", default="")
    parser.add_argument("--verifier-timeout-sec", type=int, default=180)
    parser.add_argument("--verifier-contract-path", default=str(REPO_ROOT / "verifier-contract.md"))
    parser.add_argument("--team-idempotency-key", default="")
    parser.add_argument("--member-add-idempotency-key", default="")
    parser.add_argument("--task-idempotency-key", default="")
    parser.add_argument("--message-idempotency-key", default="")
    parser.add_argument("--task-update-idempotency-key", default="")
    parser.add_argument("--task-update-message-idempotency-key", default="")
    parser.add_argument("--bridge-task-idempotency-key", default="")
    parser.add_argument("--bridge-message-idempotency-key", default="")
    parser.add_argument(
        "--python-cmd",
        default=os.environ.get("CODEX_ORCHESTRATOR_PYTHON_CMD", "python3"),
    )
    parser.add_argument("--store-root", default="")
    parser.add_argument("--work-dir", default="")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--guard-state-json", default="", help="enable loop guard and persist thin state to this JSON path")
    parser.add_argument("--guard-max-retries", type=int, default=3)
    parser.add_argument("--guard-escalate-after-n", type=int, default=2)
    parser.add_argument(
        "--guard-stop-condition",
        default="max_retries,strict_failure,manual_stop,escalated",
        help="comma-separated stop conditions: success,max_retries,strict_failure,manual_stop,escalated",
    )
    parser.add_argument(
        "--recovery-playbook-path",
        default=str(REPO_ROOT / "docs" / "recovery-playbook.md"),
    )
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    script_paths = {
        "session_helper": os.environ.get("CODEX_ORCH_SESSION_SCRIPT", str(REPO_ROOT / "poc" / "session_helper.py")),
        "task_update_notify_helper": os.environ.get("CODEX_ORCH_TASK_UPDATE_NOTIFY_SCRIPT", str(REPO_ROOT / "poc" / "task_update_notify_helper.py")),
        "post_step_check_helper": os.environ.get("CODEX_ORCH_POST_CHECK_SCRIPT", str(REPO_ROOT / "poc" / "post_step_check_helper.py")),
        "computer_use_helper": os.environ.get("CODEX_ORCH_COMPUTER_USE_SCRIPT", str(REPO_ROOT / "poc" / "computer_use_helper.py")),
        "verifier_gate_helper": os.environ.get("CODEX_ORCH_VERIFIER_GATE_SCRIPT", str(REPO_ROOT / "poc" / "verifier_gate_helper.py")),
        "bridge_helper": os.environ.get("CODEX_ORCH_BRIDGE_SCRIPT", str(REPO_ROOT / "poc" / "bridge_helper.py")),
        "loopback_helper": os.environ.get("CODEX_ORCH_LOOPBACK_SCRIPT", str(REPO_ROOT / "poc" / "loopback_helper.py")),
        "chain_helper": os.environ.get("CODEX_ORCH_CHAIN_SCRIPT", str(REPO_ROOT / "poc" / "chain_helper.py")),
    }

    work_dir_path = Path(args.work_dir) if args.work_dir else Path(tempfile.mkdtemp(prefix="one-shot-orchestrator-"))
    work_dir_path.mkdir(parents=True, exist_ok=True)

    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    notify_member_id = args.notify_member_id or args.member_id
    results: Dict[str, Dict[str, Any]] = {}

    guard_enabled = bool(args.guard_state_json)
    guard_ok = True
    guard_init_ok = True
    preflight_blocks_run = False
    preflight_error_message = ""
    guard_state: Dict[str, Any] = {}
    guard_state_path: Optional[Path] = Path(args.guard_state_json) if guard_enabled else None
    max_retries = max(1, int(args.guard_max_retries))
    escalate_after_n = max(1, int(args.guard_escalate_after_n))
    stop_conditions: List[str] = []

    if guard_enabled:
        try:
            stop_conditions = parse_stop_conditions(args.guard_stop_condition)
            if guard_state_path is None:
                raise ValueError("guard state path is required")
            guard_state = load_state(guard_state_path)
            preflight_guard_result = evaluate_preflight_guard(
                strict=args.strict,
                state=guard_state,
                max_retries=max_retries,
                stop_conditions=stop_conditions,
                recovery_playbook_path=args.recovery_playbook_path,
            )
            preflight_guard_result["state_path"] = str(guard_state_path)
            preflight_guard_result["ok"] = True
            preflight_blocks_run = preflight_guard_result.get("decision") == "stop"
        except Exception as error:
            guard_init_ok = False
            guard_ok = False
            preflight_error_message = str(error)
            preflight_guard_result = {
                "enabled": True,
                "ok": False,
                "decision": "guard_error",
                "error": {
                    "code": "PREFLIGHT_GUARD_FAILED",
                    "message": preflight_error_message,
                },
                "note": "Preflight guard error is fatal only in strict mode.",
                "state_path": args.guard_state_json,
            }
            preflight_blocks_run = bool(args.strict)
    else:
        preflight_guard_result = {
            "enabled": False,
            "ok": True,
            "decision": "disabled",
            "note": "Preflight guard is disabled. Set --guard-state-json to enable it.",
        }

    if preflight_blocks_run:
        skip_reason = "preflight_guard_stop"
        if preflight_guard_result.get("decision") == "guard_error":
            skip_reason = "preflight_guard_error_strict"
        for step_name in all_orchestrator_steps():
            results[step_name] = skipped_step(step_name, skip_reason)
    else:
        session_output_path = make_step_output_path(work_dir_path, "01-session-helper")
        session_cmd = build_cmd(
            python_cmd=args.python_cmd,
            script_path=script_paths["session_helper"],
            strict=args.strict,
            store_root=args.store_root,
            args=[
                "--team-name",
                args.team_name,
                "--member-id",
                args.member_id,
                "--task-title",
                args.task_title,
                "--message-text",
                args.bootstrap_message,
                "--output-json",
                str(session_output_path),
            ],
        )
        if args.team_idempotency_key:
            session_cmd.extend(["--team-idempotency-key", args.team_idempotency_key])
        if args.member_add_idempotency_key:
            session_cmd.extend(["--member-add-idempotency-key", args.member_add_idempotency_key])
        if args.task_idempotency_key:
            session_cmd.extend(["--task-idempotency-key", args.task_idempotency_key])
        if args.message_idempotency_key:
            session_cmd.extend(["--message-idempotency-key", args.message_idempotency_key])
        results["session_helper"] = run_helper_step("session_helper", session_cmd, session_output_path)

        task_update_output_path = make_step_output_path(work_dir_path, "02-task-update-notify-helper")
        task_update_cmd = build_cmd(
            python_cmd=args.python_cmd,
            script_path=script_paths["task_update_notify_helper"],
            strict=args.strict,
            store_root=args.store_root,
            args=[
                "--input-json",
                str(session_output_path),
                "--state",
                args.task_update_state,
                "--to-member-id",
                notify_member_id,
                "--message-text",
                args.task_update_message,
                "--output-json",
                str(task_update_output_path),
            ],
        )
        if args.task_update_result_reference:
            task_update_cmd.extend(["--result-reference", args.task_update_result_reference])
        if args.task_update_blocked_reason:
            task_update_cmd.extend(["--blocked-reason", args.task_update_blocked_reason])
        if args.task_update_idempotency_key:
            task_update_cmd.extend(["--task-idempotency-key", args.task_update_idempotency_key])
        if args.task_update_message_idempotency_key:
            task_update_cmd.extend(["--message-idempotency-key", args.task_update_message_idempotency_key])
        results["task_update_notify_helper"] = run_helper_step("task_update_notify_helper", task_update_cmd, task_update_output_path)

        post_check_output_path = make_step_output_path(work_dir_path, "03-post-step-check-helper")
        post_check_cmd = build_cmd(
            python_cmd=args.python_cmd,
            script_path=script_paths["post_step_check_helper"],
            strict=args.strict,
            store_root=args.store_root,
            args=[
                "--input-json",
                str(task_update_output_path),
                "--output-json",
                str(post_check_output_path),
            ],
        )
        results["post_step_check_helper"] = run_helper_step("post_step_check_helper", post_check_cmd, post_check_output_path)

        computer_use_output_path = make_step_output_path(work_dir_path, "04-computer-use-helper")
        computer_use_evidence_json = ""
        if args.computer_use_url:
            computer_use_output_dir = args.computer_use_output_dir or str(work_dir_path / "computer-use")
            computer_use_cmd = [args.python_cmd, script_paths["computer_use_helper"]]
            if args.strict:
                computer_use_cmd.append("--strict")
            computer_use_cmd.extend(
                [
                    "--url",
                    args.computer_use_url,
                    "--operation",
                    args.computer_use_operation,
                    "--timeout-sec",
                    str(args.computer_use_timeout_sec),
                    "--timeout-ms",
                    str(args.computer_use_timeout_ms),
                    "--output-dir",
                    computer_use_output_dir,
                    "--output-json",
                    str(computer_use_output_path),
                ]
            )
            if args.computer_use_screenshot_path:
                computer_use_cmd.extend(["--screenshot-path", args.computer_use_screenshot_path])
            results["computer_use_helper"] = run_helper_step("computer_use_helper", computer_use_cmd, computer_use_output_path)
            if computer_use_output_path.exists():
                computer_use_evidence_json = str(computer_use_output_path)
        else:
            results["computer_use_helper"] = skipped_step("computer_use_helper", "computer_use_url_not_set")
            computer_use_evidence_json = ""

        task_id = pick_task_id(results)
        team_id = pick_team_id(results)
        from_member_id = pick_from_member_id(results)

        verifier_gate_output_path = make_step_output_path(work_dir_path, "05-verifier-gate-helper")
        verifier_gate_cmd = [args.python_cmd, script_paths["verifier_gate_helper"]]
        if args.strict:
            verifier_gate_cmd.append("--strict")
        verifier_gate_cmd.extend(["--input-json", str(post_check_output_path), "--output-json", str(verifier_gate_output_path)])
        if task_id:
            verifier_gate_cmd.extend(["--task-id", task_id])
        if team_id:
            verifier_gate_cmd.extend(["--team-id", team_id])
        if computer_use_evidence_json:
            verifier_gate_cmd.extend(["--computer-use-evidence-json", computer_use_evidence_json])
        if args.verifier_cmd:
            verifier_gate_cmd.extend(["--verifier-cmd", args.verifier_cmd])
        if args.gate_expected_task_state:
            verifier_gate_cmd.extend(["--expected-task-state", args.gate_expected_task_state])
        verifier_gate_cmd.extend(["--verifier-timeout-sec", str(args.verifier_timeout_sec), "--verifier-contract-path", args.verifier_contract_path])
        results["verifier_gate_helper"] = run_helper_step("verifier_gate_helper", verifier_gate_cmd, verifier_gate_output_path)

        if args.flow_mode == "gate":
            results["bridge_helper"] = skipped_step("bridge_helper", "flow_mode_gate")
            results["loopback_helper"] = skipped_step("loopback_helper", "flow_mode_gate")
            results["chain_helper"] = skipped_step("chain_helper", "flow_mode_gate")
        else:
            bridge_output_path = make_step_output_path(work_dir_path, "06-bridge-helper")
            bridge_cmd = build_cmd(
                python_cmd=args.python_cmd,
                script_path=script_paths["bridge_helper"],
                strict=args.strict,
                store_root=args.store_root,
                args=[
                    "--input-json",
                    str(verifier_gate_output_path),
                    "--to-member-id",
                    notify_member_id,
                    "--message-text",
                    args.bridge_message,
                    "--output-json",
                    str(bridge_output_path),
                ],
            )
            if from_member_id:
                bridge_cmd.extend(["--from-member-id", from_member_id])
            if args.bridge_task_idempotency_key:
                bridge_cmd.extend(["--task-idempotency-key", args.bridge_task_idempotency_key])
            if args.bridge_message_idempotency_key:
                bridge_cmd.extend(["--message-idempotency-key", args.bridge_message_idempotency_key])
            results["bridge_helper"] = run_helper_step("bridge_helper", bridge_cmd, bridge_output_path)

            loopback_output_path = make_step_output_path(work_dir_path, "07-loopback-helper")
            loopback_cmd = build_cmd(
                python_cmd=args.python_cmd,
                script_path=script_paths["loopback_helper"],
                strict=args.strict,
                store_root=args.store_root,
                args=[
                    "--input-json",
                    str(bridge_output_path),
                    "--output-json",
                    str(loopback_output_path),
                ],
            )
            results["loopback_helper"] = run_helper_step("loopback_helper", loopback_cmd, loopback_output_path)

            chain_output_path = make_step_output_path(work_dir_path, "08-chain-helper")
            chain_cmd = [args.python_cmd, script_paths["chain_helper"]]
            if args.strict:
                chain_cmd.append("--strict")
            chain_cmd.extend(["--input-json", str(loopback_output_path), "--output-json", str(chain_output_path)])
            if task_id:
                chain_cmd.extend(["--task-id", task_id])
            if team_id:
                chain_cmd.extend(["--team-id", team_id])
            if computer_use_evidence_json:
                chain_cmd.extend(["--computer-use-evidence-json", computer_use_evidence_json])
            if args.verifier_cmd:
                chain_cmd.extend(["--verifier-cmd", args.verifier_cmd])
            if args.gate_expected_task_state:
                chain_cmd.extend(["--expected-task-state", args.gate_expected_task_state])
            chain_cmd.extend(["--verifier-timeout-sec", str(args.verifier_timeout_sec), "--verifier-contract-path", args.verifier_contract_path])
            results["chain_helper"] = run_helper_step("chain_helper", chain_cmd, chain_output_path)

    final_ok = (not preflight_blocks_run) and all(bool((step or {}).get("ok")) for step in results.values())

    guard_result: Dict[str, Any]
    if guard_enabled and preflight_blocks_run:
        if preflight_guard_result.get("decision") == "guard_error":
            guard_result = {
                "enabled": True,
                "ok": False,
                "decision": "not_executed_preflight_error",
                "error": {
                    "code": "PREFLIGHT_GUARD_FAILED",
                    "message": preflight_error_message,
                },
                "note": "Post-run guard is skipped because preflight guard failed in strict mode.",
                "state_path": args.guard_state_json,
            }
        else:
            guard_result = {
                "enabled": True,
                "ok": True,
                "decision": "not_executed",
                "reason": "preflight_stopped_run",
                "note": "Post-run guard is skipped because preflight guard stopped this run.",
                "state_path": str(guard_state_path) if guard_state_path else args.guard_state_json,
            }
    elif guard_enabled and guard_init_ok:
        try:
            guard_result, next_guard_state = evaluate_guard(
                run_ok=final_ok,
                strict=args.strict,
                state=guard_state,
                max_retries=max_retries,
                escalate_after_n=escalate_after_n,
                stop_conditions=stop_conditions,
                recovery_playbook_path=args.recovery_playbook_path,
            )
            if guard_state_path is None:
                raise ValueError("guard state path is required")
            save_state(guard_state_path, next_guard_state)
            guard_result["state_path"] = str(guard_state_path)
            guard_result["ok"] = True
        except Exception as error:
            guard_ok = False
            guard_result = {
                "enabled": True,
                "ok": False,
                "decision": "guard_error",
                "error": {
                    "code": "GUARD_EVALUATION_FAILED",
                    "message": str(error),
                },
                "note": "Guard failure does not run retries; strict mode returns non-zero.",
                "state_path": args.guard_state_json,
            }
    elif guard_enabled:
        guard_result = {
            "enabled": True,
            "ok": False,
            "decision": "not_executed_preflight_error",
            "error": {
                "code": "PREFLIGHT_GUARD_FAILED",
                "message": preflight_error_message or "unknown preflight guard error",
            },
            "note": "Post-run guard is skipped because preflight guard could not be initialized.",
            "state_path": args.guard_state_json,
        }
    else:
        guard_result = {
            "enabled": False,
            "ok": True,
            "decision": "disabled",
            "note": "Loop guard is disabled. Set --guard-state-json to enable thin attempt tracking.",
        }

    final_ok_with_guard = final_ok and guard_ok
    output = {
        "ts": utc_now_iso(),
        "helper": "one_shot_orchestrator",
        "mode": "strict" if args.strict else "fail-open",
        "flow_mode": args.flow_mode,
        "ok": final_ok_with_guard,
        "single_pass": True,
        "run_id": run_ts,
        "input": {
            "team_name": args.team_name,
            "member_id": args.member_id,
            "notify_member_id": notify_member_id,
            "task_title": args.task_title,
            "task_update_state": args.task_update_state,
            "gate_expected_task_state": args.gate_expected_task_state or None,
            "computer_use_url": args.computer_use_url or None,
            "computer_use_operation": args.computer_use_operation if args.computer_use_url else None,
            "verifier_cmd": args.verifier_cmd or None,
            "store_root": args.store_root or None,
        },
        "paths": {
            "work_dir": str(work_dir_path),
        },
        "preflight_guard": preflight_guard_result,
        "results": results,
        "guard": guard_result,
        "notes": {
            "orchestrator_scope": "wires existing helpers only",
            "looping": "single pass only; no recursion/retry/auto-loop",
            "preflight_guard_scope": "run start eligibility decision only",
            "guard_scope": "stop/continue/escalate decision only; no auto-retry",
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
