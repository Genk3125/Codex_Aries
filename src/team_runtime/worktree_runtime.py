#!/usr/bin/env python3
"""
Worktree Runtime Tools MVP — Phase 21.

Scope (in):
  worktree_enter / worktree_exit / worktree_cleanup / worktree_list
  safety boundary (repo root only, destructive requires explicit flag)
  idempotent create/attach
  state persistence + startup reconcile

Scope (out):
  task ownership / task state
  auto merge / auto stash / conflict resolution
  cross-repo worktree management
  persistent scheduler (Trigger Layer owns that)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .control_plane import atomic_write_json, read_json_or_default, utc_now_iso

WORKTREE_STATUSES = {"active", "detached", "cleanup_pending", "deleted"}
ACTIVE_STATUSES = {"active"}
CLEANUP_MODES = {"detach_only", "delete_if_clean", "force_delete"}

IDEMPOTENCY_KEY_PATTERN = re.compile(
    r"^(trigger|worktree|verifier_queue):[a-z][a-z0-9_]{2,31}:[a-z0-9][a-z0-9._-]{1,63}:[a-z0-9][a-z0-9._-]{7,63}$"
)


@dataclass
class WorktreeRuntimeError(Exception):
    code: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"error": self.code, "message": self.message}


def _validate_idempotency_key(key: Optional[str]) -> None:
    if key is None:
        return
    if not IDEMPOTENCY_KEY_PATTERN.match(key):
        raise WorktreeRuntimeError(
            "INVALID_IDEMPOTENCY_KEY",
            f"idempotency_key must match pattern: {IDEMPOTENCY_KEY_PATTERN.pattern}",
        )


def _worktree_id() -> str:
    return "wt_" + uuid.uuid4().hex[:12]


def _git_worktree_list(repo_root: Path) -> List[Dict[str, str]]:
    """Return list of {path, branch, head} from git worktree list."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    if result.returncode != 0:
        return []
    worktrees: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            if current:
                worktrees.append(current)
                current = {}
        elif line.startswith("worktree "):
            current["path"] = line[len("worktree "):]
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):]
        elif line == "bare":
            current["bare"] = "true"
    if current:
        worktrees.append(current)
    return worktrees


def _git_is_clean(worktree_path: Path) -> bool:
    """Return True if worktree has no uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0 and result.stdout.strip() == ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _git_worktree_add(repo_root: Path, path: Path, branch: str, base_ref: Optional[str]) -> None:
    cmd = ["git", "worktree", "add", str(path), branch]
    if base_ref:
        cmd = ["git", "worktree", "add", "-b", branch, str(path), base_ref]
    result = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise WorktreeRuntimeError(
            "GIT_WORKTREE_ADD_FAILED",
            f"git worktree add failed: {result.stderr.strip()}",
        )


def _git_worktree_attach(repo_root: Path, path: Path, branch: str) -> None:
    cmd = ["git", "worktree", "add", "--checkout", str(path), branch]
    result = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise WorktreeRuntimeError(
            "GIT_WORKTREE_ATTACH_FAILED",
            f"git worktree attach failed: {result.stderr.strip()}",
        )


def _git_worktree_remove(repo_root: Path, path: Path, force: bool = False) -> None:
    cmd = ["git", "worktree", "remove", str(path)]
    if force:
        cmd.append("--force")
    result = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise WorktreeRuntimeError(
            "GIT_WORKTREE_REMOVE_FAILED",
            f"git worktree remove failed: {result.stderr.strip()}",
        )


def _git_worktree_prune(repo_root: Path) -> None:
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=30,
    )


class WorktreeRuntime:
    """
    Minimal worktree runtime for Phase 21.

    Does NOT own task state, team state, merge decisions, or auto-stash.
    Provides: enter / exit / cleanup / list + startup reconcile.
    """

    def __init__(self, store_root: Path, repo_root: Optional[Path] = None):
        self.store_root = store_root
        self.worktrees_dir = self.store_root / "worktrees"
        self.idempotency_path = self.store_root / "idempotency.json"
        self.events_log = self.store_root / "worktree-events.log"
        self.repo_root = repo_root or self._detect_repo_root()
        self._init_store()

    def _detect_repo_root(self) -> Path:
        """Detect git repo root from CWD."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return Path.cwd()

    def _init_store(self) -> None:
        self.store_root.mkdir(parents=True, exist_ok=True)
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        if not self.idempotency_path.exists():
            atomic_write_json(self.idempotency_path, {"schema_version": 1, "keys": {}})

    def _log_event(self, event_type: str, payload: Any) -> None:
        entry = json.dumps(
            {"ts": utc_now_iso(), "event_type": event_type, "payload": payload},
            ensure_ascii=False,
        )
        with self.events_log.open("a", encoding="utf-8") as fh:
            fh.write(entry + "\n")

    def _wt_path(self, worktree_id: str) -> Path:
        return self.worktrees_dir / f"{worktree_id}.json"

    def _save_wt(self, wt: Dict[str, Any]) -> None:
        atomic_write_json(self._wt_path(wt["worktree_id"]), wt)

    def _load_wt(self, worktree_id: str) -> Optional[Dict[str, Any]]:
        p = self._wt_path(worktree_id)
        if not p.exists():
            return None
        return read_json_or_default(p, {})

    def _all_worktrees(self) -> Iterator[Dict[str, Any]]:
        for p in sorted(self.worktrees_dir.glob("wt_*.json")):
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

    def _validate_repo_boundary(self, path: Path) -> None:
        """Ensure path is under repo_root."""
        try:
            path.resolve().relative_to(self.repo_root.resolve())
        except ValueError:
            raise WorktreeRuntimeError(
                "UNSAFE_PATH",
                f"worktree path must be under repo root: {self.repo_root}",
            )

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    def worktree_enter(
        self,
        team_id: str,
        member_id: str,
        repo_path: Optional[str] = None,
        branch_name: Optional[str] = None,
        base_ref: Optional[str] = None,
        mode: str = "create",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enter (create or attach) a worktree for a team member.

        Out of scope: task ownership, auto-stash, merge decisions.
        Safety: refuses if team_status is deleting/deleted (caller must check).
        """
        _validate_idempotency_key(idempotency_key)
        hit = self._check_idempotency(idempotency_key)
        if hit:
            return {**hit["result"], "idempotent": True}

        if mode not in {"create", "attach"}:
            raise WorktreeRuntimeError("INVALID_MODE", "mode must be create|attach")

        # Determine worktree path
        effective_repo = Path(repo_path) if repo_path else self.repo_root
        self._validate_repo_boundary(effective_repo)

        auto_branch = f"codex/team-{team_id}/{member_id}"
        effective_branch = branch_name or auto_branch
        wt_path = effective_repo / ".worktrees" / team_id / member_id

        # Idempotency: same team+member already active?
        for existing in self._all_worktrees():
            if (
                existing.get("team_id") == team_id
                and existing.get("member_id") == member_id
                and existing.get("status") == "active"
            ):
                result = {
                    "worktree_id": existing["worktree_id"],
                    "worktree_path": existing["worktree_path"],
                    "branch_name": existing["branch_name"],
                    "attached": True,
                    "already_active": True,
                }
                self._record_idempotency(idempotency_key, result)
                return result

        worktree_id = _worktree_id()
        now = utc_now_iso()

        if mode == "create":
            _git_worktree_add(self.repo_root, wt_path, effective_branch, base_ref)
            attached = False
        else:
            _git_worktree_attach(self.repo_root, wt_path, effective_branch)
            attached = True

        wt: Dict[str, Any] = {
            "worktree_id": worktree_id,
            "schema_version": 1,
            "team_id": team_id,
            "member_id": member_id,
            "worktree_path": str(wt_path),
            "branch_name": effective_branch,
            "base_ref": base_ref,
            "mode": mode,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        self._save_wt(wt)
        self._log_event("worktree_entered", {"worktree_id": worktree_id, "team_id": team_id, "member_id": member_id})

        result = {
            "worktree_id": worktree_id,
            "worktree_path": str(wt_path),
            "branch_name": effective_branch,
            "attached": attached,
        }
        self._record_idempotency(idempotency_key, result)
        return result

    def worktree_exit(
        self,
        worktree_id: str,
        cleanup_mode: str = "delete_if_clean",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Exit a worktree. Detach, optionally delete.

        cleanup_mode:
          detach_only   — remove from git tracking only, files remain
          delete_if_clean — delete if no uncommitted changes (default)
          force_delete  — always delete (explicit flag required)

        Out of scope: auto-stash, auto-merge, task state updates.
        """
        _validate_idempotency_key(idempotency_key)
        hit = self._check_idempotency(idempotency_key)
        if hit:
            return {**hit["result"], "idempotent": True}

        if cleanup_mode not in CLEANUP_MODES:
            raise WorktreeRuntimeError("INVALID_CLEANUP_MODE", f"cleanup_mode must be one of {sorted(CLEANUP_MODES)}")

        wt = self._load_wt(worktree_id)
        if wt is None:
            raise WorktreeRuntimeError("WORKTREE_NOT_FOUND", f"worktree {worktree_id} not found")
        if wt.get("status") == "deleted":
            result = {"worktree_id": worktree_id, "detached": True, "deleted": True, "already_deleted": True, "cleanup_notes": "already deleted"}
            self._record_idempotency(idempotency_key, result)
            return result

        wt_path = Path(wt["worktree_path"])
        detached = False
        deleted = False
        cleanup_notes = ""

        if cleanup_mode == "detach_only":
            _git_worktree_prune(self.repo_root)
            detached = True
            cleanup_notes = "detach_only: files remain at path"
            wt["status"] = "detached"
        elif cleanup_mode == "delete_if_clean":
            if not wt_path.exists():
                cleanup_notes = "path already gone; marked deleted"
                deleted = True
                detached = True
            elif _git_is_clean(wt_path):
                _git_worktree_remove(self.repo_root, wt_path, force=False)
                detached = True
                deleted = True
                cleanup_notes = "clean worktree deleted"
            else:
                raise WorktreeRuntimeError(
                    "UNCOMMITTED_CHANGES",
                    f"worktree {worktree_id} has uncommitted changes; use force_delete to override",
                )
            wt["status"] = "deleted" if deleted else "detached"
        elif cleanup_mode == "force_delete":
            if wt_path.exists():
                _git_worktree_remove(self.repo_root, wt_path, force=True)
            _git_worktree_prune(self.repo_root)
            detached = True
            deleted = True
            cleanup_notes = "force_delete: path removed regardless of changes"
            wt["status"] = "deleted"

        wt["updated_at"] = utc_now_iso()
        self._save_wt(wt)
        self._log_event("worktree_exited", {"worktree_id": worktree_id, "cleanup_mode": cleanup_mode})

        result = {
            "worktree_id": worktree_id,
            "detached": detached,
            "deleted": deleted,
            "cleanup_notes": cleanup_notes,
        }
        self._record_idempotency(idempotency_key, result)
        return result

    def worktree_cleanup(
        self,
        team_id: Optional[str] = None,
        force: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Bulk cleanup: delete all cleanup_pending or detached worktrees.
        Optionally scoped to a team.

        Out of scope: task state, auto decisions. Caller decides scope.
        """
        _validate_idempotency_key(idempotency_key)
        hit = self._check_idempotency(idempotency_key)
        if hit:
            return {**hit["result"], "idempotent": True}

        cleaned: List[str] = []
        skipped: List[str] = []
        errors: List[str] = []

        for wt in self._all_worktrees():
            if team_id and wt.get("team_id") != team_id:
                continue
            if wt.get("status") not in {"cleanup_pending", "detached"}:
                continue

            wt_path = Path(wt["worktree_path"])
            wt_id = wt["worktree_id"]
            try:
                if not wt_path.exists():
                    wt["status"] = "deleted"
                    wt["updated_at"] = utc_now_iso()
                    self._save_wt(wt)
                    cleaned.append(wt_id)
                    continue
                if not force and not _git_is_clean(wt_path):
                    skipped.append(wt_id)
                    continue
                _git_worktree_remove(self.repo_root, wt_path, force=force)
                wt["status"] = "deleted"
                wt["updated_at"] = utc_now_iso()
                self._save_wt(wt)
                cleaned.append(wt_id)
            except WorktreeRuntimeError as err:
                errors.append(f"{wt_id}: {err.message}")

        _git_worktree_prune(self.repo_root)
        self._log_event("worktree_cleanup", {"cleaned": len(cleaned), "skipped": len(skipped), "errors": len(errors)})

        result = {
            "cleaned_count": len(cleaned),
            "skipped_count": len(skipped),
            "error_count": len(errors),
            "cleaned": cleaned,
            "skipped": skipped,
            "errors": errors,
        }
        self._record_idempotency(idempotency_key, result)
        return result

    def worktree_list(
        self,
        team_id: Optional[str] = None,
        status: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        """List tracked worktrees. Read-only."""
        worktrees = []
        for wt in self._all_worktrees():
            if not include_deleted and wt.get("status") == "deleted":
                continue
            if team_id and wt.get("team_id") != team_id:
                continue
            if status and wt.get("status") != status:
                continue
            worktrees.append(wt)
        return {"worktrees": worktrees, "count": len(worktrees)}

    def startup_reconcile(self) -> Dict[str, Any]:
        """
        Reconcile state on startup.
        - Finds worktrees marked active/detached whose paths no longer exist.
        - Marks them cleanup_pending.
        - Does NOT auto-delete (caller decides).
        - Does NOT touch task state or trigger state.
        """
        git_paths = {wt.get("path") for wt in _git_worktree_list(self.repo_root)}
        orphaned: List[str] = []
        updated: int = 0

        for wt in self._all_worktrees():
            if wt.get("status") not in {"active", "detached"}:
                continue
            wt_path = wt.get("worktree_path", "")
            path_exists = Path(wt_path).exists()
            in_git = wt_path in git_paths
            if not path_exists or not in_git:
                wt["status"] = "cleanup_pending"
                wt["updated_at"] = utc_now_iso()
                self._save_wt(wt)
                orphaned.append(wt["worktree_id"])
                updated += 1

        self._log_event("startup_reconcile", {"orphaned_count": len(orphaned), "orphaned": orphaned})
        return {"updated": updated, "orphaned": orphaned}


# ──────────────────────────────────────────────────────────────────────────────
# CLI (minimal, for testing)
# ──────────────────────────────────────────────────────────────────────────────

def _parse_json_arg(name: str, value: Optional[str]) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as err:
        raise WorktreeRuntimeError("INVALID_JSON", f"{name}: {err}") from err


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Worktree Runtime CLI")
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--repo-root")
    sub = parser.add_subparsers(dest="command")

    enter = sub.add_parser("enter")
    enter.add_argument("--team-id", required=True)
    enter.add_argument("--member-id", required=True)
    enter.add_argument("--repo-path")
    enter.add_argument("--branch-name")
    enter.add_argument("--base-ref")
    enter.add_argument("--mode", default="create", choices=["create", "attach"])
    enter.add_argument("--idempotency-key")

    exit_ = sub.add_parser("exit")
    exit_.add_argument("--worktree-id", required=True)
    exit_.add_argument("--cleanup-mode", default="delete_if_clean",
                       choices=["detach_only", "delete_if_clean", "force_delete"])
    exit_.add_argument("--idempotency-key")

    cleanup = sub.add_parser("cleanup")
    cleanup.add_argument("--team-id")
    cleanup.add_argument("--force", action="store_true")
    cleanup.add_argument("--idempotency-key")

    list_ = sub.add_parser("list")
    list_.add_argument("--team-id")
    list_.add_argument("--status")
    list_.add_argument("--include-deleted", action="store_true")

    sub.add_parser("reconcile")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    repo_root = Path(args.repo_root) if args.repo_root else None
    runtime = WorktreeRuntime(store_root=Path(args.store_root), repo_root=repo_root)

    try:
        if args.command == "enter":
            result = runtime.worktree_enter(
                team_id=args.team_id,
                member_id=args.member_id,
                repo_path=args.repo_path,
                branch_name=args.branch_name,
                base_ref=args.base_ref,
                mode=args.mode,
                idempotency_key=args.idempotency_key,
            )
        elif args.command == "exit":
            result = runtime.worktree_exit(
                worktree_id=args.worktree_id,
                cleanup_mode=args.cleanup_mode,
                idempotency_key=args.idempotency_key,
            )
        elif args.command == "cleanup":
            result = runtime.worktree_cleanup(
                team_id=args.team_id,
                force=args.force,
                idempotency_key=args.idempotency_key,
            )
        elif args.command == "list":
            result = runtime.worktree_list(
                team_id=args.team_id,
                status=args.status,
                include_deleted=args.include_deleted,
            )
        elif args.command == "reconcile":
            result = runtime.startup_reconcile()
        else:
            raise WorktreeRuntimeError("UNKNOWN_COMMAND", f"unknown command: {args.command}")
    except WorktreeRuntimeError as err:
        print(json.dumps({"ok": False, "error": err.to_dict()}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
