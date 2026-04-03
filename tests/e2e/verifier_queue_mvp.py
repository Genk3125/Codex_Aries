#!/usr/bin/env python3
"""E2E test for Verifier Queue MVP (Phase 22)."""
from __future__ import annotations
import json, shutil, sys, tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from poc.codex_runtime_adapter import CodexRuntimeAdapter
from poc.verifier_queue import VerifierQueue, VerifierQueueError


def ok(c, m): assert c, m
def eq(a, e, m): assert a == e, f"{m}: expected {e!r}, got {a!r}"

def make_vq(tmp): return VerifierQueue(tmp / "vq-store")


def t1_create_list(tmp):
    vq = make_vq(tmp / "t1")
    r = vq.verifier_request_create(payload_ref="runs/abc/orch.json", requester_id="gate_01",
        idempotency_key="verifier_queue:verifier_request_create:task_abc:req_verify_0001")
    ok("request_id" in r, "T1: request_id present")
    listed = vq.verifier_request_list()
    eq(listed["count"], 1, "T1: list count")
    eq(listed["requests"][0]["status"], "requested", "T1: status=requested")
    print("T1 PASS: create+list")


def t2_claim_once(tmp):
    vq = make_vq(tmp / "t2")
    vq.verifier_request_create(payload_ref="runs/t2/orch.json")
    c = vq.verifier_request_claim_once(claimer_id="worker_verifier")
    ok(c["claimed"], "T2: claimed=True")
    eq(c["request"]["status"], "running", "T2: status=running")
    c2 = vq.verifier_request_claim_once(claimer_id="worker_verifier_2")
    ok(not c2["claimed"], "T2: second claim returns claimed=False")
    print("T2 PASS: claim_once single-pass")


def t3_complete(tmp):
    vq = make_vq(tmp / "t3")
    vq.verifier_request_create(payload_ref="runs/t3/orch.json")
    c = vq.verifier_request_claim_once(claimer_id="w1")
    rid = c["request"]["request_id"]
    result = vq.verifier_request_complete(request_id=rid, outcome="succeeded", result_ref="runs/t3/verdict.json")
    eq(result["status"], "succeeded", "T3: status=succeeded")
    eq(result.get("result_ref"), "runs/t3/verdict.json", "T3: result_ref set")
    print("T3 PASS: complete")


def t4_idempotency(tmp):
    vq = make_vq(tmp / "t4")
    key = "verifier_queue:verifier_request_create:task_idem:req_idem_0001"
    r1 = vq.verifier_request_create(payload_ref="runs/idem/orch.json", idempotency_key=key)
    r2 = vq.verifier_request_create(payload_ref="runs/idem/orch.json", idempotency_key=key)
    eq(r1["request_id"], r2["request_id"], "T4: same request_id")
    ok(r2.get("idempotent"), "T4: idempotent flag")
    eq(vq.verifier_request_list()["count"], 1, "T4: only 1 entry")
    print("T4 PASS: idempotency")


def t5_invalid_key(tmp):
    vq = make_vq(tmp / "t5")
    try:
        vq.verifier_request_create(payload_ref="x", idempotency_key="bad_key")
        raise AssertionError("T5: should raise")
    except VerifierQueueError as e:
        eq(e.code, "INVALID_IDEMPOTENCY_KEY", "T5: error code")
    print("T5 PASS: invalid key rejected")


def t6_adapter(tmp):
    a = CodexRuntimeAdapter(store_root=tmp / "adapter-store")
    info = a.call("runtime_info", {})
    ok(info["worktree_runtime_available"], "T6: worktree available")
    ok("verifier_request_create" in info["supported_operations"], "T6: vq ops in adapter")
    r = a.call("verifier_request_create", {"payload_ref": "runs/adapter/orch.json", "requester_id": "gate"})
    ok("request_id" in r, "T6: adapter create ok")
    c = a.call("verifier_request_claim_once", {"claimer_id": "w1"})
    ok(c["claimed"], "T6: adapter claim ok")
    done = a.call("verifier_request_complete", {"request_id": c["request"]["request_id"], "outcome": "succeeded"})
    eq(done["status"], "succeeded", "T6: adapter complete ok")
    print("T6 PASS: adapter integration")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="vq-mvp-"))
    results = {}
    try:
        for name, fn in [("T1", t1_create_list), ("T2", t2_claim_once), ("T3", t3_complete),
                         ("T4", t4_idempotency), ("T5", t5_invalid_key), ("T6", t6_adapter)]:
            try:
                fn(tmp)
                results[name] = "PASS"
            except Exception as e:
                print(f"{name} FAIL: {e}")
                results[name] = f"FAIL: {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    p = sum(1 for v in results.values() if v == "PASS")
    summary = {"ok": p == len(results), "pass": p, "fail": len(results)-p, "results": results}
    print(json.dumps(summary, indent=2))
    return 0 if p == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
