# Task Update + Notify Helper

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/task_update_notify_helper.py`

## 1. 目的

`task_update` の直後に担当者通知 `send_message` を続けて実行し、  
状態更新後の通知を 1 コマンド化する。

## 2. スコープ

- 実施:
  - 先に `task_update`
  - `task_update` 成功時のみ `send_message` 実行
  - `task_id` を `--task-id` または JSON 入力から解決
  - `to_member_id` / `message_text` は明示指定
  - fail-open / strict の透過
  - `task_update` と `send_message` の両結果を JSON 出力
- 非実施:
  - verifier 自動起動
  - 自動再割当
  - approval / trigger / worktree
  - runtime 本体変更

## 3. 設計（薄いラッパー）

1. runtime wrapper（既定: `/Users/kondogenki/.codex/runtime-adapter/codex-runtime`）に  
   `op --name task_update` / `op --name send_message` を順に転送。
2. `task_id` 解決順:
   - `--task-id`
   - 入力 JSON の `next.task_update_example.task_id`
   - 入力 JSON の `ids.task_id`
   - 入力 JSON の `input.resolved_task_id`（`task_update_helper` 出力）
3. `team_id` / `from_member_id` は入力 JSON から解決可能だが、不足時は明示指定が必要。
4. `task_update` が失敗した場合、`send_message` は実行せず `skipped_reason` を返す。

## 4. 実行手順

### A. session_helper 出力を直接使う
```bash
CODEX_RUNTIME_STORE_ROOT=/tmp/runtime-helper-check \
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/task_update_notify_helper.py \
  --input-json /tmp/runtime-helper-check/result-failopen.json \
  --state in_progress \
  --to-member-id worker_helper_1 \
  --message-text "task moved to in_progress" \
  --task-idempotency-key helper-tun-1 \
  --message-idempotency-key helper-tun-msg-1 \
  --output-json /tmp/runtime-helper-check/task-update-notify-failopen.json
```

### B. strict
```bash
CODEX_RUNTIME_STORE_ROOT=/tmp/runtime-helper-check-strict \
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/task_update_notify_helper.py \
  --strict \
  --input-json /tmp/runtime-helper-check/result-strict.json \
  --state blocked \
  --blocked-reason "waiting for verifier" \
  --to-member-id worker_helper_2 \
  --message-text "task blocked: waiting for verifier" \
  --task-idempotency-key helper-tun-2 \
  --message-idempotency-key helper-tun-msg-2 \
  --output-json /tmp/runtime-helper-check-strict/task-update-notify-strict.json
```

## 5. task_update_helper との棲み分け

- `task_update_helper`: task 状態更新だけを最小実行する単機能ツール。
- `task_update_notify_helper`: 状態更新成功後の通知まで含める連結ツール。
- まずは `task_update_helper` で検証し、運用で頻出なら `task_update_notify_helper` を使う。
