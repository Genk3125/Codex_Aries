# Post-Step Check Helper

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/post_step_check_helper.py`

## 1. 目的

操作後の状態確認を 1 コマンド化し、`reconcile-all -> task_get -> message_list` の手作業を減らす。

## 2. スコープ

- 実施:
  - `runtime_reconcile_all` を先に実行
  - 続けて `task_get` と `message_list` を実行
  - `task_id` / `team_id` を `--task-id` / `--team-id` または入力 JSON から解決
  - fail-open / strict を runtime adapter に透過
  - reconcile / task / message の結果を 1 つの JSON に集約
- 非実施:
  - verifier 自動起動
  - 自動再実行
  - approval / trigger / worktree
  - runtime 本体変更

## 3. 設計（薄いラッパー）

1. runtime wrapper（既定: `/Users/kondogenki/.codex/runtime-adapter/codex-runtime`）へ `op` を順次転送する。
2. 実行順は固定:
   - `runtime_reconcile_all`
   - `task_get`
   - `message_list`
3. `task_id` / `team_id` は下記入力を優先順で解決:
   - 明示引数 `--task-id` / `--team-id`
   - `session_helper` 出力（例: `ids.*`, `next.*`）
   - `task_update_notify_helper` 出力（例: `input.*`, `task_update.*`）
4. strict 時のみ helper exit code を厳格化（`ok=false` なら `2`）。

## 4. 実行手順

### A. `task_update_notify_helper` 出力を使う（fail-open）
```bash
CODEX_RUNTIME_STORE_ROOT=/tmp/runtime-post-step-check \
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/post_step_check_helper.py \
  --input-json /tmp/runtime-post-step-check/task-update-notify.json \
  --store-root /tmp/runtime-post-step-check \
  --output-json /tmp/runtime-post-step-check/post-step-check-fail-open.json
```

### B. strict
```bash
CODEX_RUNTIME_STORE_ROOT=/tmp/runtime-post-step-check \
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/post_step_check_helper.py \
  --strict \
  --input-json /tmp/runtime-post-step-check/task-update-notify.json \
  --store-root /tmp/runtime-post-step-check \
  --output-json /tmp/runtime-post-step-check/post-step-check-strict.json
```

### C. `session_helper` 出力を直接使う
```bash
CODEX_RUNTIME_STORE_ROOT=/tmp/runtime-post-step-check \
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/post_step_check_helper.py \
  --input-json /tmp/runtime-post-step-check/session.json \
  --store-root /tmp/runtime-post-step-check \
  --output-json /tmp/runtime-post-step-check/post-step-check-from-session.json
```
