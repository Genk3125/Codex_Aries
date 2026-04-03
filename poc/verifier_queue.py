#!/usr/bin/env python3
"""
Verifier Queue MVP — Phase 22.

Scope (in):
  verifier_request_create / get / list / claim_once
  idempotency (create)
  schema_version=1
  store at verifier-queue/
  strict/fail-open transparent via adapter

Scope (out):
  retry / priority / backoff
  verdict logic (stays in verifier_gate_helper.py / verifier-contract.md)
  second orchestrator behavior
  auto-scheduling
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from dataclasses import dataclass

from poc.verifier_gate_helper import utc_now_iso

try:
    from src.team_runtime.control_plane import atomic_write_json, read_json_or_default
except Exception:  # noqa: BLE001
    # Fallback for direct execution
    import os, sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.team_runtime.control_plane import atomic_write_json, read_json_or_default

REQUEST_STATUSES = {"requested", "running", "succeeded", "failed", "cancelled"}
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}

IDEMPOTENCY_KEY_PATTERN = re.compile(
    r"^(trigger|worktree|verifier_queue):[a-z][a-z0-9_]{2,31}:[a-z0-9][a-z0-9._-]{1,63}:[a-z0-9][a-z0-9._-]{7,63}$"
)


@dataclass
class VerifierQueueError(Exception):
    code: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"error": self.code, "message": self.message}


def _validate_idempotency_key(key: Optional[str]) -> None:
    if key is None:
        return
    if not IDEMPOTENCY_KEY_PATTERN.match(key):
        raise VerifierQueueError(
            "INVALID_IDEMPOTENCY_KEY",
            f"idempotency_key must match pattern: {IDEMPOTENCY_KEY_PATTERN.pattern}",
        )


def _request_id() -> str:
    return "vqr_" + uuid.uuid4().hex[:12]


class VerifierQueue:
    """
    Async verifier request queue.

    Single-pass: claim_once returns at most one unclaimed request.
    No retry, no priority, no auto-scheduling.
    Verdict logic stays in verifier_gate_helper / verifier-contract.
    """

    def __init__(self, store_root: Path):
        self.store_root = store_root
        self.requests_dir = self.store_root / "requests"
        self.idempotency_path = self.store_root / "idempotency.json"
        self.claim_index_path = self.store_root / "claim-index.json"
        self.events_log = self.store_root / "verifier-queue-events.log"
        self._init_store()

    def _init_store(self) -> None:
        self.store_root.mkdir(parents=True, exist_ok=True)
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        if not self.idempotency_path.exists():
            atomic_write_json(self.idempotency_path, {"schema_version": 1, "keys": {}})
        if not self.claim_index_path.exists():
            atomic_write_json(self.claim_index_path, {"schema_version": 1, "claimed": {}})

    def _log_event(self, event_type: str, payload: Any) -> None:
        entry = json.dumps(
            {"ts": utc_now_iso(), "event_type": event_type, "payload": payload},
            ensure_ascii=False,
        )
        with self.events_log.open("a", encoding="utf-8") as fh:
            fh.write(entry + "\n")

    def _req_path(self, request_id: str) -> Path:
        return self.requests_dir / f"{request_id}.json"

    def _save_req(self, req: Dict[str, Any]) -> None:
        atomic_write_json(self._req_path(req["request_id"]), req)

    def _load_req(self, request_id: str) -> Optional[Dict[str, Any]]:
        p = self._req_path(request_id)
        if not p.exists():
            return None
        return read_json_or_default(p, {})

    def _all_requests(self) -> Iterator[Dict[str, Any]]:
        for p in sorted(self.requests_dir.glob("vqr_*.json")):
            data = read_json_or_default(p, {})
            if data:
                yield data

    def _check_idempotency(self, key: Optional[str]) -> Optional[Dict[str, Any]]:
        if key is None:
            return None
        store = read_json_or_default(self.idempotency_path, {"schema_version": 1, "keys": {}})
        return store.get("keys", {}).get(key)

    def _record_idempotency(self, key: Optional[str], result: Dict[str, Any]) -> None:
        if key is None:
            return
        store = read_json_or_default(self.idempotency_path, {"schema_version": 1, "keys": {}})
        keys = store.setdefault("keys", {})
        keys[key] = {"result": result, "recorded_at": utc_now_iso()}
        atomic_write_json(self.idempotency_path, store)

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    def verifier_request_create(
        self,
        payload_ref: str,
        requester_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enqueue a verifier request.

        payload_ref: path or identifier pointing to the payload to verify.
        Does NOT invoke verifier — caller does that after claim_once.
        No retry, no priority.
        """
        _validate_idempotency_key(idempotency_key)
        hit = self._check_idempotency(idempotency_key)
        if hit:
            return {**hit["result"], "idempotent": True}

        rid = request_id or _request_id()
        now = utc_now_iso()
        req: Dict[str, Any] = {
            "request_id": rid,
            "schema_version": 1,
            "status": "requested",
            "payload_ref": str(payload_ref),
            "requester_id": requester_id or "",
            "context": context or {},
            "created_at": now,
            "updated_at": now,
            "claimed_at": None,
            "completed_at": None,
        }
        self._save_req(req)
        self._log_event("request_created", {"request_id": rid})

        result = {"request_id": rid, "status": "requested"}
        self._record_idempotency(idempotency_key, result)
        return result

    def verifier_request_get(self, request_id: str) -> Dict[str, Any]:
        """Return request by ID."""
        req = self._load_req(request_id)
        if req is None:
            raise VerifierQueueError("REQUEST_NOT_FOUND", f"request {request_id} not found")
        return req

    def verifier_request_list(
        self,
        status: Optional[str] = None,
        requester_id: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """List requests, optionally filtered. Read-only."""
        if status and status not in REQUEST_STATUSES:
            raise VerifierQueueError("INVALID_STATUS", f"status must be one of {sorted(REQUEST_STATUSES)}")
        requests = []
        for req in self._all_requests():
            if status and req.get("status") != status:
                continue
            if requester_id and req.get("requester_id") != requester_id:
                continue
            requests.append(req)
            if len(requests) >= limit:
                break
        return {"requests": requests, "count": len(requests)}

    def verifier_request_claim_once(
        self,
        claimer_id: str,
    ) -> Dict[str, Any]:
        """
        Claim one unclaimed 'requested' item atomically (single-pass).

        Returns {claimed: True, request: {...}} or {claimed: False}.
        No retry logic — caller runs verifier exactly once after claim.
        """
        claim_index = read_json_or_default(self.claim_index_path, {"schema_version": 1, "claimed": {}})
        claimed_ids = set(claim_index.get("claimed", {}).keys())

        for req in self._all_requests():
            rid = req.get("request_id", "")
            if req.get("status") != "requested":
                continue
            if rid in claimed_ids:
                continue
            # Claim it
            now = utc_now_iso()
            req["status"] = "running"
            req["claimed_at"] = now
            req["updated_at"] = now
            self._save_req(req)

            claim_index["claimed"][rid] = {"claimer_id": claimer_id, "claimed_at": now}
            atomic_write_json(self.claim_index_path, claim_index)
            self._log_event("request_claimed", {"request_id": rid, "claimer_id": claimer_id})
            return {"claimed": True, "request": req}

        return {"claimed": False, "request": None}

    def verifier_request_complete(
        self,
        request_id: str,
        outcome: str,
        result_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mark a running request as succeeded/failed/cancelled.
        Called by the claimer after executing the verifier.
        Outcome: succeeded | failed | cancelled
        """
        if outcome not in TERMINAL_STATUSES:
            raise VerifierQueueError("INVALID_OUTCOME", f"outcome must be one of {sorted(TERMINAL_STATUSES)}")
        req = self._load_req(request_id)
        if req is None:
            raise VerifierQueueError("REQUEST_NOT_FOUND", f"request {request_id} not found")
        if req.get("status") == outcome:
            return {**req, "already_completed": True}
        if req.get("status") not in {"running", "requested"}:
            raise VerifierQueueError(
                "INVALID_STATE_TRANSITION",
                f"cannot complete request in status={req['status']}",
            )
        now = utc_now_iso()
        req["status"] = outcome
        req["completed_at"] = now
        req["updated_at"] = now
        if result_ref:
            req["result_ref"] = result_ref
        self._save_req(req)
        self._log_event("request_completed", {"request_id": request_id, "outcome": outcome})
        return req
