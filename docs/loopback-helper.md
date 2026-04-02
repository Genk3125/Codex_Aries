# Loopback Helper

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/loopback_helper.py`

## 1. 目的

`bridge_helper` 実行後に `post_step_check_helper` を再実行し、  
`blocked` 反映後の整合確認までを 1 コマンドで閉じる。

## 2. スコープ

- 実施:
  - `bridge_helper` 出力 JSON を入力として受ける
  - `bridge_result.executed=false` の場合は skip
  - `bridge_result.executed=true` の場合のみ `post_step_check_helper` 実行
  - `task_id` / `team_id` を bridge 出力から解決
  - fail-open / strict 透過
  - `bridge_result` と `post_check_result` を含む JSON 出力
- 非実施:
  - gate 判定ロジックの再実装
  - task_update / send_message / verifier 判定ロジックの再実装
  - 自動修正 / verifier 自動起動 / approval / trigger / worktree

## 3. 設計（薄い接続）

1. loopback は bridge 結果を確認し、条件を満たす時だけ post-check を実行する。
2. post-check は `post_step_check_helper` へ subprocess で橋渡しする。
3. strict 時のみ失敗を終了コード `2` で返し、fail-open は JSON を返して継続する。
4. 今回は **1回だけ** `post_step_check_helper` を再実行する。再帰・自動ループは実装しない。

## 4. 将来の無限循環リスク（明示）

- 本 helper は「bridge 後に post-check を1回実行する」前提であり、現時点で反復制御は持たない。
- 将来、loopback の自動反復を入れると `bridge -> loopback -> gate -> bridge ...` の循環が起きる可能性がある。
- 反復を導入する場合は以下を最低限必須にする:
  - `attempt_count`
  - `max_retries`
  - `escalate_after_n`
  - `stop_condition`
- 停止・エスカレーション条件は `/Users/kondogenki/AI Agent Maximizer/docs/recovery-playbook.md` と整合させる。

## 5. 実行手順

### A. bridge 実行済み（post-check 実行）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/loopback_helper.py \
  --input-json /tmp/runtime-post-step-check/bridge-trigger.json \
  --store-root /tmp/runtime-post-step-check \
  --output-json /tmp/runtime-post-step-check/loopback-trigger.json
```

### B. bridge 未実行（skip）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/loopback_helper.py \
  --input-json /tmp/runtime-post-step-check/bridge-skip.json \
  --store-root /tmp/runtime-post-step-check \
  --output-json /tmp/runtime-post-step-check/loopback-skip.json
```

### C. strict
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/loopback_helper.py \
  --strict \
  --input-json /tmp/runtime-post-step-check/bridge-trigger.json \
  --store-root /tmp/runtime-post-step-check \
  --output-json /tmp/runtime-post-step-check/loopback-trigger-strict.json
```
