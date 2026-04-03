# Resume Context

## Status
- **現在の状態**: `stopped_post_run`
- **最終成功ステップ**: `(なし)`
- **失敗ステップ**: `session_helper` (exit_code: 0)
- **停止理由**: max_retries, escalated

## Evidence Summary
- **実行コマンド数**: 4
- **ステップ数**: 7 (成功: 0, 失敗: 4, スキップ: 3)
- **失敗ステップ一覧**: `session_helper`, `task_update_notify_helper`, `post_step_check_helper`, `verifier_gate_helper`

## Next Action
- **種別**: `prepare_escalation`
- **ヒント**: Run escalation flow and prepare coordinator/verifier packet before next run.
- **アクション**:
  - run recovery_next_helper
  - run escalation_draft_helper
  - optionally run handoff_helper

## IDs
- team_id: `(未取得)`
- task_id: `(未取得)`
- member_id: `worker_daily_driver`
- leader_id: `(未取得)`

## Meta
- run_id: `20260403115438`
- flow_mode: `gate`
- mode: `fail-open`
