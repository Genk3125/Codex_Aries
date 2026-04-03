#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from src.team_runtime import (
        TASK_STATES,
        UNSET,
        ControlPlaneError,
        MessageBusError,
        TaskBusError,
        TeamControlPlane,
        TeamMessageBus,
        TeamTaskBus,
        TriggerLayer,
        TriggerLayerError,
        utc_now_iso,
    )
    from src.team_runtime.worktree_runtime import WorktreeRuntime, WorktreeRuntimeError
    from poc.verifier_queue import VerifierQueue, VerifierQueueError
except Exception:  # noqa: BLE001
    from team_control_plane import ControlPlaneError, TeamControlPlane, utc_now_iso
    from team_message_bus import MessageBusError, TeamMessageBus
    from team_task_bus import TASK_STATES, TaskBusError, TeamTaskBus, UNSET
    TriggerLayer = None  # type: ignore[assignment]
    TriggerLayerError = Exception  # type: ignore[assignment]
    WorktreeRuntime = None  # type: ignore[assignment,misc]
    WorktreeRuntimeError = Exception  # type: ignore[assignment]
    VerifierQueue = None  # type: ignore[assignment,misc]
    VerifierQueueError = Exception  # type: ignore[assignment]


class AdapterError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class CodexRuntimeAdapter:
    """
    Thin runtime adapter on top of existing PoCs.
    - No fork of Codex core
    - Store root configurable
    - Fail-open envelope support
    """

    def __init__(self, store_root: Path):
        self.store_root = store_root
        self.cp_store = self.store_root / "control-plane"
        self.mb_store = self.store_root / "message-bus"
        self.tb_store = self.store_root / "task-bus"
        self.trigger_store = self.store_root / "trigger-layer"

        self.control_plane = TeamControlPlane(self.cp_store)
        self.message_bus = TeamMessageBus(
            store_root=self.mb_store,
            control_plane_store_root=self.cp_store,
        )
        self.task_bus = TeamTaskBus(
            store_root=self.tb_store,
            control_plane_store_root=self.cp_store,
            message_bus_store_root=self.mb_store,
        )
        self.worktree_store = self.store_root / "worktree-runtime"
        self.vq_store = self.store_root / "verifier-queue"

        self.trigger_layer = None
        self.trigger_layer_error: str | None = None
        if TriggerLayer is not None:
            try:
                self.trigger_layer = TriggerLayer(self.trigger_store)
            except Exception as error:  # noqa: BLE001
                self.trigger_layer_error = str(error)
        else:
            self.trigger_layer_error = "TriggerLayer import unavailable"

        self.worktree_runtime = None
        self.worktree_runtime_error: str | None = None
        if WorktreeRuntime is not None:
            try:
                self.worktree_runtime = WorktreeRuntime(self.worktree_store)
            except Exception as error:  # noqa: BLE001
                self.worktree_runtime_error = str(error)
        else:
            self.worktree_runtime_error = "WorktreeRuntime import unavailable"

        self.verifier_queue = None
        self.verifier_queue_error: str | None = None
        if VerifierQueue is not None:
            try:
                self.verifier_queue = VerifierQueue(self.vq_store)
            except Exception as error:  # noqa: BLE001
                self.verifier_queue_error = str(error)
        else:
            self.verifier_queue_error = "VerifierQueue import unavailable"

    def _parse_payload(self, args: Dict[str, Any]) -> str:
        if "payload_json" in args and args["payload_json"] is not None:
            return str(args["payload_json"])
        payload = args.get("payload", {})
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise AdapterError("VALIDATION_ERROR", "payload must be object when payload_json is omitted")
        return json.dumps(payload, ensure_ascii=False)

    def _task_update_arg(self, args: Dict[str, Any], key: str) -> Any:
        return args[key] if key in args else UNSET

    def _parse_object_arg(
        self,
        args: Dict[str, Any],
        *,
        object_key: str,
        json_key: str,
        default_empty: bool = True,
    ) -> Dict[str, Any]:
        value = args.get(object_key)
        if value is None:
            value = args.get(json_key)
        if value is None:
            return {} if default_empty else {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as error:
                raise AdapterError("VALIDATION_ERROR", f"invalid {json_key}: {error}") from error
            if not isinstance(parsed, dict):
                raise AdapterError("VALIDATION_ERROR", f"{json_key} must be JSON object")
            return parsed
        raise AdapterError("VALIDATION_ERROR", f"{object_key} must be object or JSON object string")

    def _require_trigger_layer(self) -> Any:
        if self.trigger_layer is None:
            detail = self.trigger_layer_error or "not initialized"
            raise AdapterError("TRIGGER_LAYER_UNAVAILABLE", f"trigger layer unavailable: {detail}")
        return self.trigger_layer

    def _require_worktree_runtime(self) -> Any:
        if self.worktree_runtime is None:
            detail = self.worktree_runtime_error or "not initialized"
            raise AdapterError("WORKTREE_RUNTIME_UNAVAILABLE", f"worktree runtime unavailable: {detail}")
        return self.worktree_runtime

    def _require_verifier_queue(self) -> Any:
        if self.verifier_queue is None:
            detail = self.verifier_queue_error or "not initialized"
            raise AdapterError("VERIFIER_QUEUE_UNAVAILABLE", f"verifier queue unavailable: {detail}")
        return self.verifier_queue

    def call(self, operation: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if operation == "team_create":
            return self.control_plane.team_create(
                team_name=str(args["team_name"]),
                description=str(args.get("description", "")),
                leader_agent_id=args.get("leader_agent_id"),
                idempotency_key=args.get("idempotency_key"),
            )
        if operation == "team_member_add":
            return self.control_plane.team_member_add(
                team_id=str(args["team_id"]),
                agent_id=str(args["agent_id"]),
                role=str(args.get("role", "member")),
                idempotency_key=args.get("idempotency_key"),
            )
        if operation == "team_member_remove":
            return self.control_plane.team_member_remove(
                team_id=str(args["team_id"]),
                agent_id=str(args["agent_id"]),
                reason=str(args.get("reason", "")),
            )
        if operation == "team_delete":
            return self.control_plane.team_delete(
                team_id=str(args["team_id"]),
                mode=str(args.get("mode", "graceful")),
                reason=str(args.get("reason", "")),
                simulate_crash_after_marking_deleting=bool(args.get("simulate_crash_after_marking_deleting", False)),
            )
        if operation == "team_list":
            return self.control_plane.list_teams()
        if operation == "team_startup_reconcile":
            return self.control_plane.startup_reconcile()

        if operation == "send_message":
            message_type = str(args.get("message_type", "direct"))
            if message_type not in {"direct", "control"}:
                raise AdapterError("VALIDATION_ERROR", "message_type must be direct|control")
            subtype_default = "text" if message_type == "direct" else "shutdown"
            payload_json = self._parse_payload(args)
            return self.message_bus.send_message(
                team_id=str(args["team_id"]),
                from_member_id=str(args["from_member_id"]),
                to_member_id=str(args["to_member_id"]),
                message_type=message_type,
                subtype=str(args.get("subtype", subtype_default)),
                payload_json=payload_json,
                idempotency_key=args.get("idempotency_key"),
                defer_delivery=bool(args.get("defer_delivery", False)),
            )
        if operation == "message_list":
            return self.message_bus.list_messages(team_id=args.get("team_id"))
        if operation == "message_startup_reconcile":
            return self.message_bus.startup_reconcile()

        if operation == "task_create":
            return self.task_bus.task_create(
                team_id=str(args["team_id"]),
                title=str(args["title"]),
                description=str(args.get("description", "")),
                owner_member_id=args.get("owner_member_id"),
                state=str(args.get("state", "todo")),
                blocked_reason=args.get("blocked_reason"),
                result_reference=args.get("result_reference"),
                idempotency_key=args.get("idempotency_key"),
            )
        if operation == "task_get":
            return self.task_bus.task_get(task_id=str(args["task_id"]))
        if operation == "task_list":
            state = args.get("state")
            if state is not None and state not in TASK_STATES:
                raise AdapterError("INVALID_STATE", f"invalid state: {state}")
            return self.task_bus.task_list(
                team_id=args.get("team_id"),
                state=state,
                owner_member_id=args.get("owner_member_id"),
            )
        if operation == "task_update":
            return self.task_bus.task_update(
                task_id=str(args["task_id"]),
                title=self._task_update_arg(args, "title"),
                description=self._task_update_arg(args, "description"),
                owner_member_id=self._task_update_arg(args, "owner_member_id"),
                state=self._task_update_arg(args, "state"),
                blocked_reason=self._task_update_arg(args, "blocked_reason"),
                result_reference=self._task_update_arg(args, "result_reference"),
                idempotency_key=args.get("idempotency_key"),
            )
        if operation == "task_startup_reconcile_orphans":
            return self.task_bus.startup_reconcile_orphan_owners()

        if operation == "trigger_create":
            schedule = self._parse_object_arg(args, object_key="schedule", json_key="schedule_json")
            target = self._parse_object_arg(args, object_key="target", json_key="target_json")
            payload = self._parse_object_arg(args, object_key="payload", json_key="payload_json")
            return self._require_trigger_layer().trigger_create(
                kind=str(args["kind"]),
                schedule=schedule,
                target=target,
                payload=payload,
                status=str(args.get("status", "scheduled")),
                trigger_id=args.get("trigger_id"),
                idempotency_key=args.get("idempotency_key"),
            )
        if operation == "trigger_list":
            return self._require_trigger_layer().trigger_list(
                status=args.get("status"),
                kind=args.get("kind"),
                team_id=args.get("team_id"),
                include_deleted=bool(args.get("include_deleted", False)),
            )
        if operation == "trigger_delete":
            return self._require_trigger_layer().trigger_delete(
                trigger_id=str(args["trigger_id"]),
                reason=str(args.get("reason", "")),
                idempotency_key=args.get("idempotency_key"),
            )
        if operation == "trigger_fire_due":
            max_count_raw = args.get("max_count", 100)
            try:
                max_count = int(max_count_raw)
            except (TypeError, ValueError) as error:
                raise AdapterError("VALIDATION_ERROR", "max_count must be integer") from error
            return self._require_trigger_layer().trigger_fire_due(
                now_iso=args.get("now_iso"),
                max_count=max_count,
                idempotency_key=args.get("idempotency_key"),
            )

        if operation == "worktree_enter":
            return self._require_worktree_runtime().worktree_enter(
                team_id=str(args["team_id"]),
                member_id=str(args["member_id"]),
                repo_path=args.get("repo_path"),
                branch_name=args.get("branch_name"),
                base_ref=args.get("base_ref"),
                mode=str(args.get("mode", "create")),
                idempotency_key=args.get("idempotency_key"),
            )
        if operation == "worktree_exit":
            return self._require_worktree_runtime().worktree_exit(
                worktree_id=str(args["worktree_id"]),
                cleanup_mode=str(args.get("cleanup_mode", "delete_if_clean")),
                idempotency_key=args.get("idempotency_key"),
            )
        if operation == "worktree_cleanup":
            return self._require_worktree_runtime().worktree_cleanup(
                team_id=args.get("team_id"),
                force=bool(args.get("force", False)),
                idempotency_key=args.get("idempotency_key"),
            )
        if operation == "worktree_list":
            return self._require_worktree_runtime().worktree_list(
                team_id=args.get("team_id"),
                status=args.get("status"),
                include_deleted=bool(args.get("include_deleted", False)),
            )
        if operation == "worktree_startup_reconcile":
            return self._require_worktree_runtime().startup_reconcile()

        if operation == "verifier_request_create":
            return self._require_verifier_queue().verifier_request_create(
                payload_ref=str(args["payload_ref"]),
                requester_id=args.get("requester_id"),
                context=args.get("context"),
                request_id=args.get("request_id"),
                idempotency_key=args.get("idempotency_key"),
            )
        if operation == "verifier_request_get":
            return self._require_verifier_queue().verifier_request_get(
                request_id=str(args["request_id"]),
            )
        if operation == "verifier_request_list":
            limit_raw = args.get("limit", 100)
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError) as error:
                raise AdapterError("VALIDATION_ERROR", "limit must be integer") from error
            return self._require_verifier_queue().verifier_request_list(
                status=args.get("status"),
                requester_id=args.get("requester_id"),
                limit=limit,
            )
        if operation == "verifier_request_claim_once":
            return self._require_verifier_queue().verifier_request_claim_once(
                claimer_id=str(args["claimer_id"]),
            )
        if operation == "verifier_request_complete":
            return self._require_verifier_queue().verifier_request_complete(
                request_id=str(args["request_id"]),
                outcome=str(args["outcome"]),
                result_ref=args.get("result_ref"),
            )

        if operation == "runtime_reconcile_all":
            return {
                "control_plane": self.control_plane.startup_reconcile(),
                "message_bus": self.message_bus.startup_reconcile(),
                "task_bus": self.task_bus.startup_reconcile_orphan_owners(),
            }

        if operation == "runtime_info":
            supported_operations = [
                "team_create",
                "team_member_add",
                "team_member_remove",
                "team_delete",
                "team_list",
                "team_startup_reconcile",
                "send_message",
                "message_list",
                "message_startup_reconcile",
                "task_create",
                "task_get",
                "task_list",
                "task_update",
                "task_startup_reconcile_orphans",
                "runtime_reconcile_all",
                "runtime_info",
            ]
            if self.trigger_layer is not None:
                supported_operations.extend(
                    [
                        "trigger_create",
                        "trigger_list",
                        "trigger_delete",
                        "trigger_fire_due",
                    ]
                )
            if self.worktree_runtime is not None:
                supported_operations.extend(
                    [
                        "worktree_enter",
                        "worktree_exit",
                        "worktree_cleanup",
                        "worktree_list",
                        "worktree_startup_reconcile",
                    ]
                )
            if self.verifier_queue is not None:
                supported_operations.extend(
                    [
                        "verifier_request_create",
                        "verifier_request_get",
                        "verifier_request_list",
                        "verifier_request_claim_once",
                        "verifier_request_complete",
                    ]
                )
            return {
                "store_root": str(self.store_root),
                "control_plane_store": str(self.cp_store),
                "message_bus_store": str(self.mb_store),
                "task_bus_store": str(self.tb_store),
                "trigger_layer_store": str(self.trigger_store),
                "worktree_runtime_store": str(self.worktree_store),
                "trigger_layer_available": self.trigger_layer is not None,
                "trigger_layer_error": self.trigger_layer_error,
                "worktree_runtime_available": self.worktree_runtime is not None,
                "worktree_runtime_error": self.worktree_runtime_error,
                "supported_operations": sorted(supported_operations),
            }

        raise AdapterError("UNKNOWN_OPERATION", f"unsupported operation: {operation}")


def parse_args_payload(args_json: str, args_file: str) -> Dict[str, Any]:
    if args_json and args_file:
        raise AdapterError("VALIDATION_ERROR", "use either --args-json or --args-file")
    if args_file:
        data = json.loads(Path(args_file).read_text(encoding="utf-8"))
    elif args_json:
        data = json.loads(args_json)
    else:
        data = {}
    if not isinstance(data, dict):
        raise AdapterError("VALIDATION_ERROR", "operation args must be JSON object")
    return data


def normalize_error(error: Exception) -> Tuple[str, str]:
    if isinstance(error, (ControlPlaneError, MessageBusError, TaskBusError, AdapterError)):
        return str(error.code), str(error.message)
    if hasattr(error, "code") and hasattr(error, "message"):
        return str(getattr(error, "code")), str(getattr(error, "message"))
    return "UNHANDLED_ERROR", str(error)


def envelope(
    *,
    operation: str,
    args: Dict[str, Any],
    result: Dict[str, Any] | None,
    error: Dict[str, str] | None,
    fail_open: bool,
) -> Dict[str, Any]:
    return {
        "ts": utc_now_iso(),
        "operation": operation,
        "args": args,
        "ok": error is None,
        "fail_open": fail_open,
        "result": result,
        "error": error,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex runtime adapter for control/message/task PoCs")
    parser.add_argument(
        "--store-root",
        default=os.environ.get("CODEX_RUNTIME_STORE_ROOT", str(Path.cwd() / ".runtime" / "codex-runtime-adapter")),
        help="Runtime store root (or CODEX_RUNTIME_STORE_ROOT)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Disable fail-open. Errors return non-zero exit.",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to save adapter response JSON",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    op = subparsers.add_parser("op", help="Invoke operation")
    op.add_argument("--name", required=True, help="Operation name")
    op.add_argument("--args-json", default="", help="Operation args as JSON object string")
    op.add_argument("--args-file", default="", help="Path to JSON args file")

    info = subparsers.add_parser("ops", help="List supported operations")
    _ = info
    return parser


def main() -> int:
    parser = build_parser()
    cli = parser.parse_args()

    try:
        adapter = CodexRuntimeAdapter(store_root=Path(cli.store_root))
    except Exception as error:  # noqa: BLE001
        code, message = normalize_error(error)
        output = envelope(
            operation="adapter_init",
            args={"store_root": cli.store_root},
            result=None,
            error={"code": code, "message": message},
            fail_open=not cli.strict,
        )
        text = json.dumps(output, ensure_ascii=False, indent=2)
        print(text)
        if cli.output_json:
            Path(cli.output_json).parent.mkdir(parents=True, exist_ok=True)
            Path(cli.output_json).write_text(text + "\n", encoding="utf-8")
        return 0 if not cli.strict else 2

    if cli.command == "ops":
        result = adapter.call("runtime_info", {})
        output = envelope(
            operation="runtime_info",
            args={},
            result=result,
            error=None,
            fail_open=not cli.strict,
        )
        text = json.dumps(output, ensure_ascii=False, indent=2)
        print(text)
        if cli.output_json:
            Path(cli.output_json).parent.mkdir(parents=True, exist_ok=True)
            Path(cli.output_json).write_text(text + "\n", encoding="utf-8")
        return 0

    try:
        op_args = parse_args_payload(cli.args_json, cli.args_file)
        result = adapter.call(cli.name, op_args)
        output = envelope(
            operation=cli.name,
            args=op_args,
            result=result,
            error=None,
            fail_open=not cli.strict,
        )
    except Exception as error:  # noqa: BLE001
        code, message = normalize_error(error)
        output = envelope(
            operation=cli.name,
            args=op_args if "op_args" in locals() else {},
            result=None,
            error={"code": code, "message": message},
            fail_open=not cli.strict,
        )

    text = json.dumps(output, ensure_ascii=False, indent=2)
    print(text)
    if cli.output_json:
        output_path = Path(cli.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")

    if output["error"] is not None and cli.strict:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
