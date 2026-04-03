#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_PRESETS: Dict[str, Dict[str, Dict[str, str]]] = {
    "model_presets": {
        "quality": {
            "description": "High-quality planning and coordination",
            "intended_use": "main",
        },
        "balanced": {
            "description": "Balanced quality and speed",
            "intended_use": "main_or_sub",
        },
        "fast": {
            "description": "Fast delegated execution",
            "intended_use": "sub",
        },
    },
    "reasoning_presets": {
        "low": {
            "description": "Fast response with light reasoning",
            "intended_use": "sub",
        },
        "medium": {
            "description": "Default balanced reasoning",
            "intended_use": "main_or_sub",
        },
        "high": {
            "description": "Deep reasoning for complex tasks",
            "intended_use": "main_or_sub",
        },
        "xhigh": {
            "description": "Maximum reasoning depth",
            "intended_use": "main",
        },
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_runtime_cmd() -> str:
    env_value = os.environ.get("CODEX_RUNTIME_HELPER_RUNTIME_CMD", "")
    if env_value.strip():
        return env_value.strip()
    runtime_adapter_path = Path(__file__).resolve().with_name("codex_runtime_adapter.py")
    return f"{sys.executable} {runtime_adapter_path}"


def parse_json_object(text: str, source_name: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{source_name} is not valid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise ValueError(f"{source_name} must be a JSON object")
    return parsed


def load_input_json(input_json: str, input_file: str) -> Dict[str, Any]:
    if bool(input_json) == bool(input_file):
        raise ValueError("Specify exactly one of --input-json or --input-file")
    if input_json:
        return parse_json_object(input_json, "--input-json")
    file_path = Path(input_file)
    if not file_path.exists():
        raise ValueError(f"input file not found: {input_file}")
    return parse_json_object(file_path.read_text(encoding="utf-8"), "--input-file")


def load_presets(presets_file: str) -> Dict[str, Dict[str, Dict[str, str]]]:
    if not presets_file:
        return DEFAULT_PRESETS
    file_path = Path(presets_file)
    if not file_path.exists():
        return DEFAULT_PRESETS
    loaded = parse_json_object(file_path.read_text(encoding="utf-8"), "--presets-file")
    model_presets = loaded.get("model_presets")
    reasoning_presets = loaded.get("reasoning_presets")
    if not isinstance(model_presets, dict) or not model_presets:
        raise ValueError("--presets-file must include non-empty model_presets object")
    if not isinstance(reasoning_presets, dict) or not reasoning_presets:
        raise ValueError("--presets-file must include non-empty reasoning_presets object")
    return loaded  # type: ignore[return-value]


def require_non_empty_string(data: Dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def normalize_optional_string(raw: Any, context: str) -> Optional[str]:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{context} must be a string when provided")
    value = raw.strip()
    return value or None


def normalize_agent(
    raw: Any,
    context: str,
    allowed_model_presets: Dict[str, Any],
    allowed_reasoning_presets: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{context} must be an object")
    agent_id = require_non_empty_string(raw, "agent_id", context)
    role = require_non_empty_string(raw, "role", context)
    model_preset = require_non_empty_string(raw, "model_preset", context)
    reasoning_preset = require_non_empty_string(raw, "reasoning_preset", context)
    initial_prompt = raw.get("initial_prompt", "")
    if initial_prompt is None:
        initial_prompt = ""
    if not isinstance(initial_prompt, str):
        raise ValueError(f"{context}.initial_prompt must be a string")
    if model_preset not in allowed_model_presets:
        allowed = ", ".join(sorted(allowed_model_presets.keys()))
        raise ValueError(f"{context}.model_preset '{model_preset}' is not allowed ({allowed})")
    if reasoning_preset not in allowed_reasoning_presets:
        allowed = ", ".join(sorted(allowed_reasoning_presets.keys()))
        raise ValueError(f"{context}.reasoning_preset '{reasoning_preset}' is not allowed ({allowed})")
    return {
        "agent_id": agent_id,
        "role": role,
        "model_preset": model_preset,
        "reasoning_preset": reasoning_preset,
        "initial_prompt": initial_prompt.strip(),
    }


def normalize_initial_task(
    raw_task: Any,
    team_name: str,
    main_agent_id: str,
    sub_agent_ids: List[str],
) -> Dict[str, Any]:
    raw = raw_task if isinstance(raw_task, dict) else {}
    title = raw.get("title", f"Kickoff for {team_name}")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("initial_task.title must be a non-empty string when provided")
    state = raw.get("state", "ready")
    if not isinstance(state, str) or not state.strip():
        raise ValueError("initial_task.state must be a non-empty string when provided")
    owner = raw.get("owner", "main")
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("initial_task.owner must be a non-empty string when provided")
    owner = owner.strip()
    if owner == "main":
        owner_member_id = main_agent_id
    elif owner in sub_agent_ids:
        owner_member_id = owner
    else:
        valid = ", ".join(["main"] + sub_agent_ids)
        raise ValueError(f"initial_task.owner must be one of: {valid}")
    blocked_reason = normalize_optional_string(raw.get("blocked_reason"), "initial_task.blocked_reason")
    result_reference = normalize_optional_string(raw.get("result_reference"), "initial_task.result_reference")
    return {
        "title": title.strip(),
        "state": state.strip(),
        "owner": owner,
        "owner_member_id": owner_member_id,
        "blocked_reason": blocked_reason,
        "result_reference": result_reference,
    }


def normalize_initial_messages(
    raw_messages: Any,
    main_agent_id: str,
    sub_agents: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    sub_ids = {sub["agent_id"] for sub in sub_agents}
    if raw_messages is None:
        raw_messages = []
    if raw_messages and not isinstance(raw_messages, list):
        raise ValueError("initial_messages must be an array when provided")
    if not raw_messages:
        templates: List[Dict[str, Any]] = []
        for sub in sub_agents:
            templates.append(
                {
                    "from_member_id": main_agent_id,
                    "to_member_id": sub["agent_id"],
                    "text": f"[{sub['role']}] delegated task kickoff",
                }
            )
        return templates

    templates = []
    for index, message in enumerate(raw_messages):
        context = f"initial_messages[{index}]"
        if not isinstance(message, dict):
            raise ValueError(f"{context} must be an object")
        to_member_id = require_non_empty_string(message, "to_member_id", context)
        text = require_non_empty_string(message, "text", context)
        from_member_id = message.get("from_member_id", main_agent_id)
        if not isinstance(from_member_id, str) or not from_member_id.strip():
            raise ValueError(f"{context}.from_member_id must be a non-empty string when provided")
        if to_member_id not in sub_ids:
            raise ValueError(f"{context}.to_member_id must reference an existing sub agent")
        templates.append(
            {
                "from_member_id": from_member_id.strip(),
                "to_member_id": to_member_id,
                "text": text,
            }
        )
    return templates


def normalize_spec(
    raw_spec: Dict[str, Any],
    presets: Dict[str, Dict[str, Dict[str, str]]],
) -> Dict[str, Any]:
    team_name = require_non_empty_string(raw_spec, "team_name", "root")
    objective = raw_spec.get("objective", "")
    if objective is None:
        objective = ""
    if not isinstance(objective, str):
        raise ValueError("root.objective must be a string when provided")

    model_presets = presets.get("model_presets", {})
    reasoning_presets = presets.get("reasoning_presets", {})

    main_agent = normalize_agent(
        raw_spec.get("main_agent"),
        "main_agent",
        model_presets,
        reasoning_presets,
    )
    sub_agents_raw = raw_spec.get("sub_agents", [])
    if sub_agents_raw is None:
        sub_agents_raw = []
    if not isinstance(sub_agents_raw, list):
        raise ValueError("sub_agents must be an array")
    sub_agents = [
        normalize_agent(item, f"sub_agents[{index}]", model_presets, reasoning_presets)
        for index, item in enumerate(sub_agents_raw)
    ]

    agent_ids = [main_agent["agent_id"]] + [sub["agent_id"] for sub in sub_agents]
    if len(agent_ids) != len(set(agent_ids)):
        raise ValueError("agent_id values must be unique across main_agent and sub_agents")

    initial_task_provided = "initial_task" in raw_spec
    initial_messages_provided = "initial_messages" in raw_spec
    initial_task = normalize_initial_task(
        raw_task=raw_spec.get("initial_task"),
        team_name=team_name,
        main_agent_id=main_agent["agent_id"],
        sub_agent_ids=[sub["agent_id"] for sub in sub_agents],
    )
    initial_messages = normalize_initial_messages(
        raw_messages=raw_spec.get("initial_messages"),
        main_agent_id=main_agent["agent_id"],
        sub_agents=sub_agents,
    )
    return {
        "team_name": team_name,
        "objective": objective.strip(),
        "main_agent": main_agent,
        "sub_agents": sub_agents,
        "initial_task": initial_task,
        "initial_task_provided": initial_task_provided,
        "initial_messages": initial_messages,
        "initial_messages_provided": initial_messages_provided,
    }


def apply_should_include_task(normalized_spec: Dict[str, Any], force: bool, skip: bool) -> bool:
    if skip:
        return False
    if force:
        return True
    return bool(normalized_spec["initial_task_provided"])


def apply_should_include_messages(normalized_spec: Dict[str, Any], force: bool, skip: bool) -> bool:
    if skip:
        return False
    if force:
        return True
    return bool(normalized_spec["initial_messages_provided"])


def build_runtime_ops_plan(
    normalized_spec: Dict[str, Any],
    *,
    include_task_create: bool,
    include_send_messages: bool,
) -> List[Dict[str, Any]]:
    sub_agents = normalized_spec["sub_agents"]
    initial_task = normalized_spec["initial_task"]
    initial_messages = normalized_spec["initial_messages"]

    plan: List[Dict[str, Any]] = []
    step = 1
    plan.append(
        {
            "step": step,
            "operation": "team_create",
            "args_template": {
                "team_name": normalized_spec["team_name"],
                "leader_agent_id": normalized_spec["main_agent"]["agent_id"],
                "idempotency_key": "{{idempotency_prefix}}:team_create",
            },
        }
    )
    step += 1

    for sub in sub_agents:
        plan.append(
            {
                "step": step,
                "operation": "team_member_add",
                "args_template": {
                    "team_id": "{{team_id}}",
                    "agent_id": sub["agent_id"],
                    "role": sub["role"],
                    "idempotency_key": f"{{{{idempotency_prefix}}}}:team_member_add:{sub['agent_id']}",
                },
            }
        )
        step += 1

    if include_task_create:
        args_template: Dict[str, Any] = {
            "team_id": "{{team_id}}",
            "title": initial_task["title"],
            "owner_member_id": initial_task["owner_member_id"],
            "state": initial_task["state"],
            "idempotency_key": "{{idempotency_prefix}}:task_create",
        }
        if initial_task.get("blocked_reason"):
            args_template["blocked_reason"] = initial_task["blocked_reason"]
        if initial_task.get("result_reference"):
            args_template["result_reference"] = initial_task["result_reference"]
        plan.append({"step": step, "operation": "task_create", "args_template": args_template})
        step += 1

    if include_send_messages:
        for index, message in enumerate(initial_messages):
            plan.append(
                {
                    "step": step,
                    "operation": "send_message",
                    "args_template": {
                        "team_id": "{{team_id}}",
                        "from_member_id": message["from_member_id"],
                        "to_member_id": message["to_member_id"],
                        "message_type": "direct",
                        "payload": {"text": message["text"]},
                        "idempotency_key": f"{{{{idempotency_prefix}}}}:send_message:{index + 1}",
                    },
                }
            )
            step += 1

    return plan


def build_command_templates(
    normalized_spec: Dict[str, Any],
    *,
    include_task_create: bool,
    include_send_messages: bool,
) -> Dict[str, Any]:
    main_agent = normalized_spec["main_agent"]
    sub_agents = normalized_spec["sub_agents"]
    initial_task = normalized_spec["initial_task"]
    initial_messages = normalized_spec["initial_messages"]

    member_add_templates = []
    for sub in sub_agents:
        member_add_templates.append(
            {
                "member_id": sub["agent_id"],
                "argv_template": [
                    "codex-runtime",
                    "op",
                    "--name",
                    "team_member_add",
                    "--args-json",
                    json.dumps(
                        {
                            "team_id": "{{team_id}}",
                            "agent_id": sub["agent_id"],
                            "role": sub["role"],
                            "idempotency_key": f"{{{{idempotency_prefix}}}}:team_member_add:{sub['agent_id']}",
                        },
                        ensure_ascii=False,
                    ),
                ],
            }
        )

    message_templates = []
    if include_send_messages:
        for index, message in enumerate(initial_messages):
            message_templates.append(
                {
                    "target": message["to_member_id"],
                    "argv_template": [
                        "codex-runtime",
                        "op",
                        "--name",
                        "send_message",
                        "--args-json",
                        json.dumps(
                            {
                                "team_id": "{{team_id}}",
                                "from_member_id": message["from_member_id"],
                                "to_member_id": message["to_member_id"],
                                "message_type": "direct",
                                "payload": {"text": message["text"]},
                                "idempotency_key": f"{{{{idempotency_prefix}}}}:send_message:{index + 1}",
                            },
                            ensure_ascii=False,
                        ),
                    ],
                }
            )

    output: Dict[str, Any] = {
        "team_create": {
            "argv_template": [
                "codex-runtime",
                "op",
                "--name",
                "team_create",
                "--args-json",
                json.dumps(
                    {
                        "team_name": normalized_spec["team_name"],
                        "leader_agent_id": main_agent["agent_id"],
                        "idempotency_key": "{{idempotency_prefix}}:team_create",
                    },
                    ensure_ascii=False,
                ),
            ]
        },
        "team_member_add": member_add_templates,
        "send_message": message_templates,
        "notes": [
            "model_preset and reasoning_preset are preserved as preset names",
            "main_agent is brain/coordinator and sub_agents are delegated workers",
            "apply mode calls existing runtime adapter sequentially",
        ],
        "main_agent_id": main_agent["agent_id"],
    }

    if include_task_create:
        task_args: Dict[str, Any] = {
            "team_id": "{{team_id}}",
            "title": initial_task["title"],
            "owner_member_id": initial_task["owner_member_id"],
            "state": initial_task["state"],
            "idempotency_key": "{{idempotency_prefix}}:task_create",
        }
        if initial_task.get("blocked_reason"):
            task_args["blocked_reason"] = initial_task["blocked_reason"]
        if initial_task.get("result_reference"):
            task_args["result_reference"] = initial_task["result_reference"]
        output["task_create"] = {
            "argv_template": [
                "codex-runtime",
                "op",
                "--name",
                "task_create",
                "--args-json",
                json.dumps(task_args, ensure_ascii=False),
            ]
        }
    else:
        output["task_create"] = None

    return output


def build_plan_result(
    normalized_spec: Dict[str, Any],
    presets: Dict[str, Dict[str, Dict[str, str]]],
    *,
    include_task_create: bool,
    include_send_messages: bool,
) -> Dict[str, Any]:
    team_definition = {
        "schema_version": "agent_team.plan.v2",
        "team_name": normalized_spec["team_name"],
        "objective": normalized_spec["objective"] or None,
        "main_agent": normalized_spec["main_agent"],
        "sub_agents": normalized_spec["sub_agents"],
        "member_count": 1 + len(normalized_spec["sub_agents"]),
        "preset_catalog": {
            "model_presets": sorted(presets["model_presets"].keys()),
            "reasoning_presets": sorted(presets["reasoning_presets"].keys()),
        },
    }

    runtime_ops_plan = build_runtime_ops_plan(
        normalized_spec,
        include_task_create=include_task_create,
        include_send_messages=include_send_messages,
    )
    initial_task_template = {
        "enabled": include_task_create,
        **normalized_spec["initial_task"],
    }
    initial_message_templates = {
        "enabled": include_send_messages,
        "messages": normalized_spec["initial_messages"] if include_send_messages else [],
    }
    command_templates = build_command_templates(
        normalized_spec,
        include_task_create=include_task_create,
        include_send_messages=include_send_messages,
    )

    return {
        "team_definition": team_definition,
        "runtime_ops_plan": runtime_ops_plan,
        "initial_task_template": initial_task_template,
        "initial_message_templates": initial_message_templates,
        "command_templates": command_templates,
    }


def run_runtime_operation(
    runtime_cmd: List[str],
    *,
    strict: bool,
    store_root: Optional[str],
    operation: str,
    op_args: Dict[str, Any],
) -> Dict[str, Any]:
    command = list(runtime_cmd)
    if strict:
        command.append("--strict")
    if store_root:
        command.extend(["--store-root", store_root])
    command.extend(["op", "--name", operation, "--args-json", json.dumps(op_args, ensure_ascii=False)])

    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    stdout_text = (proc.stdout or "").strip()
    stderr_text = (proc.stderr or "").strip()

    envelope = None
    parse_error = None
    if stdout_text:
        try:
            parsed = json.loads(stdout_text)
            if isinstance(parsed, dict):
                envelope = parsed
            else:
                parse_error = "runtime output is not a JSON object"
        except json.JSONDecodeError as error:
            parse_error = f"invalid runtime JSON output: {error}"
    else:
        parse_error = "empty runtime output"

    operation_ok = None
    if isinstance(envelope, dict):
        operation_ok = bool(envelope.get("ok"))
    step_ok = proc.returncode == 0 and parse_error is None and operation_ok is True
    return {
        "operation": operation,
        "args": op_args,
        "command": command,
        "exit_code": proc.returncode,
        "operation_ok": operation_ok,
        "parse_error": parse_error,
        "stderr": stderr_text or None,
        "envelope": envelope,
        "ok": step_ok,
        "error": (envelope or {}).get("error"),
        "result": (envelope or {}).get("result"),
    }


def run_apply(
    normalized_spec: Dict[str, Any],
    *,
    runtime_cmd: List[str],
    strict: bool,
    store_root: Optional[str],
    include_task_create: bool,
    include_send_messages: bool,
    idempotency_prefix: str,
) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    stopped: Optional[Dict[str, Any]] = None
    resolved_ids: Dict[str, Optional[str]] = {
        "team_id": None,
        "leader_agent_id": None,
        "task_id": None,
    }

    def execute_step(operation: str, op_args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        nonlocal stopped
        step = run_runtime_operation(
            runtime_cmd,
            strict=strict,
            store_root=store_root,
            operation=operation,
            op_args=op_args,
        )
        step["step_index"] = len(steps) + 1
        steps.append(step)
        if not step["ok"] and stopped is None:
            stopped = {
                "step_index": step["step_index"],
                "operation": operation,
                "reason": step.get("parse_error")
                or (step.get("error") or {}).get("message")
                or "runtime operation failed",
            }
        return step if step["ok"] else None

    main_agent = normalized_spec["main_agent"]
    sub_agents = normalized_spec["sub_agents"]
    initial_task = normalized_spec["initial_task"]
    initial_messages = normalized_spec["initial_messages"]

    team_step = execute_step(
        "team_create",
        {
            "team_name": normalized_spec["team_name"],
            "leader_agent_id": main_agent["agent_id"],
            "idempotency_key": f"{idempotency_prefix}:team_create",
        },
    )
    if team_step is None:
        return finalize_apply_result(
            steps=steps,
            stopped=stopped,
            resolved_ids=resolved_ids,
            runtime_cmd=runtime_cmd,
            strict=strict,
            store_root=store_root,
            include_task_create=include_task_create,
            include_send_messages=include_send_messages,
            idempotency_prefix=idempotency_prefix,
        )

    team_result = team_step.get("result") or {}
    team_id = team_result.get("team_id")
    leader_agent_id = team_result.get("leader_agent_id")
    if not isinstance(team_id, str) or not team_id:
        stopped = {"step_index": team_step["step_index"], "operation": "team_create", "reason": "team_id missing from team_create result"}
        return finalize_apply_result(
            steps=steps,
            stopped=stopped,
            resolved_ids=resolved_ids,
            runtime_cmd=runtime_cmd,
            strict=strict,
            store_root=store_root,
            include_task_create=include_task_create,
            include_send_messages=include_send_messages,
            idempotency_prefix=idempotency_prefix,
        )

    resolved_ids["team_id"] = team_id
    resolved_ids["leader_agent_id"] = leader_agent_id if isinstance(leader_agent_id, str) else None

    for sub in sub_agents:
        member_step = execute_step(
            "team_member_add",
            {
                "team_id": team_id,
                "agent_id": sub["agent_id"],
                "role": sub["role"],
                "idempotency_key": f"{idempotency_prefix}:team_member_add:{sub['agent_id']}",
            },
        )
        if member_step is None:
            return finalize_apply_result(
                steps=steps,
                stopped=stopped,
                resolved_ids=resolved_ids,
                runtime_cmd=runtime_cmd,
                strict=strict,
                store_root=store_root,
                include_task_create=include_task_create,
                include_send_messages=include_send_messages,
                idempotency_prefix=idempotency_prefix,
            )

    if include_task_create:
        task_args: Dict[str, Any] = {
            "team_id": team_id,
            "title": initial_task["title"],
            "owner_member_id": initial_task["owner_member_id"],
            "state": initial_task["state"],
            "idempotency_key": f"{idempotency_prefix}:task_create",
        }
        if initial_task.get("blocked_reason"):
            task_args["blocked_reason"] = initial_task["blocked_reason"]
        if initial_task.get("result_reference"):
            task_args["result_reference"] = initial_task["result_reference"]
        task_step = execute_step("task_create", task_args)
        if task_step is None:
            return finalize_apply_result(
                steps=steps,
                stopped=stopped,
                resolved_ids=resolved_ids,
                runtime_cmd=runtime_cmd,
                strict=strict,
                store_root=store_root,
                include_task_create=include_task_create,
                include_send_messages=include_send_messages,
                idempotency_prefix=idempotency_prefix,
            )
        task_result = task_step.get("result") or {}
        task_id = task_result.get("task_id")
        if isinstance(task_id, str) and task_id:
            resolved_ids["task_id"] = task_id

    if include_send_messages:
        for index, message in enumerate(initial_messages):
            message_step = execute_step(
                "send_message",
                {
                    "team_id": team_id,
                    "from_member_id": message["from_member_id"],
                    "to_member_id": message["to_member_id"],
                    "message_type": "direct",
                    "payload": {"text": message["text"]},
                    "idempotency_key": f"{idempotency_prefix}:send_message:{index + 1}",
                },
            )
            if message_step is None:
                return finalize_apply_result(
                    steps=steps,
                    stopped=stopped,
                    resolved_ids=resolved_ids,
                    runtime_cmd=runtime_cmd,
                    strict=strict,
                    store_root=store_root,
                    include_task_create=include_task_create,
                    include_send_messages=include_send_messages,
                    idempotency_prefix=idempotency_prefix,
                )

    return finalize_apply_result(
        steps=steps,
        stopped=stopped,
        resolved_ids=resolved_ids,
        runtime_cmd=runtime_cmd,
        strict=strict,
        store_root=store_root,
        include_task_create=include_task_create,
        include_send_messages=include_send_messages,
        idempotency_prefix=idempotency_prefix,
    )


def finalize_apply_result(
    *,
    steps: List[Dict[str, Any]],
    stopped: Optional[Dict[str, Any]],
    resolved_ids: Dict[str, Optional[str]],
    runtime_cmd: List[str],
    strict: bool,
    store_root: Optional[str],
    include_task_create: bool,
    include_send_messages: bool,
    idempotency_prefix: str,
) -> Dict[str, Any]:
    succeeded = sum(1 for step in steps if step.get("ok"))
    failed = sum(1 for step in steps if not step.get("ok"))
    return {
        "executed": True,
        "mode": "strict" if strict else "fail-open",
        "runtime_cmd": runtime_cmd,
        "store_root": store_root,
        "idempotency_prefix": idempotency_prefix,
        "requested_operations": {
            "task_create": include_task_create,
            "send_message": include_send_messages,
        },
        "resolved_ids": resolved_ids,
        "operation_counts": {
            "executed": len(steps),
            "succeeded": succeeded,
            "failed": failed,
        },
        "steps": steps,
        "stopped": stopped,
        "next": {
            "reconcile_example": {
                "runtime_cmd_template": runtime_cmd
                + (["--strict"] if strict else [])
                + (["--store-root", store_root] if store_root else [])
                + ["op", "--name", "runtime_reconcile_all"],
            }
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 2 command surface for /agent_team (plan + thin apply)",
    )
    parser.add_argument("mode", choices=["plan", "apply"])
    parser.add_argument("--input-json", default="")
    parser.add_argument("--input-file", default="")
    parser.add_argument(
        "--presets-file",
        default="configs/agent-team-presets.json",
        help="Optional preset catalog json file",
    )
    parser.add_argument(
        "--runtime-cmd",
        default=default_runtime_cmd(),
        help="Runtime adapter command string (e.g. '/path/codex-runtime' or 'python3 .../codex_runtime_adapter.py')",
    )
    parser.add_argument(
        "--store-root",
        default=os.environ.get("CODEX_RUNTIME_STORE_ROOT", ""),
        help="Optional runtime store root passed through to runtime adapter",
    )
    parser.add_argument(
        "--idempotency-prefix",
        default=f"agent_team:{compact_utc_id()}",
        help="Idempotency key prefix for apply mode",
    )
    parser.add_argument("--force-task-create", action="store_true", help="Apply task_create even when initial_task is omitted")
    parser.add_argument("--skip-task-create", action="store_true", help="Skip task_create even when initial_task exists")
    parser.add_argument("--force-send-messages", action="store_true", help="Apply send_message even when initial_messages is omitted")
    parser.add_argument("--skip-send-messages", action="store_true", help="Skip send_message even when initial_messages exists")
    parser.add_argument("--strict", action="store_true", help="Pass strict mode to runtime adapter and return non-zero on apply failure")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    runtime_cmd = shlex.split(args.runtime_cmd)
    if not runtime_cmd:
        raise SystemExit("runtime command is empty")
    store_root = args.store_root.strip() or None
    idempotency_prefix = args.idempotency_prefix.strip() or f"agent_team:{compact_utc_id()}"

    output: Dict[str, Any] = {
        "ts": utc_now_iso(),
        "helper": "agent_team_command",
        "mode": args.mode,
    }

    try:
        spec = load_input_json(args.input_json, args.input_file)
        presets = load_presets(args.presets_file)
        normalized_spec = normalize_spec(spec, presets)

        include_task_create = apply_should_include_task(
            normalized_spec,
            force=args.force_task_create,
            skip=args.skip_task_create,
        )
        include_send_messages = apply_should_include_messages(
            normalized_spec,
            force=args.force_send_messages,
            skip=args.skip_send_messages,
        )

        output.update(
            build_plan_result(
                normalized_spec,
                presets,
                include_task_create=include_task_create,
                include_send_messages=include_send_messages,
            )
        )

        if args.mode == "plan":
            output.update(
                {
                    "ok": True,
                    "apply_extension": {
                        "status": "ready",
                        "notes": [
                            "slash command integration remains out of scope",
                            "apply mode executes existing runtime adapter sequentially",
                        ],
                    },
                }
            )
            exit_code = 0
        else:
            apply_result = run_apply(
                normalized_spec,
                runtime_cmd=runtime_cmd,
                strict=args.strict,
                store_root=store_root,
                include_task_create=include_task_create,
                include_send_messages=include_send_messages,
                idempotency_prefix=idempotency_prefix,
            )
            apply_ok = apply_result["stopped"] is None
            output.update(
                {
                    "ok": apply_ok,
                    "apply_result": apply_result,
                }
            )
            exit_code = 0 if apply_ok or not args.strict else 2

    except ValueError as error:
        output.update(
            {
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": str(error)},
            }
        )
        exit_code = 1

    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
