#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .control_plane import atomic_write_json, read_json_or_default, utc_now_iso

TRIGGER_KINDS = {"one_shot", "recurring", "remote", "sleep"}
TRIGGER_STATUSES = {"scheduled", "running", "paused", "completed", "failed", "cancelled", "deleted"}
ACTIVE_STATUSES = {"scheduled", "running", "paused"}
IDEMPOTENCY_KEY_PATTERN = re.compile(
    r"^(trigger|worktree|verifier_queue):[a-z][a-z0-9_]{2,31}:[a-z0-9][a-z0-9._-]{1,63}:[a-z0-9][a-z0-9._-]{7,63}$"
)


def _parse_iso_to_utc(value: str, field_name: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"invalid {field_name}: {value}") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def _to_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _ensure_object(name: str, value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be object")
    return value


@dataclass
class TriggerLayerError(Exception):
    code: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"error": self.code, "message": self.message}


class TriggerLayer:
    """
    Trigger layer skeleton for Phase 20.
    Scope:
    - trigger_create
    - trigger_list
    - trigger_delete
    - trigger_fire_due (single-pass minimal)
    Out of scope:
    - polling loop
    - retry/priority/backoff
    - auth/approval policy
    """

    def __init__(self, store_root: Path):
        self.store_root = store_root
        self.triggers_dir = self.store_root / "triggers"
        self.idempotency_path = self.store_root / "idempotency.json"
        self.events_log_path = self.store_root / "trigger-events.log"
        self._bootstrap_store()

    def _bootstrap_store(self) -> None:
        self.triggers_dir.mkdir(parents=True, exist_ok=True)
        if not self.idempotency_path.exists():
            atomic_write_json(
                self.idempotency_path,
                {
                    "schema_version": 1,
                    "trigger_create": {},
                    "trigger_delete": {},
                    "trigger_fire_due": {},
                },
            )
        if not self.events_log_path.exists():
            self.events_log_path.parent.mkdir(parents=True, exist_ok=True)
            self.events_log_path.touch()

    def _append_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {"ts": utc_now_iso(), "event_type": event_type, "payload": payload}
        with self.events_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _trigger_file_path(self, trigger_id: str) -> Path:
        return self.triggers_dir / f"trigger-{trigger_id}.json"

    def _load_trigger(self, trigger_id: str) -> Dict[str, Any]:
        path = self._trigger_file_path(trigger_id)
        if not path.exists():
            raise TriggerLayerError("TRIGGER_NOT_FOUND", f"trigger not found: {trigger_id}")
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise TriggerLayerError("STORE_CORRUPTED", f"trigger file is invalid: {trigger_id}")
        return data

    def _save_trigger(self, trigger: Dict[str, Any]) -> None:
        trigger["schema_version"] = 1
        trigger["updated_at"] = utc_now_iso()
        trigger["version"] = int(trigger.get("version", 0)) + 1
        atomic_write_json(self._trigger_file_path(str(trigger["trigger_id"])), trigger)

    def _iter_triggers(self) -> Iterator[Dict[str, Any]]:
        for file_path in sorted(self.triggers_dir.glob("trigger-*.json")):
            with file_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                yield data

    def _read_idempotency(self) -> Dict[str, Any]:
        data = read_json_or_default(
            self.idempotency_path,
            {
                "schema_version": 1,
                "trigger_create": {},
                "trigger_delete": {},
                "trigger_fire_due": {},
            },
        )
        changed = False
        if not isinstance(data, dict):
            data = {}
            changed = True
        if data.get("schema_version") != 1:
            data["schema_version"] = 1
            changed = True
        for key in ("trigger_create", "trigger_delete", "trigger_fire_due"):
            if not isinstance(data.get(key), dict):
                data[key] = {}
                changed = True
        if changed:
            atomic_write_json(self.idempotency_path, data)
        return data

    def _save_idempotency(self, data: Dict[str, Any]) -> None:
        atomic_write_json(self.idempotency_path, data)

    def _normalize_schedule(self, kind: str, schedule: Dict[str, Any], now_dt: datetime) -> Tuple[Dict[str, Any], Optional[str]]:
        raw = dict(schedule)
        if kind in {"one_shot", "sleep"}:
            at_raw = raw.get("at")
            if not at_raw:
                at_raw = raw.get("due_at")
            if not at_raw:
                raise TriggerLayerError("VALIDATION_ERROR", "one_shot/sleep requires schedule.at (or due_at)")
            at_dt = _parse_iso_to_utc(str(at_raw), "schedule.at")
            normalized = {"at": _to_utc_iso(at_dt)}
            return normalized, normalized["at"]
        if kind == "recurring":
            interval = raw.get("interval_sec")
            if not isinstance(interval, int) or interval <= 0:
                raise TriggerLayerError("VALIDATION_ERROR", "recurring requires positive integer schedule.interval_sec")
            start_raw = raw.get("start_at")
            start_dt = now_dt if start_raw in {None, ""} else _parse_iso_to_utc(str(start_raw), "schedule.start_at")
            normalized = {
                "interval_sec": interval,
                "start_at": _to_utc_iso(start_dt),
            }
            return normalized, normalized["start_at"]
        if kind == "remote":
            next_raw = raw.get("next_run_at")
            if next_raw in {None, ""}:
                return {}, None
            next_dt = _parse_iso_to_utc(str(next_raw), "schedule.next_run_at")
            normalized = {"next_run_at": _to_utc_iso(next_dt)}
            return normalized, normalized["next_run_at"]
        raise TriggerLayerError("VALIDATION_ERROR", f"unsupported kind: {kind}")

    def _trigger_response(self, trigger: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "trigger_id": trigger["trigger_id"],
            "kind": trigger["kind"],
            "status": trigger["status"],
            "target": trigger.get("target", {}),
            "schedule": trigger.get("schedule", {}),
            "next_run_at": trigger.get("next_run_at"),
            "last_run_at": trigger.get("last_run_at"),
            "fire_count": int(trigger.get("fire_count", 0)),
            "deleted_at": trigger.get("deleted_at"),
            "schema_version": int(trigger.get("schema_version", 1)),
            "updated_at": trigger.get("updated_at"),
        }

    def _validate_idempotency_key(self, idempotency_key: Optional[str], operation_name: str) -> None:
        if idempotency_key is None:
            return
        if not IDEMPOTENCY_KEY_PATTERN.match(idempotency_key):
            raise TriggerLayerError(
                "VALIDATION_ERROR",
                f"idempotency_key format is invalid for {operation_name}",
            )

    def _due_check(self, trigger: Dict[str, Any], now_dt: datetime) -> Tuple[bool, Optional[datetime], str]:
        if str(trigger.get("status")) != "scheduled":
            return False, None, "status_not_scheduled"
        next_run_at = trigger.get("next_run_at")
        if not isinstance(next_run_at, str) or not next_run_at.strip():
            return False, None, "next_run_at_missing"
        try:
            due_dt = _parse_iso_to_utc(next_run_at, "next_run_at")
        except ValueError:
            return False, None, "next_run_at_invalid"
        if due_dt > now_dt:
            return False, due_dt, "not_due"
        return True, due_dt, "due"

    def _next_after_fire(self, trigger: Dict[str, Any], due_dt: datetime) -> Tuple[str, Optional[str]]:
        kind = str(trigger.get("kind"))
        if kind == "recurring":
            schedule = _ensure_object("schedule", trigger.get("schedule"))
            interval = int(schedule.get("interval_sec", 0))
            if interval <= 0:
                raise TriggerLayerError("STORE_CORRUPTED", "recurring trigger missing interval_sec")
            next_dt = due_dt + timedelta(seconds=interval)
            return "scheduled", _to_utc_iso(next_dt)
        return "completed", None

    def trigger_create(
        self,
        *,
        kind: str,
        schedule: Dict[str, Any],
        target: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        status: str = "scheduled",
        trigger_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if kind not in TRIGGER_KINDS:
            raise TriggerLayerError("VALIDATION_ERROR", f"kind must be one of {sorted(TRIGGER_KINDS)}")
        if status not in {"scheduled", "paused"}:
            raise TriggerLayerError("VALIDATION_ERROR", "status must be scheduled|paused on create")
        self._validate_idempotency_key(idempotency_key, "trigger_create")
        schedule_obj = _ensure_object("schedule", schedule)
        target_obj = _ensure_object("target", target)
        payload_obj = _ensure_object("payload", payload)

        idempotency = self._read_idempotency()
        if idempotency_key:
            existing = idempotency["trigger_create"].get(idempotency_key)
            if existing:
                return existing["response"]

        now_dt = datetime.now(timezone.utc)
        normalized_schedule, next_run_at = self._normalize_schedule(kind, schedule_obj, now_dt)
        trigger_id_value = trigger_id or f"trg_{uuid.uuid4().hex[:12]}"
        if self._trigger_file_path(trigger_id_value).exists():
            raise TriggerLayerError("TRIGGER_ALREADY_EXISTS", f"trigger already exists: {trigger_id_value}")

        now_text = _to_utc_iso(now_dt)
        trigger = {
            "schema_version": 1,
            "trigger_id": trigger_id_value,
            "kind": kind,
            "status": status,
            "target": target_obj,
            "payload": payload_obj,
            "schedule": normalized_schedule,
            "next_run_at": next_run_at,
            "last_run_at": None,
            "last_claim_at": None,
            "created_at": now_text,
            "updated_at": now_text,
            "deleted_at": None,
            "version": 0,
            "fire_count": 0,
            "idempotency_key_create": idempotency_key or "",
            "last_handoff": None,
        }
        self._save_trigger(trigger)
        response = self._trigger_response(trigger)

        if idempotency_key:
            idempotency["trigger_create"][idempotency_key] = {
                "created_at": now_text,
                "trigger_id": trigger_id_value,
                "response": response,
            }
            self._save_idempotency(idempotency)

        self._append_event("trigger_create", {"trigger_id": trigger_id_value, "kind": kind, "status": status})
        return response

    def trigger_list(
        self,
        *,
        status: Optional[str] = None,
        kind: Optional[str] = None,
        team_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        if status and status not in TRIGGER_STATUSES:
            raise TriggerLayerError("VALIDATION_ERROR", f"invalid status: {status}")
        if kind and kind not in TRIGGER_KINDS:
            raise TriggerLayerError("VALIDATION_ERROR", f"invalid kind: {kind}")

        entries: List[Dict[str, Any]] = []
        for trigger in self._iter_triggers():
            trigger_status = str(trigger.get("status", ""))
            if not include_deleted and trigger_status == "deleted":
                continue
            if status and trigger_status != status:
                continue
            if kind and str(trigger.get("kind")) != kind:
                continue
            if team_id:
                target = trigger.get("target")
                if not isinstance(target, dict) or str(target.get("team_id", "")) != str(team_id):
                    continue
            entries.append(self._trigger_response(trigger))

        entries.sort(key=lambda item: (item.get("next_run_at") is None, str(item.get("next_run_at") or ""), item["trigger_id"]))
        return {"count": len(entries), "triggers": entries}

    def trigger_delete(
        self,
        *,
        trigger_id: str,
        reason: str = "",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not trigger_id:
            raise TriggerLayerError("VALIDATION_ERROR", "trigger_id is required")
        self._validate_idempotency_key(idempotency_key, "trigger_delete")

        idempotency = self._read_idempotency()
        if idempotency_key:
            existing = idempotency["trigger_delete"].get(idempotency_key)
            if existing:
                return existing["response"]

        trigger = self._load_trigger(trigger_id)
        already_cancelled = str(trigger.get("status")) in {"cancelled", "deleted"}
        now_text = utc_now_iso()

        if not already_cancelled:
            trigger["status"] = "cancelled"
            trigger["next_run_at"] = None
            trigger["deleted_at"] = now_text
            trigger["delete_reason"] = reason
            self._save_trigger(trigger)
            self._append_event(
                "trigger_delete",
                {"trigger_id": trigger_id, "reason": reason, "status": trigger["status"]},
            )

        response = {
            "trigger_id": trigger_id,
            "status": str(trigger.get("status")),
            "deleted_at": trigger.get("deleted_at"),
            "already_cancelled": already_cancelled,
        }
        if idempotency_key:
            idempotency["trigger_delete"][idempotency_key] = {
                "created_at": now_text,
                "trigger_id": trigger_id,
                "response": response,
            }
            self._save_idempotency(idempotency)
        return response

    def trigger_fire_due(
        self,
        *,
        now_iso: Optional[str] = None,
        max_count: int = 100,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if max_count <= 0:
            raise TriggerLayerError("VALIDATION_ERROR", "max_count must be > 0")
        self._validate_idempotency_key(idempotency_key, "trigger_fire_due")

        idempotency = self._read_idempotency()
        if idempotency_key:
            existing = idempotency["trigger_fire_due"].get(idempotency_key)
            if existing:
                return existing["response"]

        now_dt = datetime.now(timezone.utc) if not now_iso else _parse_iso_to_utc(now_iso, "now_iso")
        now_text = _to_utc_iso(now_dt)
        fire_batch_id = f"fire_{uuid.uuid4().hex[:12]}"

        records = list(self._iter_triggers())
        records.sort(key=lambda item: (item.get("next_run_at") is None, str(item.get("next_run_at") or ""), str(item.get("trigger_id") or "")))

        fired: List[Dict[str, Any]] = []
        handoffs: List[Dict[str, Any]] = []
        checked_count = 0
        skipped_count = 0

        for trigger in records:
            checked_count += 1
            if len(fired) >= max_count:
                break
            due, due_dt, reason = self._due_check(trigger, now_dt)
            if not due or due_dt is None:
                skipped_count += 1
                if reason == "next_run_at_invalid":
                    self._append_event(
                        "trigger_fire_skip_invalid_next_run_at",
                        {"trigger_id": trigger.get("trigger_id"), "next_run_at": trigger.get("next_run_at")},
                    )
                continue

            trigger_id = str(trigger["trigger_id"])
            status_before = str(trigger.get("status"))
            claim_id = f"claim_{uuid.uuid4().hex[:10]}"

            trigger["status"] = "running"
            trigger["last_claim_at"] = now_text
            self._save_trigger(trigger)
            self._append_event(
                "trigger_claim",
                {
                    "fire_batch_id": fire_batch_id,
                    "claim_id": claim_id,
                    "trigger_id": trigger_id,
                    "due_at": _to_utc_iso(due_dt),
                    "claimed_at": now_text,
                },
            )

            status_after, next_run_at = self._next_after_fire(trigger, due_dt)
            handoff = {
                "handoff_id": f"handoff_{uuid.uuid4().hex[:12]}",
                "fire_batch_id": fire_batch_id,
                "claim_id": claim_id,
                "trigger_id": trigger_id,
                "kind": str(trigger.get("kind")),
                "target": trigger.get("target", {}),
                "payload": trigger.get("payload", {}),
                "due_at": _to_utc_iso(due_dt),
                "claimed_at": now_text,
                "fired_at": now_text,
                "single_pass": True,
            }

            trigger["status"] = status_after
            trigger["last_run_at"] = now_text
            trigger["next_run_at"] = next_run_at
            trigger["fire_count"] = int(trigger.get("fire_count", 0)) + 1
            trigger["last_handoff"] = handoff
            self._save_trigger(trigger)

            self._append_event(
                "trigger_fire",
                {
                    "fire_batch_id": fire_batch_id,
                    "claim_id": claim_id,
                    "trigger_id": trigger_id,
                    "status_before": status_before,
                    "status_after": status_after,
                    "next_run_at": next_run_at,
                },
            )

            fired.append(
                {
                    "trigger_id": trigger_id,
                    "kind": str(trigger.get("kind")),
                    "status_before": status_before,
                    "status_after": status_after,
                    "due_at": _to_utc_iso(due_dt),
                    "next_run_at": next_run_at,
                    "claim_id": claim_id,
                    "handoff_id": handoff["handoff_id"],
                }
            )
            handoffs.append(handoff)

        response = {
            "fire_batch_id": fire_batch_id,
            "single_pass": True,
            "now": now_text,
            "checked_count": checked_count,
            "skipped_count": skipped_count,
            "claimed_count": len(fired),
            "fired_count": len(fired),
            "max_count": max_count,
            "truncated": len(fired) >= max_count,
            "fired": fired,
            "handoffs": handoffs,
        }
        self._append_event(
            "trigger_fire_due_summary",
            {
                "fire_batch_id": fire_batch_id,
                "checked_count": checked_count,
                "fired_count": len(fired),
                "skipped_count": skipped_count,
                "max_count": max_count,
            },
        )

        if idempotency_key:
            idempotency["trigger_fire_due"][idempotency_key] = {
                "created_at": now_text,
                "fire_batch_id": fire_batch_id,
                "response": response,
            }
            self._save_idempotency(idempotency)
        return response


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trigger layer CLI (Phase 20 skeleton)")
    parser.add_argument(
        "--store-root",
        default=os.environ.get("CODEX_TRIGGER_STORE_ROOT", str(Path.cwd() / ".runtime" / "trigger-layer")),
        help="Trigger layer store root",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--kind", required=True)
    create.add_argument("--schedule-json", required=True)
    create.add_argument("--target-json", default="{}")
    create.add_argument("--payload-json", default="{}")
    create.add_argument("--status", default="scheduled")
    create.add_argument("--trigger-id", default="")
    create.add_argument("--idempotency-key", default="")

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--status", default="")
    list_cmd.add_argument("--kind", default="")
    list_cmd.add_argument("--team-id", default="")
    list_cmd.add_argument("--include-deleted", action="store_true")

    delete = sub.add_parser("delete")
    delete.add_argument("--trigger-id", required=True)
    delete.add_argument("--reason", default="")
    delete.add_argument("--idempotency-key", default="")

    fire = sub.add_parser("fire-due")
    fire.add_argument("--now-iso", default="")
    fire.add_argument("--max-count", type=int, default=100)
    fire.add_argument("--idempotency-key", default="")
    return parser


def _parse_json_arg(name: str, value: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise TriggerLayerError("VALIDATION_ERROR", f"invalid {name}: {error}") from error
    if not isinstance(parsed, dict):
        raise TriggerLayerError("VALIDATION_ERROR", f"{name} must be object json")
    return parsed


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    layer = TriggerLayer(Path(args.store_root))

    try:
        if args.command == "create":
            result = layer.trigger_create(
                kind=str(args.kind),
                schedule=_parse_json_arg("schedule_json", args.schedule_json),
                target=_parse_json_arg("target_json", args.target_json),
                payload=_parse_json_arg("payload_json", args.payload_json),
                status=str(args.status),
                trigger_id=args.trigger_id or None,
                idempotency_key=args.idempotency_key or None,
            )
        elif args.command == "list":
            result = layer.trigger_list(
                status=args.status or None,
                kind=args.kind or None,
                team_id=args.team_id or None,
                include_deleted=bool(args.include_deleted),
            )
        elif args.command == "delete":
            result = layer.trigger_delete(
                trigger_id=str(args.trigger_id),
                reason=str(args.reason),
                idempotency_key=args.idempotency_key or None,
            )
        elif args.command == "fire-due":
            result = layer.trigger_fire_due(
                now_iso=args.now_iso or None,
                max_count=int(args.max_count),
                idempotency_key=args.idempotency_key or None,
            )
        else:
            raise TriggerLayerError("UNKNOWN_COMMAND", f"unknown command: {args.command}")
    except TriggerLayerError as error:
        print(json.dumps({"ok": False, "error": error.to_dict()}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
