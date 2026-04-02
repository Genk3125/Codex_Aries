# Team Member Re-Experiment Summary (2026-04-03)

- store_root: `/Users/kondogenki/.codex/runtime-spike-team-member-rerun-20260403`
- team_id: `team_f01374473d70`
- leader_id: `leader_8aaee6c2`
- task_id: `task_468f4044a5fa`

## Check Results
- send_message to added member:
  - status: `delivered`
  - delivery_state: `delivered`
- send_message after member remove:
  - status: `failed`
  - delivery_state: `failed`
  - delivery_error: `RECIPIENT_NOT_DELIVERABLE:shutdown`
- leader removal strict check:
  - exit_code: `2`
  - error_code: `LEADER_REMOVAL_NOT_ALLOWED`
- reconcile-all:
  - control_plane.cleaned_count: `0`
  - message_bus.pending_after: `0`
  - task_bus.orphaned: `1`
  - task_bus.moved_to_ready: `1`

## Interpretation
- 追加 member 宛の direct message は期待どおり `delivered`。
- member remove 後は同宛先が `deliverable` でなくなり、期待どおり `failed`。
- leader remove は拒否され、strict で non-zero 返却を確認。
- reconcile-all は未解決 pending を増やさず、orphan owner を検知して `ready` へ戻した。

## Final Verdict
- `PASS`（今回の必須観点に対して）

## Artifacts
- log: `/Users/kondogenki/AI Agent Maximizer/logs/experiment-team-member-rerun-2026-04-03.log`
