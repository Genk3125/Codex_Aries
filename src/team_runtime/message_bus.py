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


@dataclass
class MessageBusError(Exception):
    code: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"error": self.code, "message": self.message}


class TeamMessageBus:
    """
    Minimal Team Message Bus PoC.
    Scope:
    - direct message
    - control message (minimal)
    - idempotency
    - per-recipient delivery state
    - startup reconcile for pending delivery
    Out of scope:
    - broadcast
    - approval workflow
    - task integration
    - remote trigger/UI
    """

    def __init__(self, store_root: Path, control_plane_store_root: Path):
        self.store_root = store_root
        self.messages_dir = self.store_root / "messages"
        self.idempotency_path = self.store_root / "idempotency.json"
        self.events_log_path = self.store_root / "message-events.log"
        self.control_plane = TeamControlPlane(control_plane_store_root)
        self._bootstrap_store()

    def _bootstrap_store(self) -> None:
        self.messages_dir.mkdir(parents=True, exist_ok=True)
        if not self.idempotency_path.exists():
            atomic_write_json(self.idempotency_path, {"schema_version": 1, "send_message": {}})
        if not self.events_log_path.exists():
            self.events_log_path.parent.mkdir(parents=True, exist_ok=True)
            self.events_log_path.touch()

    def _append_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {"ts": utc_now_iso(), "event_type": event_type, "payload": payload}
        with self.events_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def record_external_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        event = {
            "source": "external",
            "event_type": event_type,
            "payload": payload,
        }
        self._append_event("external_event", event)
        return {"recorded_at": utc_now_iso(), "event_type": event_type}

    def _message_file_path(self, message_id: str) -> Path:
        return self.messages_dir / f"message-{message_id}.json"

    def _save_message(self, message: Dict[str, Any]) -> None:
        message["updated_at"] = utc_now_iso()
        message["version"] = int(message.get("version", 0)) + 1
        atomic_write_json(self._message_file_path(message["message_id"]), message)

    def _load_message(self, message_id: str) -> Dict[str, Any]:
        message_path = self._message_file_path(message_id)
        if not message_path.exists():
            raise MessageBusError("MESSAGE_NOT_FOUND", f"message not found: {message_id}")
        with message_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _read_idempotency(self) -> Dict[str, Any]:
        return read_json_or_default(self.idempotency_path, {"schema_version": 1, "send_message": {}})

    def _save_idempotency(self, data: Dict[str, Any]) -> None:
        atomic_write_json(self.idempotency_path, data)

    def _parse_payload(self, payload_json: str) -> Dict[str, Any]:
        try:
            payload = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError as error:
            raise MessageBusError("VALIDATION_ERROR", f"invalid payload json: {error}") from error
        if not isinstance(payload, dict):
            raise MessageBusError("VALIDATION_ERROR", "payload must be a JSON object")
        return payload

    def _find_member(self, team: Dict[str, Any], member_id: str) -> Optional[Dict[str, Any]]:
        for member in team.get("members", []):
            if member.get("agent_id") == member_id:
                return member
        return None

    def _assert_team_sendable(self, team: Dict[str, Any]) -> None:
        status = str(team.get("status", ""))
        if status in {"deleting", "deleted"}:
            raise MessageBusError(
                "TEAM_NOT_SENDABLE",
                f"team status {status} cannot accept new messages",
            )

    def _new_delivery_state(self) -> Dict[str, Any]:
        return {
            "state": "pending",
            "attempt_count": 0,
            "last_attempt_at": None,
            "delivered_at": None,
            "error": None,
        }

    def _finalize_message_status(self, message: Dict[str, Any]) -> None:
        states = [str(v.get("state", "")) for v in message.get("delivery", {}).values()]
        if states and all(state == "delivered" for state in states):
            message["status"] = "delivered"
            return
        if any(state == "pending" for state in states):
            message["status"] = "pending"
            return
        if states and all(state == "rejected" for state in states):
            message["status"] = "rejected"
            return
        if states and all(state in {"failed", "rejected"} for state in states):
            message["status"] = "failed"
            return
        message["status"] = "partial"

    def _evaluate_recipient_delivery(
        self,
        message: Dict[str, Any],
        recipient_id: str,
        team: Dict[str, Any],
    ) -> None:
        delivery = message["delivery"][recipient_id]
        if delivery.get("state") != "pending":
            return

        delivery["attempt_count"] = int(delivery.get("attempt_count", 0)) + 1
        delivery["last_attempt_at"] = utc_now_iso()
        team_status = str(team.get("status", ""))

        if team_status in {"deleting", "deleted"}:
            delivery["state"] = "rejected"
            delivery["error"] = f"TEAM_NOT_SENDABLE:{team_status}"
            return

        recipient = self._find_member(team, recipient_id)
        if not recipient:
            delivery["state"] = "failed"
            delivery["error"] = "RECIPIENT_NOT_FOUND"
            return

        lifecycle = str(recipient.get("lifecycle", ""))
        if lifecycle in {"running", "idle"}:
            delivery["state"] = "delivered"
            delivery["delivered_at"] = utc_now_iso()
            delivery["error"] = None
            return
        if lifecycle in {"pending_init", "interrupted"}:
            delivery["state"] = "pending"
            delivery["error"] = f"RECIPIENT_TEMP_UNAVAILABLE:{lifecycle}"
            return

        delivery["state"] = "failed"
        delivery["error"] = f"RECIPIENT_NOT_DELIVERABLE:{lifecycle}"

    def _evaluate_message_delivery(self, message: Dict[str, Any], pending_only: bool = False) -> None:
        team_id = str(message.get("team_id"))
        try:
            team = self.control_plane.get_team(team_id)
            recipients = list(message.get("to_member_ids", []))
            for recipient_id in recipients:
                state = message["delivery"][recipient_id]["state"]
                if pending_only and state != "pending":
                    continue
                self._evaluate_recipient_delivery(message, recipient_id, team)
        except ControlPlaneError as error:
            for recipient_id, delivery in message.get("delivery", {}).items():
                if pending_only and delivery.get("state") != "pending":
                    continue
                delivery["attempt_count"] = int(delivery.get("attempt_count", 0)) + 1
                delivery["last_attempt_at"] = utc_now_iso()
                if error.code == "TEAM_NOT_FOUND":
                    delivery["state"] = "rejected"
                    delivery["error"] = "TEAM_NOT_FOUND"
                else:
                    delivery["state"] = "failed"
                    delivery["error"] = error.code

        self._finalize_message_status(message)
        self._save_message(message)

    def send_message(
        self,
        team_id: str,
        from_member_id: str,
        to_member_id: str,
        message_type: str,
        subtype: str,
        payload_json: str,
        idempotency_key: Optional[str] = None,
        defer_delivery: bool = False,
    ) -> Dict[str, Any]:
        if message_type not in {"direct", "control"}:
            raise MessageBusError("VALIDATION_ERROR", "message_type must be direct or control")
        if not team_id or not from_member_id or not to_member_id:
            raise MessageBusError("VALIDATION_ERROR", "team_id/from_member_id/to_member_id are required")

        payload = self._parse_payload(payload_json)
        idempotency = self._read_idempotency()
        if idempotency_key:
            existing = idempotency.get("send_message", {}).get(idempotency_key)
            if existing:
                return existing["response"]

        try:
            team = self.control_plane.get_team(team_id)
        except ControlPlaneError as error:
            raise MessageBusError(error.code, error.message) from error
        self._assert_team_sendable(team)

        sender = self._find_member(team, from_member_id)
        if not sender:
            raise MessageBusError("SENDER_NOT_FOUND", f"sender not found in team: {from_member_id}")

        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        message = {
            "schema_version": 1,
            "message_id": message_id,
            "team_id": team_id,
            "type": message_type,
            "subtype": subtype,
            "from_member_id": from_member_id,
            "to_member_ids": [to_member_id],
            "payload": payload,
            "created_at": now,
            "updated_at": now,
            "status": "pending",
            "delivery": {to_member_id: self._new_delivery_state()},
            "version": 0,
            "idempotency_key": idempotency_key or "",
        }
        self._save_message(message)

        if not defer_delivery:
            self._evaluate_message_delivery(message, pending_only=False)
        else:
            self._append_event(
                "message_delivery_deferred",
                {"message_id": message_id, "team_id": team_id, "to_member_id": to_member_id},
            )
            message = self._load_message(message_id)

        response = {
            "message_id": message["message_id"],
            "team_id": message["team_id"],
            "type": message["type"],
            "subtype": message["subtype"],
            "status": message["status"],
            "delivery": message["delivery"],
            "created_at": message["created_at"],
        }

        if idempotency_key:
            idempotency.setdefault("send_message", {})[idempotency_key] = {
                "created_at": now,
                "message_id": message_id,
                "response": response,
            }
            self._save_idempotency(idempotency)

        self._append_event("message_send", response)
        return response

    def startup_reconcile(self) -> Dict[str, Any]:
        updated_count = 0
        pending_before = 0
        pending_after = 0
        delivered_count = 0
        failed_or_rejected_count = 0
        updated_messages: List[str] = []

        for message_file in sorted(self.messages_dir.glob("message-*.json")):
            with message_file.open("r", encoding="utf-8") as handle:
                message = json.load(handle)

            states_before = [d.get("state") for d in message.get("delivery", {}).values()]
            pending_before += sum(1 for state in states_before if state == "pending")
            if not any(state == "pending" for state in states_before):
                continue

            self._evaluate_message_delivery(message, pending_only=True)
            message = self._load_message(message["message_id"])
            states_after = [d.get("state") for d in message.get("delivery", {}).values()]

            pending_after += sum(1 for state in states_after if state == "pending")
            delivered_count += sum(1 for state in states_after if state == "delivered")
            failed_or_rejected_count += sum(1 for state in states_after if state in {"failed", "rejected"})
            updated_count += 1
            updated_messages.append(message["message_id"])

        summary = {
            "reconciled_at": utc_now_iso(),
            "updated_message_count": updated_count,
            "pending_before": pending_before,
            "pending_after": pending_after,
            "delivered_count": delivered_count,
            "failed_or_rejected_count": failed_or_rejected_count,
            "updated_messages": updated_messages,
        }
        self._append_event("startup_reconcile", summary)
        return summary

    def list_messages(self, team_id: Optional[str] = None) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = []
        for message_file in sorted(self.messages_dir.glob("message-*.json")):
            with message_file.open("r", encoding="utf-8") as handle:
                message = json.load(handle)
            if team_id and message.get("team_id") != team_id:
                continue
            messages.append(message)
        return {"count": len(messages), "messages": messages}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal Team Message Bus PoC")
    parser.add_argument(
        "--store-root",
        default=str(Path.cwd() / ".runtime" / "message-bus"),
        help="Path to message-bus persistence directory",
    )
    parser.add_argument(
        "--control-plane-store-root",
        default=str(Path.cwd() / ".runtime" / "control-plane"),
        help="Path to control-plane persistence directory",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    direct = subparsers.add_parser("send-direct", help="Send minimal direct message")
    direct.add_argument("--team-id", required=True)
    direct.add_argument("--from-member-id", required=True)
    direct.add_argument("--to-member-id", required=True)
    direct.add_argument("--payload-json", default="{}")
    direct.add_argument("--idempotency-key")
    direct.add_argument("--defer-delivery", action="store_true")

    control = subparsers.add_parser("send-control", help="Send minimal control message")
    control.add_argument("--team-id", required=True)
    control.add_argument("--from-member-id", required=True)
    control.add_argument("--to-member-id", required=True)
    control.add_argument("--subtype", default="shutdown")
    control.add_argument("--payload-json", default="{}")
    control.add_argument("--idempotency-key")
    control.add_argument("--defer-delivery", action="store_true")

    reconcile = subparsers.add_parser("startup-reconcile", help="Re-evaluate pending deliveries")
    _ = reconcile

    list_messages = subparsers.add_parser("list-messages", help="List persisted messages")
    list_messages.add_argument("--team-id")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    bus = TeamMessageBus(
        store_root=Path(args.store_root),
        control_plane_store_root=Path(args.control_plane_store_root),
    )

    try:
        if args.command == "send-direct":
            result = bus.send_message(
                team_id=args.team_id,
                from_member_id=args.from_member_id,
                to_member_id=args.to_member_id,
                message_type="direct",
                subtype="text",
                payload_json=args.payload_json,
                idempotency_key=args.idempotency_key,
                defer_delivery=args.defer_delivery,
            )
        elif args.command == "send-control":
            result = bus.send_message(
                team_id=args.team_id,
                from_member_id=args.from_member_id,
                to_member_id=args.to_member_id,
                message_type="control",
                subtype=args.subtype,
                payload_json=args.payload_json,
                idempotency_key=args.idempotency_key,
                defer_delivery=args.defer_delivery,
            )
        elif args.command == "startup-reconcile":
            result = bus.startup_reconcile()
        elif args.command == "list-messages":
            result = bus.list_messages(team_id=args.team_id)
        else:
            parser.print_help()
            return 1
    except MessageBusError as error:
        print(json.dumps(error.to_dict(), ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
