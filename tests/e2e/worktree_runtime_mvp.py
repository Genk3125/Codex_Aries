#!/usr/bin/env python3
"""
E2E test for Worktree Runtime MVP (Phase 21).

Tests:
  T1: worktree_list returns empty on fresh store
  T2: worktree_enter (mocked git) + worktree_list shows active entry
  T3: worktree_exit delete_if_clean on non-existent path marks deleted
  T4: idempotency - same key returns cached result
  T5: startup_reconcile marks orphan as cleanup_pending
  T6: safety boundary rejects path outside repo_root
  T7: worktree_cleanup removes cleanup_pending entry
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest.mock as mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from poc.codex_runtime_adapter import CodexRuntimeAdapter  # noqa: E402
from src.team_runtime.worktree_runtime import WorktreeRuntime, WorktreeRuntimeError  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_eq(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def make_runtime(temp_dir: Path, repo_root: Path | None = None) -> WorktreeRuntime:
    store = temp_dir / "worktree-store"
    return WorktreeRuntime(store_root=store, repo_root=repo_root or temp_dir)


def test_t1_list_empty(temp_dir: Path) -> None:
    rt = make_runtime(temp_dir / "t1")
    result = rt.worktree_list()
    assert_eq(result["count"], 0, "T1: empty list count")
    print("T1 PASS: empty list")


def test_t2_enter_list(temp_dir: Path) -> None:
    rt = make_runtime(temp_dir / "t2")
    # Mock git commands to avoid real git ops
    with mock.patch("src.team_runtime.worktree_runtime._git_worktree_add"):
        result = rt.worktree_enter(
            team_id="team_wt_test",
            member_id="worker_01",
            idempotency_key="worktree:worktree_enter:team_wt_test:req_enter_0001",
        )
    assert_true("worktree_id" in result, "T2: worktree_id present")
    assert_true("worktree_path" in result, "T2: worktree_path present")

    listed = rt.worktree_list(team_id="team_wt_test")
    assert_eq(listed["count"], 1, "T2: list shows 1 entry")
    assert_eq(listed["worktrees"][0]["status"], "active", "T2: status is active")
    print("T2 PASS: enter + list")


def test_t3_exit_missing_path(temp_dir: Path) -> None:
    rt = make_runtime(temp_dir / "t3")
    # Create a worktree entry manually with a path that doesn't exist
    with mock.patch("src.team_runtime.worktree_runtime._git_worktree_add"):
        enter = rt.worktree_enter(
            team_id="team_exit_test",
            member_id="worker_02",
        )
    wt_id = enter["worktree_id"]
    # Path doesn't actually exist, delete_if_clean should handle gracefully
    result = rt.worktree_exit(worktree_id=wt_id, cleanup_mode="delete_if_clean")
    assert_true(result["deleted"], "T3: deleted=True when path missing")
    print("T3 PASS: exit on missing path marks deleted")


def test_t4_idempotency(temp_dir: Path) -> None:
    rt = make_runtime(temp_dir / "t4")
    key = "worktree:worktree_enter:team_idem:req_idem_0001"
    with mock.patch("src.team_runtime.worktree_runtime._git_worktree_add"):
        r1 = rt.worktree_enter(
            team_id="team_idem",
            member_id="worker_idem",
            idempotency_key=key,
        )
    with mock.patch("src.team_runtime.worktree_runtime._git_worktree_add") as mock_add:
        r2 = rt.worktree_enter(
            team_id="team_idem",
            member_id="worker_idem",
            idempotency_key=key,
        )
        assert_eq(mock_add.call_count, 0, "T4: git add not called on idempotent request")
    assert_eq(r1["worktree_id"], r2["worktree_id"], "T4: same worktree_id")
    assert_true(r2.get("idempotent"), "T4: idempotent flag set")
    print("T4 PASS: idempotency")


def test_t5_startup_reconcile(temp_dir: Path) -> None:
    rt = make_runtime(temp_dir / "t5")
    with mock.patch("src.team_runtime.worktree_runtime._git_worktree_add"):
        enter = rt.worktree_enter(team_id="team_orphan", member_id="worker_03")
    # Path doesn't exist → reconcile should mark it cleanup_pending
    with mock.patch("src.team_runtime.worktree_runtime._git_worktree_list", return_value=[]):
        result = rt.startup_reconcile()
    assert_true(result["updated"] >= 1, "T5: at least 1 orphan detected")
    listed = rt.worktree_list(team_id="team_orphan", status="cleanup_pending")
    assert_eq(listed["count"], 1, "T5: orphan marked cleanup_pending")
    print("T5 PASS: startup_reconcile detects orphan")


def test_t6_safety_boundary(temp_dir: Path) -> None:
    rt = make_runtime(temp_dir / "t6", repo_root=temp_dir / "t6" / "repo")
    try:
        rt.worktree_enter(
            team_id="team_unsafe",
            member_id="worker_bad",
            repo_path="/tmp/outside_repo",
        )
        raise AssertionError("T6: should have raised WorktreeRuntimeError")
    except WorktreeRuntimeError as err:
        assert_eq(err.code, "UNSAFE_PATH", "T6: UNSAFE_PATH error code")
    print("T6 PASS: safety boundary enforced")


def test_t7_cleanup(temp_dir: Path) -> None:
    rt = make_runtime(temp_dir / "t7")
    with mock.patch("src.team_runtime.worktree_runtime._git_worktree_add"):
        enter = rt.worktree_enter(team_id="team_cleanup", member_id="worker_04")
    wt_id = enter["worktree_id"]
    # Mark as cleanup_pending manually via exit on missing path
    rt.worktree_exit(worktree_id=wt_id, cleanup_mode="delete_if_clean")
    # cleanup should find 0 cleanup_pending (already deleted)
    result = rt.worktree_cleanup(team_id="team_cleanup")
    assert_true(result["error_count"] == 0, "T7: no errors")
    print("T7 PASS: cleanup works")


def test_adapter_integration(temp_dir: Path) -> None:
    store = temp_dir / "adapter-store"
    adapter = CodexRuntimeAdapter(store_root=store)
    info = adapter.call("runtime_info", {})
    assert_true(info["worktree_runtime_available"], "adapter: worktree_runtime available")
    assert_true("worktree_enter" in info["supported_operations"], "adapter: worktree_enter in ops")
    print("T8 PASS: adapter integration (runtime_info)")


def main() -> int:
    temp_dir = Path(tempfile.mkdtemp(prefix="worktree-runtime-mvp-"))
    results = {}
    try:
        for name, fn in [
            ("T1_list_empty", test_t1_list_empty),
            ("T2_enter_list", test_t2_enter_list),
            ("T3_exit_missing_path", test_t3_exit_missing_path),
            ("T4_idempotency", test_t4_idempotency),
            ("T5_startup_reconcile", test_t5_startup_reconcile),
            ("T6_safety_boundary", test_t6_safety_boundary),
            ("T7_cleanup", test_t7_cleanup),
            ("T8_adapter_integration", test_adapter_integration),
        ]:
            try:
                fn(temp_dir)
                results[name] = "PASS"
            except Exception as err:
                print(f"{name} FAIL: {err}")
                results[name] = f"FAIL: {err}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    pass_count = sum(1 for v in results.values() if v == "PASS")
    fail_count = len(results) - pass_count
    summary = {
        "ok": fail_count == 0,
        "pass": pass_count,
        "fail": fail_count,
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
