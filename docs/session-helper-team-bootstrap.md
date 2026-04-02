# Session Helper: team bootstrap flow

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/session_helper.py`

## 1. 目的

手動運用で最も重い `team_id / leader_id / task_id` の受け渡しを減らすため、  
`team-create -> team_member_add -> task-create -> send-message` だけを束ねる薄い helper を追加する。

## 2. スコープ

- 実施:
  - `team-create`
  - `team_member_add`
  - `task-create`
  - `send-message`
  - 次ステップで再利用しやすい JSON 出力（IDs + step results）
- 非実施:
  - verifier 自動起動
  - worktree / trigger / approval
  - runtime 本体ロジックの変更
  - 完全自動 orchestration

## 3. 設計（薄いラッパー方針）

1. helper は runtime wrapper（既定: `/Users/kondogenki/.codex/runtime-adapter/codex-runtime`）を順番に呼ぶだけ。
2. 各 step の JSON envelope をそのまま保持し、独自のドメイン状態は持たない。
3. IDs は runtime の戻り値から抽出:
   - team_create -> `team_id`, `leader_agent_id`
   - task_create -> `task_id`
   - send_message -> `message_id`
4. 出力 JSON に以下を含める:
   - `ok`, `mode`, `error`
   - `ids`（`team_id`, `leader_id`, `member_id`, `task_id`, `message_id`）
   - `steps`（各 step の command / exit_code / operation_ok / error / result）
   - `next`（task_update/send_message の入力ひな形）

## 4. fail-open / strict

- fail-open（既定）:
  - runtime 呼び出しは fail-open のまま（`--strict` を付けない）
  - helper 出力の `ok` と `steps[*].operation_ok` で判定する
  - helper の終了コードは `0`
- strict:
  - helper に `--strict` を付与すると runtime へも `--strict` を透過
  - 途中失敗時は helper も終了コード `2`

## 5. 実行手順

```bash
cd /Users/kondogenki/AI\ Agent\ Maximizer

CODEX_RUNTIME_STORE_ROOT=/tmp/runtime-helper-demo \
python3 poc/session_helper.py \
  --team-name helper-demo \
  --member-id worker_demo_1 \
  --task-title "bootstrap task" \
  --task-owner member \
  --task-state ready \
  --message-text "start task" \
  --team-idempotency-key helper-team-1 \
  --member-add-idempotency-key helper-member-1 \
  --task-idempotency-key helper-task-1 \
  --message-idempotency-key helper-msg-1 \
  --output-json /tmp/runtime-helper-demo/result.json
```

strict 実行:

```bash
CODEX_RUNTIME_STORE_ROOT=/tmp/runtime-helper-demo \
python3 poc/session_helper.py \
  --strict \
  --team-name helper-demo-strict \
  --member-id worker_demo_2 \
  --task-title "bootstrap task strict" \
  --message-text "start task strict"
```

## 6. 運用上の注意

- helper は runtime の薄いオーケストレーション層であり、Control Plane / Message Bus / Task Bus の仕様責務は持たない。
- 失敗調査は helper の `steps[*]` ではなく、各 runtime envelope の `error` を一次情報として扱う。
