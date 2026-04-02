# Preflight Guard Check (Minimal Extension)

- Version: 0.1
- Date: 2026-04-03
- Target:
  - `poc/loop_guard.py`
  - `poc/one_shot_orchestrator.py`

## 1. 目的

`one_shot_orchestrator` 実行前に guard state を読み、  
止めるべき run（manual stop / max retries 到達 / 既に stop 判定済み）を開始しない。

## 2. 責務分離

- preflight guard:
  - run 開始可否だけ判断する（`allow` / `stop`）
  - helper 実行ロジックは持たない
- post-run guard（既存）:
  - 実行結果をもとに `continue` / `escalate` / `stop` を判断する
  - state 更新を担当する

## 3. 最小仕様

- preflight stop 条件:
  - `manual_stop=true` かつ `manual_stop` が stop conditions に含まれる
  - `attempt_count >= max_retries` かつ `max_retries` が stop conditions に含まれる
  - `last_decision == stop`
- preflight で stop の場合:
  - helper 群はすべて `executed=false`
  - single-pass は維持（再帰・自動再試行なし）
  - post-run guard は `not_executed`
- strict / fail-open:
  - stop 判定は両モードで run 開始を止める
  - 返却コードは既存整合を維持（strict は非0、fail-open は 0）

## 4. 実行手順

### A. preflight stop（manual stop）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --flow-mode gate \
  --team-name preflight-stop-team \
  --member-id worker_preflight_1 \
  --task-title "preflight stop test" \
  --bootstrap-message "start" \
  --store-root /tmp/runtime-preflight-stop/store \
  --guard-state-json /tmp/runtime-preflight-stop/guard-state.json \
  --output-json /tmp/runtime-preflight-stop/out.json
```

### B. preflight allow（通常実行 + post-run guard）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --flow-mode gate \
  --team-name preflight-allow-team \
  --member-id worker_preflight_2 \
  --task-title "preflight allow test" \
  --bootstrap-message "start" \
  --store-root /tmp/runtime-preflight-allow/store \
  --guard-state-json /tmp/runtime-preflight-allow/guard-state.json \
  --output-json /tmp/runtime-preflight-allow/out.json
```
