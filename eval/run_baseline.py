#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def latest_run_dir(runs_root: Path) -> Optional[Path]:
    candidates = [path for path in runs_root.glob("*") if path.is_dir()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime)
    return candidates[-1]


def run_cmd(cmd: List[str], cwd: Path) -> Dict[str, Any]:
    start = time.perf_counter()
    process = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=str(cwd))
    elapsed_sec = time.perf_counter() - start
    return {
        "cmd": cmd,
        "exit_code": process.returncode,
        "stdout": (process.stdout or "").strip(),
        "stderr": (process.stderr or "").strip(),
        "elapsed_sec": elapsed_sec,
    }


@dataclass
class TaskResult:
    task_id: str
    size: str
    kind: str
    success: bool
    attempts: int
    recovered: bool
    elapsed_sec: float
    verification_pass: Optional[bool]
    team_success: Optional[bool]
    note: str
    artifact: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "size": self.size,
            "kind": self.kind,
            "success": self.success,
            "attempts": self.attempts,
            "recovered": self.recovered,
            "elapsed_sec": self.elapsed_sec,
            "verification_pass": self.verification_pass,
            "team_success": self.team_success,
            "note": self.note,
            "artifact": self.artifact,
        }


def parse_orch_ok(run_dir: Path) -> bool:
    orch_path = run_dir / "orch.json"
    if not orch_path.exists():
        return False
    data = json.loads(orch_path.read_text(encoding="utf-8"))
    return bool(data.get("ok"))


def run_orchestrator_task(repo_root: Path, runs_root: Path, task: Dict[str, Any]) -> TaskResult:
    task_id = str(task["id"])
    size = str(task["size"])
    flow = str(task.get("flow", "gate"))
    title = str(task["title"])
    strict_fail_then_resume = bool(task.get("strict_fail_then_resume", False))
    context_threshold_bytes = task.get("context_threshold_bytes")

    if strict_fail_then_resume:
        fail_cmd = [
            str(repo_root / "scripts" / "run-task.sh"),
            "--title",
            title,
            "--flow",
            flow,
            "--strict",
            "--gate-expected-task-state",
            "done",
            "--runs-root",
            str(runs_root),
        ]
        fail_result = run_cmd(fail_cmd, cwd=repo_root)
        attempts = 1
        elapsed = fail_result["elapsed_sec"]
        if fail_result["exit_code"] == 0:
            return TaskResult(
                task_id=task_id,
                size=size,
                kind="orchestrator",
                success=False,
                attempts=attempts,
                recovered=False,
                elapsed_sec=elapsed,
                verification_pass=False,
                team_success=None,
                note="strict failure expected but command returned 0",
                artifact=None,
            )

        resume_cmd = [
            str(repo_root / "scripts" / "resume-task.sh"),
            "--runs-root",
            str(runs_root),
        ]
        resume_result = run_cmd(resume_cmd, cwd=repo_root)
        attempts += 1
        elapsed += resume_result["elapsed_sec"]
        run_dir = latest_run_dir(runs_root)
        orch_ok = bool(run_dir and parse_orch_ok(run_dir))
        success = resume_result["exit_code"] == 0 and orch_ok
        return TaskResult(
            task_id=task_id,
            size=size,
            kind="orchestrator",
            success=success,
            attempts=attempts,
            recovered=success,
            elapsed_sec=elapsed,
            verification_pass=orch_ok,
            team_success=None,
            note="strict failure + resume",
            artifact=str(run_dir) if run_dir else None,
        )

    cmd = [
        str(repo_root / "scripts" / "run-task.sh"),
        "--title",
        title,
        "--flow",
        flow,
        "--runs-root",
        str(runs_root),
    ]
    if context_threshold_bytes is not None:
        cmd.extend(["--context-threshold-bytes", str(context_threshold_bytes)])
    result = run_cmd(cmd, cwd=repo_root)
    run_dir = latest_run_dir(runs_root)
    orch_ok = bool(run_dir and parse_orch_ok(run_dir))
    success = result["exit_code"] == 0 and orch_ok
    return TaskResult(
        task_id=task_id,
        size=size,
        kind="orchestrator",
        success=success,
        attempts=1,
        recovered=False,
        elapsed_sec=result["elapsed_sec"],
        verification_pass=orch_ok,
        team_success=None,
        note="single pass",
        artifact=str(run_dir) if run_dir else None,
    )


def run_team_runtime_task(repo_root: Path, task: Dict[str, Any]) -> TaskResult:
    task_id = str(task["id"])
    size = str(task["size"])
    cmd = [ "python3", str(repo_root / "tests" / "e2e" / "team_runtime_mvp.py") ]
    result = run_cmd(cmd, cwd=repo_root)
    success = result["exit_code"] == 0
    return TaskResult(
        task_id=task_id,
        size=size,
        kind="team_runtime",
        success=success,
        attempts=1,
        recovered=False,
        elapsed_sec=result["elapsed_sec"],
        verification_pass=None,
        team_success=success,
        note="team runtime mvp scenario",
        artifact=None,
    )


def metric_percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def compute_metrics(results: List[TaskResult]) -> Dict[str, Any]:
    total = len(results)
    success_count = sum(1 for item in results if item.success)
    first_valid_times = [item.elapsed_sec for item in results if item.success]
    first_valid_output_time = round(statistics.median(first_valid_times), 3) if first_valid_times else 0.0

    recovery_candidates = [item for item in results if item.attempts > 1]
    recovery_success = [item for item in recovery_candidates if item.recovered]
    rework_cycles = [max(0, item.attempts - 1) for item in results]

    orchestrator_results = [item for item in results if item.kind == "orchestrator"]
    verification_pass_count = sum(1 for item in orchestrator_results if item.verification_pass is True)
    team_results = [item for item in results if item.kind == "team_runtime"]
    team_success_count = sum(1 for item in team_results if item.team_success is True)

    return {
        "task_success_rate": metric_percent(success_count, total),
        "first_valid_output_time_sec": first_valid_output_time,
        "self_recovery_rate": metric_percent(len(recovery_success), len(recovery_candidates)),
        "rework_cycles_per_task": round(statistics.mean(rework_cycles), 3) if rework_cycles else 0.0,
        "verification_pass_rate": metric_percent(verification_pass_count, len(orchestrator_results)),
        "team_completion_rate": metric_percent(team_success_count, len(team_results)),
        "counts": {
            "total_tasks": total,
            "success_tasks": success_count,
            "recovery_candidates": len(recovery_candidates),
            "recovery_success": len(recovery_success),
            "orchestrator_tasks": len(orchestrator_results),
            "team_tasks": len(team_results),
        },
    }


def render_markdown(results: List[TaskResult], metrics: Dict[str, Any], generated_at: str) -> str:
    lines: List[str] = []
    lines.append("# Baseline Results (Phase 16)")
    lines.append("")
    lines.append(f"- Generated at: {generated_at}")
    lines.append("- Source: `eval/tasks/manifest.json`")
    lines.append("")
    lines.append("## Task Results")
    lines.append("")
    lines.append("| Task | Size | Kind | Success | Attempts | Elapsed(sec) | Note |")
    lines.append("|---|---|---|---|---:|---:|---|")
    for item in results:
        lines.append(
            f"| {item.task_id} | {item.size} | {item.kind} | {'yes' if item.success else 'no'} | {item.attempts} | {item.elapsed_sec:.3f} | {item.note} |"
        )
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("| Metric | Value | Target |")
    lines.append("|---|---:|---:|")
    lines.append(f"| task_success_rate | {metrics['task_success_rate']}% | >= 80% |")
    lines.append(f"| first_valid_output_time | {metrics['first_valid_output_time_sec']} sec | <= 300 sec |")
    lines.append(f"| self_recovery_rate | {metrics['self_recovery_rate']}% | >= 50% |")
    lines.append(f"| rework_cycles_per_task | {metrics['rework_cycles_per_task']} | <= 2 |")
    lines.append(f"| verification_pass_rate | {metrics['verification_pass_rate']}% | >= 70% |")
    lines.append(f"| team_completion_rate | {metrics['team_completion_rate']}% | >= 60% |")
    lines.append("")
    lines.append("## Target Check")
    lines.append("")
    target_checks = [
        ("task_success_rate", metrics["task_success_rate"] >= 80.0, ">= 80%"),
        ("first_valid_output_time", metrics["first_valid_output_time_sec"] <= 300.0, "<= 300 sec"),
        ("self_recovery_rate", metrics["self_recovery_rate"] >= 50.0, ">= 50%"),
        ("rework_cycles_per_task", metrics["rework_cycles_per_task"] <= 2.0, "<= 2"),
        ("verification_pass_rate", metrics["verification_pass_rate"] >= 70.0, ">= 70%"),
        ("team_completion_rate", metrics["team_completion_rate"] >= 60.0, ">= 60%"),
    ]
    lines.append("| Metric | Pass | Target |")
    lines.append("|---|---|---|")
    for metric_name, passed, target in target_checks:
        lines.append(f"| {metric_name} | {'yes' if passed else 'no'} | {target} |")
    lines.append("")

    failed_targets = [name for name, passed, _ in target_checks if not passed]
    lines.append("## Weak Points / Next Actions")
    lines.append("")
    if not failed_targets:
        lines.append("- 目標未達の指標はなし。")
    else:
        for metric_name in failed_targets:
            if metric_name == "self_recovery_rate":
                lines.append("- `self_recovery_rate`: strict失敗ケースを増やし、resume成功までの回復パスを再測定する。")
            elif metric_name == "first_valid_output_time":
                lines.append("- `first_valid_output_time`: first useful artifact 出力を分離測定し、初動時間の可視化を改善する。")
            else:
                lines.append(f"- `{metric_name}`: 測定対象タスク構成を見直して再計測する。")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- 本ベースラインは single-pass kernel の現行実装を対象。")
    lines.append("- strict 失敗から resume する recovery ケースを 1 本含む。")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run baseline task set and compute phase16 metrics")
    parser.add_argument("--manifest", default="eval/tasks/manifest.json")
    parser.add_argument("--runs-root", default="")
    parser.add_argument("--output-json", default="eval/baseline-results.json")
    parser.add_argument("--output-markdown", default="eval/baseline-results.md")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = (repo_root / args.manifest).resolve() if not Path(args.manifest).is_absolute() else Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tasks = manifest.get("tasks", [])
    if not isinstance(tasks, list) or not tasks:
        raise SystemExit("manifest has no tasks")

    if args.runs_root:
        runs_root = Path(args.runs_root)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        runs_root = repo_root / "eval" / "runs" / stamp
    runs_root.mkdir(parents=True, exist_ok=True)

    results: List[TaskResult] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        kind = str(task.get("kind", "orchestrator"))
        if kind == "team_runtime":
            result = run_team_runtime_task(repo_root=repo_root, task=task)
        else:
            result = run_orchestrator_task(repo_root=repo_root, runs_root=runs_root, task=task)
        results.append(result)

    metrics = compute_metrics(results)
    generated_at = utc_now_iso()

    output_obj = {
        "generated_at": generated_at,
        "manifest": str(manifest_path),
        "runs_root": str(runs_root),
        "metrics": metrics,
        "results": [item.to_dict() for item in results],
    }
    output_json_path = (repo_root / args.output_json).resolve() if not Path(args.output_json).is_absolute() else Path(args.output_json)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(output_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    markdown = render_markdown(results, metrics, generated_at)
    output_md_path = (repo_root / args.output_markdown).resolve() if not Path(args.output_markdown).is_absolute() else Path(args.output_markdown)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.write_text(markdown, encoding="utf-8")

    print(json.dumps(output_obj, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
