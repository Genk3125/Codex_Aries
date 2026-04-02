#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from team_control_plane import ControlPlaneError, TeamControlPlane, utc_now_iso
from team_message_bus import MessageBusError, TeamMessageBus
from team_task_bus import TASK_STATES, TaskBusError, TeamTaskBus, UNSET


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

        if operation == "runtime_reconcile_all":
            return {
                "control_plane": self.control_plane.startup_reconcile(),
                "message_bus": self.message_bus.startup_reconcile(),
                "task_bus": self.task_bus.startup_reconcile_orphan_owners(),
            }

        if operation == "runtime_info":
            return {
                "store_root": str(self.store_root),
                "control_plane_store": str(self.cp_store),
                "message_bus_store": str(self.mb_store),
                "task_bus_store": str(self.tb_store),
                "supported_operations": sorted(
                    [
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
                ),
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
