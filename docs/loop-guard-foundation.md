# Loop Guard Foundation (Design + Minimal Implementation)

- Version: 0.1
- Date: 2026-04-03
- Target:
  - `poc/loop_guard.py`
  - `poc/one_shot_orchestrator.py`

## 1. 目的

将来の多段オーケストレーションで無限循環・無制限再試行に落ちないよう、  
単発実行を壊さずに「停止/継続/エスカレーション判断」だけを先に入れる。

## 2. 何を設計したか

### 2.1 Guard責務
- Guard は **判断のみ** を担当:
  - `continue`
  - `escalate`
  - `stop`
- 以下は Guard の責務外:
  - gate 判定
  - verifier 判定
  - task update / send_message / reconcile 実処理
  - 自動リトライ実行

### 2.2 薄い state
- 永続 state は JSON 1ファイル（`--guard-state-json`）に最小保存:
  - `attempt_count`
  - `consecutive_failures`
  - `manual_stop`
  - `last_ok`
  - `last_decision`
  - `last_reasons`
  - `updated_at`

### 2.3 必須パラメータ
- `attempt_count`: 実行回数
- `max_retries`: 停止条件に使う上限
- `escalate_after_n`: 失敗連続回数で escalation 判定
- `stop_condition`: 停止条件の集合
  - `success`
  - `max_retries`
  - `strict_failure`
  - `manual_stop`
  - `escalated`

## 3. recovery-playbook 接続

- `escalate_after_n` 到達時の `decision=escalate` は  
  `/Users/kondogenki/AI Agent Maximizer/docs/recovery-playbook.md` の 3.3 Escalate に接続。
- `strict_failure` / `max_retries` / `manual_stop` で `decision=stop` を返し、  
  Playbook の Stop Conditions を運用判断の入口にする。

## 4. strict / fail-open 整合

- fail-open:
  - `output.ok=false` でも終了コードは `0`（従来維持）
  - guard は次アクション判断を JSON に返す
- strict:
  - helper失敗または guard失敗で終了コード `2`
  - `strict_failure` を stop_condition に含めることで早期停止可能

## 5. single-pass 非破壊

- 既存の one-shot は単発実行のまま。
- Guard は実行後に 1 回評価するだけで、再帰・自動再試行・自動ループはしない。

## 6. 最小実装ポイント

1. `poc/loop_guard.py`
   - stop_condition パーサ
   - state load/save
   - `evaluate_guard()`（判断のみ）
2. `poc/one_shot_orchestrator.py`
   - `--guard-*` 引数を追加
   - 実行後に guard 評価を 1 回呼び出し
   - 出力 JSON に `guard` セクションを追加

## 7. 実行手順

### A. fail-open + guard 有効（単発）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --flow-mode gate \
  --team-name lg-team-a \
  --member-id worker_lg_a \
  --task-title "loop guard baseline" \
  --bootstrap-message "start" \
  --gate-expected-task-state in_progress \
  --store-root /tmp/runtime-loop-guard-a/store \
  --guard-state-json /tmp/runtime-loop-guard-a/guard-state.json \
  --output-json /tmp/runtime-loop-guard-a/orchestrator.json
```

### B. fail-open 失敗ケースを連続実行（escalate 判定確認）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --flow-mode gate \
  --team-name lg-team-b \
  --member-id worker_lg_b \
  --task-title "loop guard fail path" \
  --bootstrap-message "start fail path" \
  --gate-expected-task-state blocked \
  --store-root /tmp/runtime-loop-guard-b/store \
  --guard-state-json /tmp/runtime-loop-guard-b/guard-state.json \
  --guard-escalate-after-n 2 \
  --output-json /tmp/runtime-loop-guard-b/orchestrator-1.json
```

### C. strict での guard 整合確認
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --strict \
  --flow-mode gate \
  --team-name lg-team-c \
  --member-id worker_lg_c \
  --task-title "loop guard strict path" \
  --bootstrap-message "start strict path" \
  --gate-expected-task-state blocked \
  --store-root /tmp/runtime-loop-guard-c/store \
  --guard-state-json /tmp/runtime-loop-guard-c/guard-state.json \
  --output-json /tmp/runtime-loop-guard-c/orchestrator.json
```
