# Resume Context

## Status
- **現在の状態**: `failed`
- **最終成功ステップ**: `chain_helper`
- **失敗ステップ**: `session_helper` (exit_code: 0)
- **停止理由**: なし

## Evidence Summary
- **実行コマンド数**: 7
- **ステップ数**: 8 (成功: 2, 失敗: 5, スキップ: 1)
- **失敗ステップ一覧**: `session_helper`, `task_update_notify_helper`, `post_step_check_helper`, `verifier_gate_helper`, `bridge_helper`

## Next Action
- **種別**: `inspect_failure`
- **ヒント**: Inspect failed_step and summarize evidence before the next attempt.
- **アクション**:
  - check compact_state.failed_step
  - collect minimal evidence

## IDs
- team_id: `(未取得)`
- task_id: `(未取得)`
- member_id: `worker_daily_driver`
- leader_id: `(未取得)`

## Meta
- run_id: `20260403204831`
- flow_mode: `chain`
- mode: `fail-open`
