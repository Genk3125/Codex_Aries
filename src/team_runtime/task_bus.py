#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .control_plane import (
    ControlPlaneError,
    TeamControlPlane,
    atomic_write_json,
    read_json_or_default,
    utc_now_iso,
)


UNSET = object()

ALLOWED_STATE_TRANSITIONS = {
    "todo": {"ready", "cancelled"},
    "ready": {"in_progress", "blocked", "cancelled"},
    "in_progress": {"blocked", "done", "failed", "cancelled"},
    "blocked": {"ready", "cancelled"},
    "failed": {"ready", "cancelled"},
    "done": set(),
    "cancelled": set(),
}

TASK_STATES = set(ALLOWED_STATE_TRANSITIONS.keys())


@dataclass
class TaskBusError(Exception):
    code: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"error": self.code, "message": self.message}


class TeamTaskBus:
    """
    Minimal Team Task Bus PoC.
    Scope:
    - task create/get/list/update
    - owner/state/blocked_reason/result_reference
    - minimal idempotency(create/update)
    - startup orphan owner reconcile
    Out of scope:
    - auto reassignment
    - approval workflow
    - verifier automation
    - UI/trigger integration
    """

    def __init__(
        self,
        store_root: Path,
        control_plane_store_root: Path,
        message_bus_store_root: Optional[Path] = None,
    ):
        self.store_root = store_root
        self.tasks_dir = self.store_root / "tasks"
        self.idempotency_path = self.store_root / "idempotency.json"
        self.events_log_path = self.store_root / "task-events.log"
        self.control_plane_store_root = control_plane_store_root
        self.control_plane = TeamControlPlane(control_plane_store_root)
        self.message_bus_store_root = message_bus_store_root
        self._bootstrap_store()

    def _bootstrap_store(self) -> None:
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        if not self.idempotency_path.exists():
            atomic_write_json(
                self.idempotency_path,
                {
                    "schema_version": 1,
                    "task_create": {},
                    "task_update": {},
                },
            )
        if not self.events_log_path.exists():
            self.events_log_path.parent.mkdir(parents=True, exist_ok=True)
            self.events_log_path.touch()

    def _append_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {"ts": utc_now_iso(), "event_type": event_type, "payload": payload}
        with self.events_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _emit_message_bus_hint(self, event_type: str, payload: Dict[str, Any]) -> None:
        if not self.message_bus_store_root:
            return
        try:
            from .message_bus import TeamMessageBus

            bus = TeamMessageBus(
                store_root=self.message_bus_store_root,
                control_plane_store_root=self.control_plane_store_root,
            )
            bus.record_external_event(event_type=event_type, payload=payload)
            self._append_event(
                "message_bus_hint_emitted",
                {"event_type": event_type, "payload": payload},
            )
        except Exception as error:  # noqa: BLE001
            self._append_event(
                "message_bus_hint_failed",
                {"event_type": event_type, "error": str(error)},
            )

    def _task_file_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"task-{task_id}.json"

    def _save_task(self, task: Dict[str, Any]) -> None:
        task["updated_at"] = utc_now_iso()
        task["version"] = int(task.get("version", 0)) + 1
        atomic_write_json(self._task_file_path(task["task_id"]), task)

    def _load_task(self, task_id: str) -> Dict[str, Any]:
        task_path = self._task_file_path(task_id)
        if not task_path.exists():
            raise TaskBusError("TASK_NOT_FOUND", f"task not found: {task_id}")
        with task_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _read_idempotency(self) -> Dict[str, Any]:
        return read_json_or_default(
            self.idempotency_path,
            {"schema_version": 1, "task_create": {}, "task_update": {}},
        )

    def _save_idempotency(self, data: Dict[str, Any]) -> None:
        atomic_write_json(self.idempotency_path, data)

    def _load_team_or_raise(self, team_id: str) -> Dict[str, Any]:
        try:
            return self.control_plane.get_team(team_id)
        except ControlPlaneError as error:
            raise TaskBusError(error.code, error.message) from error

    def _assert_team_mutable(self, team_id: str) -> Dict[str, Any]:
        team = self._load_team_or_raise(team_id)
        status = str(team.get("status", ""))
        if status in {"deleting", "deleted"}:
            raise TaskBusError("TEAM_NOT_MUTABLE", f"team status {status} cannot mutate tasks")
        return team

    def _find_member(self, team: Dict[str, Any], member_id: str) -> Optional[Dict[str, Any]]:
        for member in team.get("members", []):
            if member.get("agent_id") == member_id:
                return member
        return None

    def _validate_owner(self, team: Dict[str, Any], owner_member_id: Optional[str]) -> None:
        if owner_member_id is None:
            return
        member = self._find_member(team, owner_member_id)
        if not member:
            raise TaskBusError("OWNER_NOT_FOUND", f"owner not found in team: {owner_member_id}")
        lifecycle = str(member.get("lifecycle", ""))
        if lifecycle in {"shutdown", "not_found"}:
            raise TaskBusError(
                "OWNER_NOT_ASSIGNABLE",
                f"owner lifecycle is not assignable: {lifecycle}",
            )

    def _validate_transition(self, old_state: str, new_state: str) -> None:
        if new_state == old_state:
            return
        if old_state not in TASK_STATES or new_state not in TASK_STATES:
            raise TaskBusError("INVALID_STATE", f"invalid state transition: {old_state} -> {new_state}")
        if new_state not in ALLOWED_STATE_TRANSITIONS[old_state]:
            raise TaskBusError(
                "INVALID_STATE_TRANSITION",
                f"invalid state transition: {old_state} -> {new_state}",
            )

    def _task_response(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "task_id": task["task_id"],
            "team_id": task["team_id"],
            "title": task["title"],
            "owner_member_id": task.get("owner_member_id"),
            "state": task["state"],
            "blocked_reason": task.get("blocked_reason"),
            "result_reference": task.get("result_reference"),
            "version": task["version"],
            "updated_at": task["updated_at"],
        }

    def task_create(
        self,
        team_id: str,
        title: str,
        description: str = "",
        owner_member_id: Optional[str] = None,
        state: str = "todo",
        blocked_reason: Optional[str] = None,
        result_reference: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not team_id or not title:
            raise TaskBusError("VALIDATION_ERROR", "team_id and title are required")
        if state not in TASK_STATES:
            raise TaskBusError("INVALID_STATE", f"invalid state: {state}")
        if state == "blocked" and not blocked_reason:
            raise TaskBusError("VALIDATION_ERROR", "blocked_reason is required when state=blocked")

        idempotency = self._read_idempotency()
        if idempotency_key:
            existing = idempotency.get("task_create", {}).get(idempotency_key)
            if existing:
                return existing["response"]

        team = self._assert_team_mutable(team_id)
        self._validate_owner(team=team, owner_member_id=owner_member_id)

        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        task = {
            "schema_version": 1,
            "task_id": task_id,
            "team_id": team_id,
            "title": title,
            "description": description,
            "owner_member_id": owner_member_id,
            "state": state,
            "blocked_reason": blocked_reason or None,
            "result_reference": result_reference or None,
            "created_at": now,
            "updated_at": now,
            "version": 0,
            "orphan_owner": None,
            "idempotency_key_create": idempotency_key or "",
        }
        self._save_task(task)
        response = self._task_response(task)

        if idempotency_key:
            idempotency.setdefault("task_create", {})[idempotency_key] = {
                "created_at": now,
                "task_id": task_id,
                "response": response,
            }
            self._save_idempotency(idempotency)

        self._append_event("task_create", response)
        self._emit_message_bus_hint(
            "task_created",
            {"team_id": team_id, "task_id": task_id, "owner_member_id": owner_member_id},
        )
        return response

    def task_get(self, task_id: str) -> Dict[str, Any]:
        task = self._load_task(task_id)
        return self._task_response(task)

    def task_list(
        self,
        team_id: Optional[str] = None,
        state: Optional[str] = None,
        owner_member_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if state and state not in TASK_STATES:
            raise TaskBusError("INVALID_STATE", f"invalid state: {state}")
        tasks: List[Dict[str, Any]] = []
        for task_file in sorted(self.tasks_dir.glob("task-*.json")):
            with task_file.open("r", encoding="utf-8") as handle:
                task = json.load(handle)
            if team_id and task.get("team_id") != team_id:
                continue
            if state and task.get("state") != state:
                continue
            if owner_member_id and task.get("owner_member_id") != owner_member_id:
                continue
            tasks.append(self._task_response(task))
        return {"count": len(tasks), "tasks": tasks}

    def task_update(
        self,
        task_id: str,
        *,
        title: Any = UNSET,
        description: Any = UNSET,
        owner_member_id: Any = UNSET,
        state: Any = UNSET,
        blocked_reason: Any = UNSET,
        result_reference: Any = UNSET,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not task_id:
            raise TaskBusError("VALIDATION_ERROR", "task_id is required")

        idempotency = self._read_idempotency()
        if idempotency_key:
            existing = idempotency.get("task_update", {}).get(idempotency_key)
            if existing:
                return existing["response"]

        task = self._load_task(task_id)
        team = self._assert_team_mutable(task["team_id"])
        original = dict(task)

        if title is not UNSET:
            if not title:
                raise TaskBusError("VALIDATION_ERROR", "title cannot be empty")
            task["title"] = str(title)

        if description is not UNSET:
            task["description"] = str(description)

        if owner_member_id is not UNSET:
            self._validate_owner(team=team, owner_member_id=owner_member_id)
            task["owner_member_id"] = owner_member_id

        if state is not UNSET:
            if state not in TASK_STATES:
                raise TaskBusError("INVALID_STATE", f"invalid state: {state}")
            self._validate_transition(task["state"], state)
            task["state"] = state

        if blocked_reason is not UNSET:
            if blocked_reason in {"", None}:
                task["blocked_reason"] = None
            else:
                task["blocked_reason"] = str(blocked_reason)

        if task["state"] == "blocked" and not task.get("blocked_reason"):
            raise TaskBusError("VALIDATION_ERROR", "blocked_reason is required when state=blocked")
        if task["state"] != "blocked" and blocked_reason is UNSET:
            task["blocked_reason"] = None

        if result_reference is not UNSET:
            if result_reference in {"", None}:
                task["result_reference"] = None
            else:
                task["result_reference"] = str(result_reference)

        if task == original:
            raise TaskBusError("NO_CHANGES", "no effective changes")

        self._save_task(task)
        response = self._task_response(task)

        if idempotency_key:
            idempotency.setdefault("task_update", {})[idempotency_key] = {
                "created_at": utc_now_iso(),
                "task_id": task_id,
                "response": response,
            }
            self._save_idempotency(idempotency)

        self._append_event("task_update", {"task_id": task_id, "response": response})
        self._emit_message_bus_hint(
            "task_updated",
            {"team_id": task["team_id"], "task_id": task_id, "state": task["state"]},
        )
        return response

    def startup_reconcile_orphan_owners(self) -> Dict[str, Any]:
        scanned = 0
        orphaned = 0
        moved_to_ready = 0
        errors: List[Dict[str, Any]] = []
        updated_tasks: List[str] = []

        for task_file in sorted(self.tasks_dir.glob("task-*.json")):
            with task_file.open("r", encoding="utf-8") as handle:
                task = json.load(handle)
            scanned += 1

            owner_member_id = task.get("owner_member_id")
            if not owner_member_id:
                continue

            reason = None
            try:
                team = self.control_plane.get_team(task["team_id"])
                member = self._find_member(team, owner_member_id)
                if member is None:
                    reason = "OWNER_NOT_FOUND_IN_TEAM"
                else:
                    lifecycle = str(member.get("lifecycle", ""))
                    if lifecycle in {"shutdown", "not_found"}:
                        reason = f"OWNER_LIFECYCLE:{lifecycle}"
            except ControlPlaneError as error:
                reason = error.code
            except Exception as error:  # noqa: BLE001
                errors.append({"task_id": task["task_id"], "error": str(error)})
                continue

            if not reason:
                continue

            orphaned += 1
            previous_owner = owner_member_id
            task["owner_member_id"] = None
            if task.get("state") == "in_progress":
                task["state"] = "ready"
                moved_to_ready += 1
            task["orphan_owner"] = {
                "previous_owner_member_id": previous_owner,
                "detected_at": utc_now_iso(),
                "reason": reason,
            }
            self._save_task(task)
            updated_tasks.append(task["task_id"])
            self._append_event(
                "task_orphan_owner_reconciled",
                {
                    "task_id": task["task_id"],
                    "previous_owner_member_id": previous_owner,
                    "reason": reason,
                },
            )
            self._emit_message_bus_hint(
                "task_owner_orphaned",
                {"team_id": task["team_id"], "task_id": task["task_id"], "reason": reason},
            )

        summary = {
            "reconciled_at": utc_now_iso(),
            "scanned": scanned,
            "orphaned": orphaned,
            "moved_to_ready": moved_to_ready,
            "updated_tasks": updated_tasks,
            "errors": errors,
        }
        self._append_event("startup_reconcile_orphan_owners", summary)
        return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal Team Task Bus PoC")
    parser.add_argument(
        "--store-root",
        default=str(Path.cwd() / ".runtime" / "task-bus"),
        help="Path to task-bus persistence directory",
    )
    parser.add_argument(
        "--control-plane-store-root",
        default=str(Path.cwd() / ".runtime" / "control-plane"),
        help="Path to control-plane persistence directory",
    )
    parser.add_argument(
        "--message-bus-store-root",
        default=None,
        help="Optional: message bus store root for loose-coupled hint emission",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("task-create", help="Create a task")
    create.add_argument("--team-id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--description", default="")
    create.add_argument("--owner-member-id")
    create.add_argument("--state", default="todo")
    create.add_argument("--blocked-reason")
    create.add_argument("--result-reference")
    create.add_argument("--idempotency-key")

    get_task = subparsers.add_parser("task-get", help="Get a task")
    get_task.add_argument("--task-id", required=True)

    list_tasks = subparsers.add_parser("task-list", help="List tasks")
    list_tasks.add_argument("--team-id")
    list_tasks.add_argument("--state")
    list_tasks.add_argument("--owner-member-id")

    update = subparsers.add_parser("task-update", help="Update a task")
    update.add_argument("--task-id", required=True)
    update.add_argument("--title")
    update.add_argument("--description")
    update.add_argument("--owner-member-id")
    update.add_argument("--state")
    update.add_argument("--blocked-reason")
    update.add_argument("--clear-blocked-reason", action="store_true")
    update.add_argument("--result-reference")
    update.add_argument("--clear-result-reference", action="store_true")
    update.add_argument("--idempotency-key")

    subparsers.add_parser(
        "startup-reconcile-orphans",
        help="Re-evaluate orphan owners at startup",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    message_bus_store_root = Path(args.message_bus_store_root) if args.message_bus_store_root else None
    task_bus = TeamTaskBus(
        store_root=Path(args.store_root),
        control_plane_store_root=Path(args.control_plane_store_root),
        message_bus_store_root=message_bus_store_root,
    )

    try:
        if args.command == "task-create":
            result = task_bus.task_create(
                team_id=args.team_id,
                title=args.title,
                description=args.description,
                owner_member_id=args.owner_member_id,
                state=args.state,
                blocked_reason=args.blocked_reason,
                result_reference=args.result_reference,
                idempotency_key=args.idempotency_key,
            )
        elif args.command == "task-get":
            result = task_bus.task_get(task_id=args.task_id)
        elif args.command == "task-list":
            result = task_bus.task_list(
                team_id=args.team_id,
                state=args.state,
                owner_member_id=args.owner_member_id,
            )
        elif args.command == "task-update":
            owner_value: Any = UNSET
            if args.owner_member_id is not None:
                if args.owner_member_id.lower() == "null":
                    owner_value = None
                else:
                    owner_value = args.owner_member_id

            blocked_reason_value: Any = UNSET
            if args.blocked_reason is not None:
                blocked_reason_value = args.blocked_reason
            if args.clear_blocked_reason:
                blocked_reason_value = None

            result_reference_value: Any = UNSET
            if args.result_reference is not None:
                result_reference_value = args.result_reference
            if args.clear_result_reference:
                result_reference_value = None

            result = task_bus.task_update(
                task_id=args.task_id,
                title=args.title if args.title is not None else UNSET,
                description=args.description if args.description is not None else UNSET,
                owner_member_id=owner_value,
                state=args.state if args.state is not None else UNSET,
                blocked_reason=blocked_reason_value,
                result_reference=result_reference_value,
                idempotency_key=args.idempotency_key,
            )
        elif args.command == "startup-reconcile-orphans":
            result = task_bus.startup_reconcile_orphan_owners()
        else:
            parser.print_help()
            return 1
    except TaskBusError as error:
        print(json.dumps(error.to_dict(), ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
