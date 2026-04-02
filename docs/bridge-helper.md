# Bridge Helper

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/bridge_helper.py`

## 1. 目的

`verifier_gate_helper` の `requires_verifier=true` を受けて、  
`task_update_notify_helper` に自動橋渡しし、task を `blocked` へ更新して担当者通知する。

## 2. スコープ

- 実施:
  - gate 出力JSONを読み込み
  - `requires_verifier=true` の時だけ `task_update_notify_helper` 実行
  - task 更新先を `blocked` に固定
  - `blocked_reason` を gate trigger 要約から生成
  - 通知先 `--to-member-id` と通知文 `--message-text` は明示指定
  - fail-open / strict 透過
  - `gate_result` と `bridge_result` を含む JSON を返す
- 非実施:
  - verifier 最終判定ロジック
  - task state 判定ロジックの再実装
  - 自動修正 / approval / trigger / worktree / runtime 本体変更

## 3. 設計（薄い橋渡し）

1. bridge は gate 判定結果を読むだけ（`requires_verifier` 判定を再計算しない）。
2. 実行条件に合致した時だけ、`task_update_notify_helper` を subprocess で呼ぶ。
3. task update は `--state blocked` 固定で呼び出す。
4. strict 時だけ失敗を終了コード `2` で返し、fail-open では JSON 結果を返して継続する。

## 4. 実行手順

### A. `requires_verifier=true` のとき橋渡し実行
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/bridge_helper.py \
  --input-json /tmp/runtime-post-step-check/verifier-gate-trigger-no-verifier.json \
  --to-member-id worker_psc_1 \
  --message-text "gate triggered; task moved to blocked" \
  --store-root /tmp/runtime-post-step-check \
  --task-idempotency-key bridge-task-1 \
  --message-idempotency-key bridge-msg-1 \
  --output-json /tmp/runtime-post-step-check/bridge-trigger.json
```

### B. `requires_verifier=false` のときは skip
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/bridge_helper.py \
  --input-json /tmp/runtime-post-step-check/verifier-gate-clean.json \
  --to-member-id worker_psc_1 \
  --message-text "no-op" \
  --store-root /tmp/runtime-post-step-check \
  --output-json /tmp/runtime-post-step-check/bridge-skip.json
```

### C. strict
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/bridge_helper.py \
  --strict \
  --input-json /tmp/runtime-post-step-check/verifier-gate-trigger-no-verifier.json \
  --to-member-id worker_psc_1 \
  --message-text "gate triggered; task moved to blocked" \
  --store-root /tmp/runtime-post-step-check \
  --output-json /tmp/runtime-post-step-check/bridge-trigger-strict.json
```
