# Task Update Helper

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/task_update_helper.py`

## 1. 目的

`session_helper` の出力 JSON をそのまま受け、  
`task_update` を 1 コマンドで実行できるようにする。

## 2. スコープ

- 実施:
  - `task_id` の自動解決（`session_helper` 出力 JSON から）
  - `state` 指定での `task_update`
  - `blocked_reason` / `result_reference` / `idempotency_key` の透過
  - fail-open / strict の透過
  - 次ステップで使いやすい JSON 出力
- 非実施:
  - verifier 自動起動
  - task 自動再割当
  - approval / trigger / worktree
  - runtime 本体の変更

## 3. 設計（薄いラッパー）

1. runtime wrapper（既定: `/Users/kondogenki/.codex/runtime-adapter/codex-runtime`）へ  
   `op --name task_update` を転送するだけ。
2. `task_id` の解決順:
   - `--task-id`（明示指定）
   - `--input-json` の `next.task_update_example.task_id`
   - `--input-json` の `ids.task_id`
3. helper は runtime の JSON envelope をそのまま `runtime.envelope` に保持する。
4. helper 出力 JSON には `ok`, `input`, `runtime`, `next` を含める。

## 4. 実行手順

### A. fail-open（既定）
```bash
CODEX_RUNTIME_STORE_ROOT=/tmp/runtime-helper-check \
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/task_update_helper.py \
  --input-json /tmp/runtime-helper-check/result-failopen.json \
  --state in_progress \
  --idempotency-key helper-tu-1 \
  --output-json /tmp/runtime-helper-check/task-update-failopen.json
```

### B. strict
```bash
CODEX_RUNTIME_STORE_ROOT=/tmp/runtime-helper-check-strict \
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/task_update_helper.py \
  --strict \
  --input-json /tmp/runtime-helper-check/result-strict.json \
  --state blocked \
  --blocked-reason "waiting for verifier" \
  --result-reference "logs/helper-strict-note.md:1" \
  --idempotency-key helper-tu-2 \
  --output-json /tmp/runtime-helper-check-strict/task-update-strict.json
```

## 5. session_helper との接続

- `session_helper` 出力の `next.task_update_example.task_id` をそのまま利用できるため、  
  手動で `task_id` をコピーする必要がない。
- `input_json` には `session_helper` の `--output-json` 先を渡せばよい。
