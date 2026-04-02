# Compact State Helper

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/compact_state_helper.py`

## 1. 目的

長い helper 出力を次ターン向けの最小 state に圧縮し、  
context 消費を抑えつつ継続判断に必要な情報だけを残す。

## 2. スコープ

- 実施:
  - `one_shot_orchestrator` 出力 JSON を入力に受ける
  - 必要なら `handoff_helper` 出力 JSON も受ける
  - `compact_state` に最低限以下を残す
    - `current_status`
    - `last_successful_step`
    - `failed_step`
    - `stop_reasons`
    - `executed_commands_summary`
    - `actual_outputs_summary`
    - `next_action`
    - `ids`（task/team/member の最低限）
  - strict / fail-open を透過する
- 非実施:
  - guard 判定の再実装
  - verifier 判定の再実装
  - retry 実行
  - runtime 操作
  - 会話全文/詳細ログの保存

## 3. 責務分離

- `handoff_helper`:
  - verifier/coordinator 向け handoff 材料整形
- `compact_state_helper`:
  - 次ターン向け最小 state への圧縮

## 4. 実行手順

### A. stop + handoff ケース
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/compact_state_helper.py \
  --orchestrator-json /tmp/runtime-preflight-max-retries/out.json \
  --handoff-json /tmp/runtime-preflight-max-retries/handoff.json \
  --output-json /tmp/runtime-preflight-max-retries/compact-state.json
```

### B. no-op ケース（handoff なし）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/compact_state_helper.py \
  --orchestrator-json /tmp/runtime-preflight-allow/out.json \
  --output-json /tmp/runtime-preflight-allow/compact-state.json
```

### C. strict（入力異常時に非0）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/compact_state_helper.py \
  --strict \
  --orchestrator-json /tmp/not-found-orchestrator.json \
  --output-json /tmp/compact-state-strict.json
```
