#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from poc.codex_runtime_adapter import CodexRuntimeAdapter  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    temp_dir = Path(tempfile.mkdtemp(prefix="team-runtime-mvp-"))
    store_root = temp_dir / "store"

    try:
        adapter = CodexRuntimeAdapter(store_root=store_root)
        created = adapter.call(
            "team_create",
            {
                "team_name": "phase13-team-runtime-mvp",
                "description": "phase13 mvp test",
                "leader_agent_id": "leader_phase13",
                "idempotency_key": "phase13-team-create",
            },
        )
        team_id = str(created["team_id"])
        leader_id = str(created["leader_agent_id"])

        members = ["member_alpha", "member_bravo", "member_charlie"]
        for member in members:
            result = adapter.call(
                "team_member_add",
                {
                    "team_id": team_id,
                    "agent_id": member,
                    "role": "member",
                    "idempotency_key": f"phase13-member-add-{member}",
                },
            )
            assert_true(result["agent_id"] == member, f"member_add failed for {member}")

        task_ids = []
        for index, member in enumerate(members, start=1):
            task = adapter.call(
                "task_create",
                {
                    "team_id": team_id,
                    "title": f"phase13-task-{index}",
                    "description": "team runtime mvp test task",
                    "owner_member_id": member,
                    "state": "ready",
                    "idempotency_key": f"phase13-task-create-{index}",
                },
            )
            task_ids.append(str(task["task_id"]))

            message = adapter.call(
                "send_message",
                {
                    "team_id": team_id,
                    "from_member_id": leader_id,
                    "to_member_id": member,
                    "message_type": "direct",
                    "subtype": "text",
                    "payload": {"task_id": task["task_id"], "text": f"please handle phase13-task-{index}"},
                    "idempotency_key": f"phase13-message-{index}",
                },
            )
            delivery = message.get("delivery", {}).get(member, {})
            assert_true(delivery.get("state") == "delivered", f"message not delivered to {member}")

            moved = adapter.call(
                "task_update",
                {
                    "task_id": task["task_id"],
                    "state": "in_progress",
                    "idempotency_key": f"phase13-task-progress-{index}",
                },
            )
            assert_true(moved["state"] == "in_progress", f"task not moved in_progress: {task['task_id']}")

            done = adapter.call(
                "task_update",
                {
                    "task_id": task["task_id"],
                    "state": "done",
                    "result_reference": f"runs/phase13/task-{index}.md",
                    "idempotency_key": f"phase13-task-done-{index}",
                },
            )
            assert_true(done["state"] == "done", f"task not moved done: {task['task_id']}")

        listed = adapter.call("task_list", {"team_id": team_id, "state": "done"})
        assert_true(int(listed["count"]) == 3, "expected three done tasks")

        deleting = adapter.call(
            "team_delete",
            {
                "team_id": team_id,
                "mode": "graceful",
                "reason": "phase13-resume-check",
                "simulate_crash_after_marking_deleting": True,
            },
        )
        assert_true(deleting["status"] == "deleting", "team did not stay in deleting at crash point")

        resumed_adapter = CodexRuntimeAdapter(store_root=store_root)
        reconciled = resumed_adapter.call("runtime_reconcile_all", {})
        cp_cleaned = reconciled.get("control_plane", {}).get("cleaned_count")
        assert_true(cp_cleaned == 1, "startup reconcile did not finalize deleting team")

        final_team = resumed_adapter.call("team_list", {})
        teams = final_team.get("teams", [])
        matched = [team for team in teams if team.get("team_id") == team_id]
        assert_true(len(matched) == 1 and matched[0].get("status") == "deleted", "team was not deleted after reconcile")

        output = {
            "ok": True,
            "team_id": team_id,
            "leader_id": leader_id,
            "members": members,
            "task_ids": task_ids,
            "reconcile_summary": reconciled,
            "store_root": str(store_root),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

