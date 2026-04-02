#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

from team_control_plane import TeamControlPlane, utc_now_iso
from team_message_bus import TeamMessageBus
from team_task_bus import TeamTaskBus


def _json_dumps(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _list_files(root: Path) -> List[str]:
    if not root.exists():
        return []
    return sorted(
        str(path)
        for path in root.rglob("*")
        if path.is_file()
    )


def _tail_events(path: Path, max_lines: int = 5) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    tail = lines[-max_lines:]
    result: List[Dict[str, Any]] = []
    for line in tail:
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            result.append({"raw": line})
    return result


def run_walkthrough(store_root: Path, reset: bool) -> Dict[str, Any]:
    cp_store = store_root / "control-plane"
    mb_store = store_root / "message-bus"
    tb_store = store_root / "task-bus"

    if reset and store_root.exists():
        shutil.rmtree(store_root)

    control_plane = TeamControlPlane(cp_store)
    message_bus = TeamMessageBus(
        store_root=mb_store,
        control_plane_store_root=cp_store,
    )
    task_bus = TeamTaskBus(
        store_root=tb_store,
        control_plane_store_root=cp_store,
        message_bus_store_root=mb_store,
    )

    steps: List[Dict[str, Any]] = []

    team_created = control_plane.team_create(
        team_name="walkthrough-team",
        description="runtime walkthrough spike",
        idempotency_key="walkthrough-team-create-1",
    )
    team_id = str(team_created["team_id"])
    leader_id = str(team_created["leader_agent_id"])
    steps.append({"step": "team_create", "result": team_created})

    task_created = task_bus.task_create(
        team_id=team_id,
        title="walkthrough task",
        description="created by runtime walkthrough",
        owner_member_id=leader_id,
        state="ready",
        idempotency_key="walkthrough-task-create-1",
    )
    task_id = str(task_created["task_id"])
    steps.append({"step": "task_create", "result": task_created})

    direct_message = message_bus.send_message(
        team_id=team_id,
        from_member_id=leader_id,
        to_member_id=leader_id,
        message_type="direct",
        subtype="text",
        payload_json='{"text":"walkthrough hello"}',
        idempotency_key="walkthrough-message-direct-1",
        defer_delivery=True,
    )
    message_id = str(direct_message["message_id"])
    steps.append({"step": "direct_message_send", "result": direct_message})

    task_updated = task_bus.task_update(
        task_id=task_id,
        state="in_progress",
        idempotency_key="walkthrough-task-update-1",
    )
    steps.append({"step": "task_state_update", "result": task_updated})

    team_delete_started = control_plane.team_delete(
        team_id=team_id,
        mode="graceful",
        reason="walkthrough_delete",
        simulate_crash_after_marking_deleting=True,
    )
    steps.append({"step": "team_delete_marked_deleting", "result": team_delete_started})

    cp_reconcile = control_plane.startup_reconcile()
    mb_reconcile = message_bus.startup_reconcile()
    tb_reconcile = task_bus.startup_reconcile_orphan_owners()
    steps.append(
        {
            "step": "startup_reconcile",
            "result": {
                "control_plane": cp_reconcile,
                "message_bus": mb_reconcile,
                "task_bus": tb_reconcile,
            },
        }
    )

    teams = control_plane.list_teams()
    messages = message_bus.list_messages(team_id=team_id)
    tasks = task_bus.task_list(team_id=team_id)

    summary = {
        "generated_at": utc_now_iso(),
        "walkthrough_scope": "control-plane + message-bus + task-bus",
        "flow_ids": {
            "team_id": team_id,
            "leader_id": leader_id,
            "task_id": task_id,
            "message_id": message_id,
        },
        "steps": steps,
        "snapshots": {
            "teams": teams,
            "messages": messages,
            "tasks": tasks,
        },
        "component_linkage_points": [
            "task_bus -> control_plane: owner/team status validation",
            "message_bus -> control_plane: send gate and recipient lifecycle check",
            "task_bus -> message_bus: optional external hint event (fail-open)",
            "startup_reconcile order: control_plane -> message_bus -> task_bus",
        ],
        "persistence": {
            "store_root": str(store_root),
            "files": _list_files(store_root),
            "event_tail": {
                "control_plane": _tail_events(cp_store / "team-events.log"),
                "message_bus": _tail_events(mb_store / "message-events.log"),
                "task_bus": _tail_events(tb_store / "task-events.log"),
            },
        },
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control+Message+Task minimal runtime walkthrough")
    parser.add_argument(
        "--store-root",
        default=str(Path.cwd() / ".runtime" / "walkthrough"),
        help="Walkthrough data root directory",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not cleanup existing store root before run",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to save JSON result",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    store_root = Path(args.store_root)
    result = run_walkthrough(store_root=store_root, reset=not args.no_reset)
    result_text = _json_dumps(result)
    print(result_text)

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result_text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
