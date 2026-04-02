# Next Tasks (Execution Order)

> 統合版の上位計画は `docs/CODEX_MAX_COMBINED_PLAN.md` を参照。
> 実行粒度のタスク分解とエージェント向けプロンプトは `docs/EXECUTION_TASK_BREAKDOWN.md` を参照。
> 現在の実装カーネル基準の優先作業は `/Users/kondogenki/AI Agent Maximizer/ToDo.md` を最優先で参照。

## Status

- この文書は **初期フェーズの実行順メモ**。
- 現在の helper / orchestrator / guard / handoff まで進んだ状態には追随していない。
- いま次にやることを決めるときは `ToDo.md` を使う。

## Task 1 — Compliance Gate
- `claude-code-main` のライセンス/利用条件を確認
- 再利用可能な範囲を `data/normalized/license-matrix.md` に確定

## Task 2 — Gap Freeze (Claude vs Codex)
- `docs/CLAUDE_VS_CODEX_FEATURE_GAPS.md` を差分の単一ソースとして確定
- P0/P1/P2 の対象外を明示してスコープ固定

## Task 3 — P0 RFC: Agent Team Control Plane
- 仕様化対象:
  - `team_create`
  - `team_delete`
  - team metadata/state persistence
- 成果物: `docs/rfc-agent-team-control-plane.md`

## Task 4 — P0 RFC: Team Message Bus
- 仕様化対象:
  - broadcast
  - shutdown/approval などの構造化メッセージ
- 成果物: `docs/rfc-team-message-bus.md`

## Task 5 — P0 RFC: Team Task Bus
- 仕様化対象:
  - task CRUD
  - task state transitions
  - team単位の task list model
- 成果物: `docs/rfc-team-task-bus.md`

## Task 6 — Baseline Evals
- `evals/baseline-tasks.md` に team orchestration 評価タスクを定義
- `logs/baseline-results-YYYYMMDD.md` に結果を保存
