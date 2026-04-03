from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .control_plane import TeamControlPlane
from .message_bus import TeamMessageBus
from .task_bus import TeamTaskBus


class TeamRuntime:
    """
    Thin runtime façade for Team Control Plane + Message Bus + Task Bus.
    This class keeps existing PoC API behavior while providing a stable
    import point for non-PoC callers.
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

    def startup_reconcile_all(self) -> Dict[str, Any]:
        return {
            "control_plane": self.control_plane.startup_reconcile(),
            "message_bus": self.message_bus.startup_reconcile(),
            "task_bus": self.task_bus.startup_reconcile_orphan_owners(),
        }

