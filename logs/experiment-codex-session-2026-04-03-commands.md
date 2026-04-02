# 実行コマンド一覧（Experiment 2026-04-03）

## 0) 初期確認
- `pwd && ls -la`
- `rg --files | rg 'README.md|logs/experiment-codex-session-2026-04-03.log|verifier-contract.md|verifier.toml|coordinator.toml|codex_runtime_adapter.py|team_control_plane.py|team_message_bus.py|team_task_bus.py'`
- `cat AGENTS.md`

## 1) 既存ログ・設計読み取り
- `sed -n '1,260p' logs/experiment-codex-session-2026-04-03.log`
- `sed -n '1,260p' docs/codex-session-min-orchestration-experiment.md`
- `sed -n '1,260p' /Users/kondogenki/.codex/runtime-adapter/codex-runtime`
- `sed -n '1,320p' poc/codex_runtime_adapter.py`
- `sed -n '1,320p' coordinator.toml`
- `sed -n '1,320p' verifier.toml`
- `sed -n '1,320p' verifier-contract.md`

## 2) Runtime 実験コマンド（本体）
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime ops`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime team-create exp-20260403 exp-team-20260403-1`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime task-create team_6a3e8ab07b48 implement-minimal-change leader_7199020b ready exp-task-impl-1`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime task-create team_6a3e8ab07b48 run-verifier leader_7199020b ready exp-task-verify-1`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime send-message team_6a3e8ab07b48 leader_7199020b leader_7199020b "Start implementation: add one minimal README line and report diff" exp-msg-impl-1`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name task_update --args-json '{"task_id":"task_1ed8b2364df7","state":"in_progress","idempotency_key":"exp-task-impl-progress-1"}'`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name task_update --args-json '{"task_id":"task_1ed8b2364df7","state":"done","result_reference":"README.md:31","idempotency_key":"exp-task-impl-done-1"}'`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime send-message team_6a3e8ab07b48 leader_7199020b leader_7199020b "Implementation done. Please run verifier with contract and record verdict." exp-msg-verify-1`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name task_update --args-json '{"task_id":"task_e84f4c242d7c","state":"in_progress","idempotency_key":"exp-task-verify-progress-1"}'`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name send_message --args-json '{"team_id":"team_missing","from_member_id":"leader_7199020b","to_member_id":"leader_7199020b","message_type":"direct","payload":{"text":"probe fail-open"},"idempotency_key":"exp-msg-failopen-check-1"}'`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime --strict op --name send_message --args-json '{"team_id":"team_missing","from_member_id":"leader_7199020b","to_member_id":"leader_7199020b","message_type":"direct","payload":{"text":"probe strict"},"idempotency_key":"exp-msg-strict-check-1"}'`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name task_update --args-json '{"task_id":"task_1ed8b2364df7","result_reference":"README.md:24","idempotency_key":"exp-task-impl-ref-fix-1"}'`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name runtime_reconcile_all --args-json '{}'`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name task_update --args-json '{"task_id":"task_e84f4c242d7c","state":"done","result_reference":"logs/experiment-verifier-report-2026-04-03.md:1","idempotency_key":"exp-task-verify-done-1"}'`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name team_list --args-json '{}'`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name task_list --args-json '{"team_id":"team_6a3e8ab07b48"}'`
- `CODEX_RUNTIME_STORE_ROOT=/Users/kondogenki/.codex/runtime-spike-exp-20260403 /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name message_list --args-json '{"team_id":"team_6a3e8ab07b48"}'`

## 3) Verifier 実行時コマンド（サブエージェント）
- `sed -n '1,140p' '/Users/kondogenki/AI Agent Maximizer/logs/experiment-codex-session-2026-04-03.log'`
- `CODEX_RUNTIME_STORE_ROOT='/Users/kondogenki/.codex/runtime-spike-exp-20260403' /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name runtime_info --args-json '{}'`
- `CODEX_RUNTIME_STORE_ROOT='/Users/kondogenki/.codex/runtime-spike-exp-20260403' /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name team_list --args-json '{}'`
- `CODEX_RUNTIME_STORE_ROOT='/Users/kondogenki/.codex/runtime-spike-exp-20260403' /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name task_list --args-json '{"team_id":"team_6a3e8ab07b48"}'`
- `CODEX_RUNTIME_STORE_ROOT='/Users/kondogenki/.codex/runtime-spike-exp-20260403' /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name message_list --args-json '{"team_id":"team_6a3e8ab07b48"}'`
- `nl -ba '/Users/kondogenki/AI Agent Maximizer/README.md' | sed -n '16,28p'`
- `CODEX_RUNTIME_STORE_ROOT='/Users/kondogenki/.codex/runtime-spike-exp-20260403' /Users/kondogenki/.codex/runtime-adapter/codex-runtime reconcile-all`
- `CODEX_RUNTIME_STORE_ROOT='/Users/kondogenki/.codex/runtime-spike-exp-20260403' /Users/kondogenki/.codex/runtime-adapter/codex-runtime op --name send_message --args-json '{"team_id":"team_missing","from_member_id":"leader_7199020b","to_member_id":"leader_7199020b","message_type":"direct","payload":{"text":"probe fail-open verifier"},"idempotency_key":"exp-msg-failopen-check-verify-1"}'`
- `CODEX_RUNTIME_STORE_ROOT='/Users/kondogenki/.codex/runtime-spike-exp-20260403' /Users/kondogenki/.codex/runtime-adapter/codex-runtime --strict op --name send_message --args-json '{"team_id":"team_missing","from_member_id":"leader_7199020b","to_member_id":"leader_7199020b","message_type":"direct","payload":{"text":"probe strict verifier"},"idempotency_key":"exp-msg-strict-check-verify-1"}'`
