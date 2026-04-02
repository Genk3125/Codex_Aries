#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def read_json_or_default(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@dataclass
class ControlPlaneError(Exception):
    code: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"error": self.code, "message": self.message}


class TeamControlPlane:
    """
    Minimal Team Control Plane PoC.
    Scope:
    - team_create
    - team_delete
    - persistence
    - startup reconcile for deleting -> deleted continuation
    Out of scope (stub/TODO):
    - Message Bus integration
    - Task Bus integration
    """

    def __init__(self, store_root: Path):
        self.store_root = store_root
        self.teams_dir = self.store_root / "teams"
        self.active_index_path = self.store_root / "active-team-index.json"
        self.idempotency_path = self.store_root / "idempotency.json"
        self.events_log_path = self.store_root / "team-events.log"
        self._bootstrap_store()

    def _bootstrap_store(self) -> None:
        self.teams_dir.mkdir(parents=True, exist_ok=True)
        if not self.active_index_path.exists():
            atomic_write_json(self.active_index_path, {"schema_version": 1, "team_name_to_id": {}})
        if not self.idempotency_path.exists():
            atomic_write_json(
                self.idempotency_path,
                {"schema_version": 1, "team_create": {}, "team_member_add": {}},
            )
        if not self.events_log_path.exists():
            self.events_log_path.parent.mkdir(parents=True, exist_ok=True)
            self.events_log_path.touch()

    def _append_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {"ts": utc_now_iso(), "event_type": event_type, "payload": payload}
        with self.events_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _message_bus_stub(self, event_type: str, team_id: str) -> None:
        self._append_event(
            "message_bus_stub",
            {
                "team_id": team_id,
                "event_type": event_type,
                "todo": "Connect to Message Bus RFC implementation.",
            },
        )

    def _task_bus_stub(self, event_type: str, team_id: str) -> None:
        self._append_event(
            "task_bus_stub",
            {
                "team_id": team_id,
                "event_type": event_type,
                "todo": "Connect to Task Bus RFC implementation.",
            },
        )

    def _team_file_path(self, team_id: str) -> Path:
        return self.teams_dir / f"team-{team_id}.json"

    def _load_team(self, team_id: str) -> Dict[str, Any]:
        team_path = self._team_file_path(team_id)
        if not team_path.exists():
            raise ControlPlaneError("TEAM_NOT_FOUND", f"team not found: {team_id}")
        with team_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def get_team(self, team_id: str) -> Dict[str, Any]:
        return self._load_team(team_id)

    def get_team_status(self, team_id: str) -> str:
        return str(self._load_team(team_id).get("status", ""))

    def _save_team(self, team: Dict[str, Any]) -> None:
        team["updated_at"] = utc_now_iso()
        team["version"] = int(team.get("version", 0)) + 1
        atomic_write_json(self._team_file_path(team["team_id"]), team)

    def _read_active_index(self) -> Dict[str, Any]:
        return read_json_or_default(self.active_index_path, {"schema_version": 1, "team_name_to_id": {}})

    def _save_active_index(self, data: Dict[str, Any]) -> None:
        atomic_write_json(self.active_index_path, data)

    def _read_idempotency(self) -> Dict[str, Any]:
        data = read_json_or_default(
            self.idempotency_path,
            {"schema_version": 1, "team_create": {}, "team_member_add": {}},
        )
        changed = False
        if not isinstance(data, dict):
            data = {}
            changed = True
        if "schema_version" not in data:
            data["schema_version"] = 1
            changed = True
        for key in ("team_create", "team_member_add"):
            if not isinstance(data.get(key), dict):
                data[key] = {}
                changed = True
        if changed:
            self._save_idempotency(data)
        return data

    def _save_idempotency(self, data: Dict[str, Any]) -> None:
        atomic_write_json(self.idempotency_path, data)

    def startup_reconcile(self) -> Dict[str, Any]:
        cleaned: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for team_file in sorted(self.teams_dir.glob("team-*.json")):
            with team_file.open("r", encoding="utf-8") as handle:
                team = json.load(handle)
            if team.get("status") != "deleting":
                continue
            try:
                result = self._finalize_delete(
                    team=team,
                    mode="graceful",
                    reason="startup_reconcile",
                )
                cleaned.append(result)
            except ControlPlaneError as error:
                errors.append({"team_id": team.get("team_id"), **error.to_dict()})

        summary = {
            "reconciled_at": utc_now_iso(),
            "cleaned_count": len(cleaned),
            "error_count": len(errors),
            "cleaned": cleaned,
            "errors": errors,
        }
        self._append_event("startup_reconcile", summary)
        return summary

    def team_create(
        self,
        team_name: str,
        description: Optional[str] = None,
        leader_agent_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not team_name:
            raise ControlPlaneError("VALIDATION_ERROR", "team_name is required")

        idempotency = self._read_idempotency()
        if idempotency_key:
            existing = idempotency.get("team_create", {}).get(idempotency_key)
            if existing:
                return existing["response"]

        active_index = self._read_active_index()
        existing_team_id = active_index.get("team_name_to_id", {}).get(team_name)
        if existing_team_id:
            existing_team = self._load_team(existing_team_id)
            if existing_team.get("status") in {"active", "deleting"}:
                raise ControlPlaneError(
                    "TEAM_ALREADY_EXISTS",
                    f"active/deleting team already exists for name: {team_name}",
                )

        team_id = f"team_{uuid.uuid4().hex[:12]}"
        leader_id = leader_agent_id or f"leader_{uuid.uuid4().hex[:8]}"
        now = utc_now_iso()

        team = {
            "schema_version": 1,
            "team_id": team_id,
            "team_name": team_name,
            "description": description or "",
            "status": "active",
            "leader_agent_id": leader_id,
            "members": [
                {
                    "agent_id": leader_id,
                    "role": "leader",
                    "lifecycle": "running",
                    "joined_at": now,
                }
            ],
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
            "version": 0,
            "cleanup_summary": None,
            "last_delete_reason": None,
        }

        self._save_team(team)
        active_index["team_name_to_id"][team_name] = team_id
        self._save_active_index(active_index)

        response = {
            "team_id": team_id,
            "team_name": team_name,
            "leader_agent_id": leader_id,
            "status": "active",
            "created_at": now,
        }

        if idempotency_key:
            idempotency.setdefault("team_create", {})[idempotency_key] = {
                "created_at": now,
                "team_id": team_id,
                "response": response,
            }
            self._save_idempotency(idempotency)

        self._message_bus_stub("team_create", team_id)
        self._task_bus_stub("team_create", team_id)
        self._append_event("team_create", response)
        return response

    def team_delete(
        self,
        team_id: str,
        mode: str = "graceful",
        reason: Optional[str] = None,
        simulate_crash_after_marking_deleting: bool = False,
    ) -> Dict[str, Any]:
        if mode not in {"graceful", "force"}:
            raise ControlPlaneError("VALIDATION_ERROR", "mode must be graceful or force")

        team = self._load_team(team_id)
        current_status = team.get("status")
        if current_status == "deleted":
            return {
                "team_id": team_id,
                "status": "deleted",
                "deleted_at": team.get("deleted_at"),
                "cleanup_summary": team.get("cleanup_summary"),
            }

        if current_status != "deleting":
            team["status"] = "deleting"
            team["last_delete_reason"] = reason or ""
            self._save_team(team)
            self._append_event(
                "team_delete_marked_deleting",
                {"team_id": team_id, "mode": mode, "reason": reason or ""},
            )

        if simulate_crash_after_marking_deleting:
            return {
                "team_id": team_id,
                "status": "deleting",
                "note": "simulated crash point reached; run startup_reconcile to continue cleanup",
            }

        return self._finalize_delete(team=team, mode=mode, reason=reason)

    def _finalize_delete(self, team: Dict[str, Any], mode: str, reason: Optional[str]) -> Dict[str, Any]:
        team_id = team["team_id"]
        members = team.get("members", [])
        active_like = {"running", "idle", "interrupted", "pending_init"}
        members_closed = 0
        orphans_detected = 0

        for member in members:
            lifecycle = member.get("lifecycle", "")
            if lifecycle in active_like:
                members_closed += 1
                member["lifecycle"] = "shutdown"
            if mode == "force" and lifecycle in active_like:
                orphans_detected += 1

        deleted_at = utc_now_iso()
        team["status"] = "deleted"
        team["deleted_at"] = deleted_at
        team["last_delete_reason"] = reason or team.get("last_delete_reason", "")
        cleanup_summary = {
            "members_closed": members_closed,
            "orphans_detected": orphans_detected,
            "errors": [],
            "mode": mode,
        }
        team["cleanup_summary"] = cleanup_summary
        self._save_team(team)

        active_index = self._read_active_index()
        team_name = team.get("team_name")
        if team_name and active_index.get("team_name_to_id", {}).get(team_name) == team_id:
            del active_index["team_name_to_id"][team_name]
            self._save_active_index(active_index)

        response = {
            "team_id": team_id,
            "status": "deleted",
            "deleted_at": deleted_at,
            "cleanup_summary": cleanup_summary,
        }
        self._message_bus_stub("team_delete", team_id)
        self._task_bus_stub("team_delete", team_id)
        self._append_event("team_delete_finalized", response)
        return response

    def team_member_add(
        self,
        team_id: str,
        agent_id: str,
        role: str = "member",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not team_id or not agent_id:
            raise ControlPlaneError("VALIDATION_ERROR", "team_id and agent_id are required")

        idempotency = self._read_idempotency()
        if idempotency_key:
            existing = idempotency.get("team_member_add", {}).get(idempotency_key)
            if existing:
                return existing["response"]

        team = self._load_team(team_id)
        status = str(team.get("status", ""))
        if status in {"deleting", "deleted"}:
            raise ControlPlaneError(
                "TEAM_NOT_MUTABLE",
                f"cannot add member to team with status: {status}",
            )

        for m in team.get("members", []):
            if m.get("agent_id") == agent_id:
                raise ControlPlaneError(
                    "MEMBER_ALREADY_EXISTS",
                    f"member already exists in team: {agent_id}",
                )

        now = utc_now_iso()
        new_member: Dict[str, Any] = {
            "agent_id": agent_id,
            "role": role,
            "lifecycle": "running",
            "joined_at": now,
        }
        team["members"].append(new_member)
        self._save_team(team)

        response: Dict[str, Any] = {
            "team_id": team_id,
            "agent_id": agent_id,
            "role": role,
            "lifecycle": "running",
            "joined_at": now,
        }

        if idempotency_key:
            idempotency.setdefault("team_member_add", {})[idempotency_key] = {
                "created_at": now,
                "team_id": team_id,
                "agent_id": agent_id,
                "response": response,
            }
            self._save_idempotency(idempotency)

        self._append_event("team_member_add", response)
        return response

    def team_member_remove(
        self,
        team_id: str,
        agent_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not team_id or not agent_id:
            raise ControlPlaneError("VALIDATION_ERROR", "team_id and agent_id are required")

        team = self._load_team(team_id)
        status = str(team.get("status", ""))
        if status == "deleted":
            raise ControlPlaneError("TEAM_NOT_FOUND", f"team is deleted: {team_id}")

        target: Optional[Dict[str, Any]] = None
        for m in team.get("members", []):
            if m.get("agent_id") == agent_id:
                target = m
                break

        if target is None:
            raise ControlPlaneError("MEMBER_NOT_FOUND", f"member not found in team: {agent_id}")

        if target.get("lifecycle") == "shutdown":
            return {
                "team_id": team_id,
                "agent_id": agent_id,
                "lifecycle": "shutdown",
                "already_removed": True,
            }

        is_leader = agent_id == team.get("leader_agent_id")
        if is_leader:
            raise ControlPlaneError(
                "LEADER_REMOVAL_NOT_ALLOWED",
                "leader removal is blocked to preserve leader invariants; use team_delete or leader handoff flow",
            )

        now = utc_now_iso()
        target["lifecycle"] = "shutdown"
        target["removed_at"] = now
        target["remove_reason"] = reason or ""
        self._save_team(team)

        response: Dict[str, Any] = {
            "team_id": team_id,
            "agent_id": agent_id,
            "lifecycle": "shutdown",
            "removed_at": now,
            "is_leader": False,
        }

        self._append_event("team_member_remove", response)
        return response

    def list_teams(self) -> Dict[str, Any]:
        teams: List[Dict[str, Any]] = []
        for team_file in sorted(self.teams_dir.glob("team-*.json")):
            with team_file.open("r", encoding="utf-8") as handle:
                teams.append(json.load(handle))
        return {"count": len(teams), "teams": teams}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal Team Control Plane PoC")
    parser.add_argument(
        "--store-root",
        default=str(Path.cwd() / ".runtime" / "control-plane"),
        help="Path to control-plane persistence directory",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("team-create", help="Create a team")
    create.add_argument("--team-name", required=True)
    create.add_argument("--description", default="")
    create.add_argument("--leader-agent-id")
    create.add_argument("--idempotency-key")

    member_add = subparsers.add_parser("member-add", help="Add a member to a team")
    member_add.add_argument("--team-id", required=True)
    member_add.add_argument("--agent-id", required=True)
    member_add.add_argument("--role", default="member")
    member_add.add_argument("--idempotency-key")

    member_remove = subparsers.add_parser("member-remove", help="Remove a member from a team")
    member_remove.add_argument("--team-id", required=True)
    member_remove.add_argument("--agent-id", required=True)
    member_remove.add_argument("--reason", default="")

    delete = subparsers.add_parser("team-delete", help="Delete a team")
    delete.add_argument("--team-id", required=True)
    delete.add_argument("--mode", default="graceful", choices=["graceful", "force"])
    delete.add_argument("--reason", default="")
    delete.add_argument(
        "--simulate-crash-after-marking-deleting",
        action="store_true",
        help="Test-only: leaves team in deleting to verify startup reconcile",
    )

    subparsers.add_parser("startup-reconcile", help="Finalize deleting teams found at startup")
    subparsers.add_parser("list-teams", help="List all persisted teams")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    plane = TeamControlPlane(store_root=Path(args.store_root))

    try:
        if args.command == "team-create":
            result = plane.team_create(
                team_name=args.team_name,
                description=args.description,
                leader_agent_id=args.leader_agent_id,
                idempotency_key=args.idempotency_key,
            )
        elif args.command == "team-delete":
            result = plane.team_delete(
                team_id=args.team_id,
                mode=args.mode,
                reason=args.reason,
                simulate_crash_after_marking_deleting=args.simulate_crash_after_marking_deleting,
            )
        elif args.command == "member-add":
            result = plane.team_member_add(
                team_id=args.team_id,
                agent_id=args.agent_id,
                role=args.role,
                idempotency_key=args.idempotency_key,
            )
        elif args.command == "member-remove":
            result = plane.team_member_remove(
                team_id=args.team_id,
                agent_id=args.agent_id,
                reason=args.reason,
            )
        elif args.command == "startup-reconcile":
            result = plane.startup_reconcile()
        elif args.command == "list-teams":
            result = plane.list_teams()
        else:
            parser.print_help()
            return 1
    except ControlPlaneError as error:
        print(json.dumps(error.to_dict(), ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
