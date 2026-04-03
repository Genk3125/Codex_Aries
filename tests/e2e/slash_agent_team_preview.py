#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = REPO_ROOT / "poc" / "slash_command_adapter.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_payload(temp_dir: str, payload: dict[str, object]) -> Path:
    input_path = Path(temp_dir) / "input.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return input_path


def run_adapter(argv: list[str]) -> tuple[int, dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(ADAPTER_PATH), *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    output = json.loads(proc.stdout or "{}")
    if not isinstance(output, dict):
        raise AssertionError("adapter output must be JSON object")
    return proc.returncode, output


def base_payload(team_name: str) -> dict[str, object]:
    return {
        "team_name": team_name,
        "objective": "slash adapter preview-first test",
        "main_agent": {
            "agent_id": "main-coordinator",
            "role": "brain/coordinator",
            "model_preset": "quality",
            "reasoning_preset": "high",
            "initial_prompt": "Coordinate and synthesize.",
        },
        "sub_agents": [
            {
                "agent_id": "worker-impl",
                "role": "implementation",
                "model_preset": "fast",
                "reasoning_preset": "medium",
                "initial_prompt": "Implement change.",
            }
        ],
        "initial_task": {
            "title": "Slash apply demo task",
            "state": "ready",
            "owner": "main",
        },
        "initial_messages": [
            {
                "to_member_id": "worker-impl",
                "text": "Kick off delegated implementation.",
            }
        ],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="slash-agent-team-preview-") as temp_dir:
        temp_root = Path(temp_dir)
        store_root = temp_root / "runtime"

        # 1) preview is default (no --apply)
        preview_input = write_payload(temp_dir, base_payload("slash-preview-default"))
        preview_code, preview_output = run_adapter(
            ["/agent_team", "--input-file", str(preview_input)]
        )
        assert_true(preview_code == 0, "preview default run must exit 0")
        assert_true(preview_output.get("ok") is True, "preview default should be ok=true")
        assert_true(preview_output.get("mode") == "preview", "mode should default to preview")
        parse_stage = ((preview_output.get("stages") or {}).get("parse") or {})
        assert_true(parse_stage.get("preview_default_applied") is True, "preview default flag should be true")
        result = preview_output.get("result", {})
        assert_true(isinstance(result, dict), "preview result must be object")
        assert_true(result.get("command_name") == "agent_team", "command_name should be agent_team")
        delegate_output = result.get("delegate_output", {})
        assert_true(isinstance(delegate_output, dict) and delegate_output.get("mode") == "plan", "preview must delegate to plan mode")
        assert_true(delegate_output.get("ok") is True, "delegated plan must be ok=true")

        # 2) apply runs only when explicitly requested
        apply_input = write_payload(temp_dir, base_payload("slash-apply-explicit"))
        apply_code, apply_output = run_adapter(
            [
                "/agent_team",
                "--apply",
                "--input-file",
                str(apply_input),
                "--store-root",
                str(store_root),
                "--idempotency-prefix",
                "slash-preview-test",
            ]
        )
        assert_true(apply_code == 0, "explicit apply should succeed in fail-open mode")
        assert_true(apply_output.get("mode") == "apply", "mode should be apply when --apply is used")
        apply_result = apply_output.get("result", {})
        assert_true(isinstance(apply_result, dict), "apply result wrapper should be object")
        delegated_apply = apply_result.get("delegate_output", {})
        assert_true(isinstance(delegated_apply, dict), "delegated apply output should be object")
        assert_true(delegated_apply.get("mode") == "apply", "delegated mode should be apply")
        assert_true(delegated_apply.get("ok") is True, "delegated apply should be ok=true")
        inner_apply = delegated_apply.get("apply_result", {})
        assert_true(isinstance(inner_apply, dict), "apply_result should exist")
        assert_true(inner_apply.get("idempotency_prefix") == "slash-preview-test", "idempotency prefix should be propagated")
        assert_true(inner_apply.get("store_root") == str(store_root), "store_root should be propagated")
        counts = inner_apply.get("operation_counts", {})
        assert_true(isinstance(counts, dict) and counts.get("executed", 0) >= 3, "apply should execute runtime operations")

        # 3) validation failure
        invalid_input = write_payload(temp_dir, {"team_name": "invalid-no-main"})
        invalid_code, invalid_output = run_adapter(
            ["/agent_team", "--input-file", str(invalid_input)]
        )
        assert_true(invalid_code == 2, "invalid payload should fail")
        assert_true(invalid_output.get("ok") is False, "invalid payload must return ok=false")
        error = invalid_output.get("error", {})
        assert_true(isinstance(error, dict) and error.get("code") == "VALIDATION_ERROR", "error code should be VALIDATION_ERROR")

    print(
        json.dumps(
            {
                "ok": True,
                "checks": [
                    "preview_default_mode",
                    "apply_explicit_mode",
                    "delegate_apply_passthrough",
                    "validation_failure",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
