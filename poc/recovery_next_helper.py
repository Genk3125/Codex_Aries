#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_json_file(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("input json must be an object")
    return data


def normalize_stop_reasons(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    normalized: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value:
            continue
        if value not in normalized:
            normalized.append(value)
    return normalized


def pick_guard_view(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {
            "enabled": False,
            "ok": False,
            "decision": None,
            "stop_reasons": [],
        }
    return {
        "enabled": bool(raw.get("enabled", False)),
        "ok": bool(raw.get("ok", False)),
        "decision": raw.get("decision"),
        "stop_reasons": normalize_stop_reasons(raw.get("stop_reasons")),
    }


def map_reason_to_branch(reason: str, source: str, playbook_path: str) -> Dict[str, Any]:
    mapping: Dict[str, Dict[str, Any]] = {
        "manual_stop": {
            "branch_id": "manual-stop-review",
            "sections": ["5. Stop Conditions", "8. 自動化しにくい判断"],
            "title": "Manual stop の解除可否をレビューする",
            "next_actions": [
                "停止継続か再開かを operator が判断する。",
                "再開する場合は guard state の manual_stop を false に戻す。",
                "再開理由をログ化して単発 run を手動再開する。",
            ],
        },
        "max_retries": {
            "branch_id": "max-retries-escalate",
            "sections": ["3.3 Escalate", "4. Failure Taxonomy", "5. Stop Conditions"],
            "title": "最大試行到達として escalation する",
            "next_actions": [
                "失敗を taxonomy で分類する。",
                "試した修正・実行コマンド・実出力を添えて escalation パッケージを作る。",
                "coordinator が次の打ち手を決めるまで run を再開しない。",
            ],
        },
        "strict_failure": {
            "branch_id": "strict-failure-verify",
            "sections": ["3.1 First Retry", "3.2 Independent Verify", "5. Stop Conditions"],
            "title": "strict 失敗の証跡を固定して独立検証へ渡す",
            "next_actions": [
                "失敗コマンドと出力を固定する。",
                "verifier に read-only 検証を依頼する。",
                "最小修正のみで次の単発 run を準備する。",
            ],
        },
        "escalated": {
            "branch_id": "escalated-review",
            "sections": ["3.3 Escalate", "6. Coordinator / Verifier 接続"],
            "title": "escalation 経路へ移行する",
            "next_actions": [
                "第2失敗以降として escalation を確定する。",
                "coordinator に仮説と次の打ち手を渡す。",
                "verifier 実行の要否を分離して判断する。",
            ],
        },
        "already_stopped": {
            "branch_id": "already-stopped-review",
            "sections": ["5. Stop Conditions", "6. Coordinator / Verifier 接続"],
            "title": "既存 stop 判定を解除せずにレビューする",
            "next_actions": [
                "前回 stop の理由と証跡を確認する。",
                "解除条件を満たすまで guard state を維持する。",
                "解除後のみ新しい run を開始する。",
            ],
        },
        "success": {
            "branch_id": "success-stop-closeout",
            "sections": ["7. 運用ルール"],
            "title": "成功停止としてクローズ処理を行う",
            "next_actions": [
                "成功結果と residual risk を記録する。",
                "この run の復旧操作は実行しない。",
                "次タスク開始前に必要なら baseline を更新する。",
            ],
        },
    }
    entry = mapping.get(reason)
    if entry is None:
        entry = {
            "branch_id": "unknown-reason-review",
            "sections": ["4. Failure Taxonomy", "8. 自動化しにくい判断"],
            "title": "未知の stop reason を分類する",
            "next_actions": [
                "stop reason を taxonomy に再分類する。",
                "分類不能なら UNKNOWN として escalation へ渡す。",
                "同一理由での再実行は新情報が出るまで止める。",
            ],
        }

    return {
        "reason": reason,
        "source": source,
        "branch_id": entry["branch_id"],
        "playbook_ref": {
            "path": playbook_path,
            "sections": entry["sections"],
        },
        "template": {
            "title": entry["title"],
            "next_actions": entry["next_actions"],
            "required_artifacts": [
                "executed_commands",
                "actual_outputs",
                "failure_taxonomy",
                "next_hypothesis",
            ],
        },
    }


def summarize_guards(source: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    preflight = pick_guard_view(source.get("preflight_guard"))
    post_run = pick_guard_view(source.get("guard"))

    details: List[Dict[str, Any]] = []
    if preflight.get("decision") == "stop":
        for reason in preflight.get("stop_reasons", []):
            details.append({"reason": reason, "source": "preflight_guard"})
    if post_run.get("decision") == "stop":
        for reason in post_run.get("stop_reasons", []):
            details.append({"reason": reason, "source": "post_run_guard"})

    summary = {
        "preflight_guard": preflight,
        "post_run_guard": post_run,
        "stop_detected": len(details) > 0,
        "stop_reason_details": details,
        "note": "Guard summary mirrors orchestrator output; this helper does not create new stop criteria.",
    }
    return summary, details


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Thin helper: map guard stop_reasons to recovery playbook branches",
    )
    parser.add_argument("--input-json", required=True, help="one_shot_orchestrator output json path")
    parser.add_argument(
        "--recovery-playbook-path",
        default="/Users/kondogenki/AI Agent Maximizer/docs/recovery-playbook.md",
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    output: Dict[str, Any]
    ok = True
    try:
        source_path = Path(args.input_json)
        if not source_path.exists():
            raise ValueError(f"input json not found: {args.input_json}")

        source = parse_json_file(source_path)
        guard_summary, details = summarize_guards(source)
        branches = [
            map_reason_to_branch(item["reason"], item["source"], args.recovery_playbook_path)
            for item in details
        ]

        mode = source.get("mode")
        if not isinstance(mode, str) or mode not in {"strict", "fail-open"}:
            mode = "strict" if args.strict else "fail-open"

        output = {
            "ts": utc_now_iso(),
            "helper": "recovery_next_helper",
            "mode": mode,
            "ok": True,
            "input": {
                "input_json": str(source_path),
                "recovery_playbook_path": args.recovery_playbook_path,
            },
            "guard_summary": guard_summary,
            "recovery_next": {
                "required": len(branches) > 0,
                "branch_count": len(branches),
                "branches": branches,
                "note": "Mapping only. Execution and final judgment remain with operator/coordinator/verifier.",
            },
        }
    except Exception as error:
        ok = False
        output = {
            "ts": utc_now_iso(),
            "helper": "recovery_next_helper",
            "mode": "strict" if args.strict else "fail-open",
            "ok": False,
            "error": {
                "code": "RECOVERY_NEXT_MAPPING_FAILED",
                "message": str(error),
            },
            "guard_summary": {
                "preflight_guard": None,
                "post_run_guard": None,
                "stop_detected": False,
                "stop_reason_details": [],
            },
            "recovery_next": {
                "required": False,
                "branch_count": 0,
                "branches": [],
            },
        }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")

    if args.strict and not ok:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
