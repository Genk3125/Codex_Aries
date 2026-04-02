# One-Shot Orchestrator

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/one_shot_orchestrator.py`

## 1. 目的

`session_helper` から `chain_helper` までを 1 コマンドで順次実行し、  
必要に応じて `verifier-cmd` の結果まで受け取る。

## 2. スコープ

- 実施:
  - 既存 helper を順番に呼ぶ薄い接続だけを担当
  - `flow_mode=chain`:
    - `session_helper`
    - `task_update_notify_helper`
    - `post_step_check_helper`
    - `verifier_gate_helper`
    - `bridge_helper`
    - `loopback_helper`
    - `chain_helper`
  - `flow_mode=gate`:
    - `session_helper` -> `task_update_notify_helper` -> `post_step_check_helper` -> `verifier_gate_helper`
  - fail-open / strict 透過
  - 全 helper の結果を集約 JSON で返却
- 非実施:
  - gate 判定の再実装
  - verifier 判定の再実装
  - task update / send_message / reconcile の再実装
  - 自動修正 / approval / trigger / worktree

## 3. 設計（薄い接続）

1. orchestrator は helper を subprocess で順に 1 回ずつ呼ぶ。
2. helper ごとの判定ロジックは各 helper に委譲し、orchestrator 側で再解釈しない。
3. `--verifier-cmd` は `verifier_gate_helper` と `chain_helper` にそのまま渡す。
4. 反復はしない（再帰・自動再試行・自動ループなし）。

## 4. Loop Guard（将来 full automation 前提）

- 今回は単発実行のみ。`chain -> gate -> bridge -> loopback -> chain` の循環制御は未実装。
- full automation 前に最低限必要:
  - `attempt_count`
  - `max_retries`
  - `escalate_after_n`
  - `stop_condition`
- 停止/エスカレーション規律は  
  `/Users/kondogenki/AI Agent Maximizer/docs/recovery-playbook.md` と一致させる。

## 5. 実行手順

### A. chain モード（推奨）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --flow-mode chain \
  --team-name orch-team \
  --member-id worker_orch_1 \
  --task-title "orchestrator task" \
  --bootstrap-message "start orchestrator run" \
  --task-update-message "task moved to in_progress" \
  --bridge-message "gate triggered; task moved to blocked" \
  --gate-expected-task-state blocked \
  --store-root /tmp/runtime-orchestrator \
  --output-json /tmp/runtime-orchestrator/orchestrator-chain.json
```

### B. gate モード
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --flow-mode gate \
  --team-name orch-gate-team \
  --member-id worker_orch_2 \
  --task-title "orchestrator gate task" \
  --bootstrap-message "start gate run" \
  --store-root /tmp/runtime-orchestrator-gate \
  --output-json /tmp/runtime-orchestrator-gate/orchestrator-gate.json
```

### C. verifier 外部注入
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --flow-mode chain \
  --team-name orch-verifier-team \
  --member-id worker_orch_3 \
  --task-title "orchestrator verifier task" \
  --bootstrap-message "start verifier-injected run" \
  --gate-expected-task-state blocked \
  --verifier-cmd "python3 /tmp/mock_verifier.py" \
  --store-root /tmp/runtime-orchestrator-verifier \
  --output-json /tmp/runtime-orchestrator-verifier/orchestrator-chain-verifier.json
```
