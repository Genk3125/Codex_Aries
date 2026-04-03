#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from poc.codex_runtime_adapter import CodexRuntimeAdapter  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def utc_iso(seconds_offset: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds_offset)).isoformat()


def main() -> int:
    temp_dir = Path(tempfile.mkdtemp(prefix="trigger-layer-mvp-"))
    store_root = temp_dir / "store"

    try:
        adapter = CodexRuntimeAdapter(store_root=store_root)

        one_shot = adapter.call(
            "trigger_create",
            {
                "kind": "one_shot",
                "schedule": {"at": utc_iso(-10)},
                "target": {"team_id": "team_trigger_mvp", "task_id": "task_alpha"},
                "payload": {"title": "one-shot"},
                "idempotency_key": "trigger:trigger_create:team_trigger_mvp:req_create_one_shot",
            },
        )
        one_shot_dup = adapter.call(
            "trigger_create",
            {
                "kind": "one_shot",
                "schedule": {"at": utc_iso(-10)},
                "target": {"team_id": "team_trigger_mvp", "task_id": "task_alpha"},
                "payload": {"title": "one-shot"},
                "idempotency_key": "trigger:trigger_create:team_trigger_mvp:req_create_one_shot",
            },
        )
        assert_true(one_shot["trigger_id"] == one_shot_dup["trigger_id"], "idempotent trigger_create should return same trigger")

        recurring = adapter.call(
            "trigger_create",
            {
                "kind": "recurring",
                "schedule": {"interval_sec": 60, "start_at": utc_iso(-15)},
                "target": {"team_id": "team_trigger_mvp", "task_id": "task_beta"},
                "payload": {"title": "recurring"},
                "idempotency_key": "trigger:trigger_create:team_trigger_mvp:req_create_recurring",
            },
        )
        remote = adapter.call(
            "trigger_create",
            {
                "kind": "remote",
                "schedule": {},
                "target": {"team_id": "team_trigger_mvp", "task_id": "task_gamma"},
                "payload": {"title": "remote"},
                "idempotency_key": "trigger:trigger_create:team_trigger_mvp:req_create_remote_01",
            },
        )

        listed = adapter.call("trigger_list", {"team_id": "team_trigger_mvp"})
        assert_true(int(listed["count"]) == 3, "expected three triggers (idempotent duplicate excluded)")

        fire_result = adapter.call(
            "trigger_fire_due",
            {
                "idempotency_key": "trigger:trigger_fire_due:team_trigger_mvp:req_fire_due_0001",
                "max_count": 10,
            },
        )
        assert_true(int(fire_result["fired_count"]) == 2, "expected one_shot + recurring to fire")
        assert_true(int(fire_result["claimed_count"]) == 2, "claimed_count should match fired_count")
        assert_true(bool(fire_result["single_pass"]) is True, "trigger_fire_due must be single-pass")
        assert_true(len(fire_result["handoffs"]) == 2, "handoff count should match fired count")

        recurring_list = adapter.call("trigger_list", {"kind": "recurring", "team_id": "team_trigger_mvp"})
        assert_true(int(recurring_list["count"]) == 1, "recurring trigger should still exist")
        recurring_item = recurring_list["triggers"][0]
        assert_true(recurring_item["status"] == "scheduled", "recurring trigger should remain scheduled")
        assert_true(isinstance(recurring_item.get("next_run_at"), str), "recurring trigger should have next_run_at")
        assert_true(int(recurring_item.get("fire_count", 0)) == 1, "recurring trigger fire_count should be 1")

        deleted = adapter.call(
            "trigger_delete",
            {
                "trigger_id": recurring["trigger_id"],
                "reason": "cleanup-check",
                "idempotency_key": "trigger:trigger_delete:team_trigger_mvp:req_delete_recurring",
            },
        )
        assert_true(deleted["status"] == "cancelled", "trigger_delete should mark cancelled")

        fire_after_delete = adapter.call("trigger_fire_due", {"max_count": 10})
        assert_true(int(fire_after_delete["fired_count"]) == 0, "no due triggers should remain after delete")

        trigger_store = store_root / "trigger-layer"
        triggers_dir = trigger_store / "triggers"
        idempotency_path = trigger_store / "idempotency.json"
        events_log_path = trigger_store / "trigger-events.log"
        assert_true(trigger_store.exists(), "trigger-layer store root should exist")
        assert_true(triggers_dir.exists(), "trigger files dir should exist")
        assert_true(idempotency_path.exists(), "idempotency.json should exist")
        assert_true(events_log_path.exists(), "trigger-events.log should exist")

        idempotency = json.loads(idempotency_path.read_text(encoding="utf-8"))
        assert_true(int(idempotency.get("schema_version", 0)) == 1, "idempotency schema_version should be 1")
        assert_true("trigger_create" in idempotency, "idempotency.trigger_create should exist")
        assert_true("trigger_delete" in idempotency, "idempotency.trigger_delete should exist")
        assert_true("trigger_fire_due" in idempotency, "idempotency.trigger_fire_due should exist")

        events_lines = [line for line in events_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert_true(len(events_lines) >= 4, "expected trigger claim/fire/create/delete events to be recorded")

        output = {
            "ok": True,
            "store_root": str(store_root),
            "trigger_store": str(trigger_store),
            "created": {
                "one_shot": one_shot["trigger_id"],
                "recurring": recurring["trigger_id"],
                "remote": remote["trigger_id"],
            },
            "fire_due": {
                "fire_batch_id": fire_result["fire_batch_id"],
                "fired_count": fire_result["fired_count"],
                "handoff_count": len(fire_result["handoffs"]),
                "single_pass": fire_result["single_pass"],
            },
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
