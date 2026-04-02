# Chain Helper

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/chain_helper.py`

## 1. 目的

`loopback_helper` 後の `post-check` が怪しい時だけ `verifier_gate_helper` へ自然接続し、  
不要な gate 実行を減らす。

## 2. スコープ

- 実施:
  - `loopback_helper` 出力 JSON を入力に受ける
  - `post_check_result.executed=false` なら skip
  - `post_check_result.ok=true` なら skip
  - `post_check_result.ok=false` の時だけ `verifier_gate_helper` を実行
  - `task_id` / `team_id` を loopback 出力から解決
  - fail-open / strict 透過
  - `loopback_result` と `verifier_gate_result` を含む JSON 出力
- 非実施:
  - gate 判定の再実装
  - verifier 判定の再実装
  - task update / send_message の再実装
  - 自動修正 / approval / trigger / worktree

## 3. 設計（薄い接続）

1. chain helper は loopback の `post_check_result` を分岐条件として扱うだけ。
2. 必要時のみ `verifier_gate_helper` を subprocess で 1 回呼ぶ。
3. 今回は **1回だけ** gate を呼ぶ。再帰・自動再試行・自動ループは入れない。
4. `post_step_check_output` が loopback に埋まっていない場合は、最小 fallback JSON を作って gate に渡す（gate ロジック再実装はしない）。

## 4. 将来の loop guard（軽量メモ）

- full automation では `chain -> gate -> bridge -> loopback -> chain` の循環リスクがある。
- 将来は `attempt_count`, `max_retries`, `escalate_after_n`, `stop_condition` を導入し、  
  `/Users/kondogenki/AI Agent Maximizer/docs/recovery-playbook.md` の停止/エスカレーション規律に接続する。

## 5. 実行手順

### A. post-check が失敗時のみ gate 実行
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/chain_helper.py \
  --input-json /tmp/runtime-post-step-check/loopback-bad-script-failopen.json \
  --output-json /tmp/runtime-post-step-check/chain-from-bad-loopback.json
```

### B. post-check 未実行なら skip
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/chain_helper.py \
  --input-json /tmp/runtime-post-step-check/loopback-skip.json \
  --output-json /tmp/runtime-post-step-check/chain-from-loopback-skip.json
```

### C. post-check 正常なら skip
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/chain_helper.py \
  --input-json /tmp/runtime-post-step-check/loopback-trigger.json \
  --output-json /tmp/runtime-post-step-check/chain-from-loopback-ok.json
```

### D. strict
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/chain_helper.py \
  --strict \
  --input-json /tmp/runtime-post-step-check/loopback-bad-script-failopen.json \
  --output-json /tmp/runtime-post-step-check/chain-from-bad-loopback-strict.json
```
