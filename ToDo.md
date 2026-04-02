# ToDo

_Updated: 2026-04-03_

このファイルは、現在の実装カーネルを前提にした「次にやること」だけを短く持つ。

参照先:
- 上位方針: `/Users/kondogenki/AI Agent Maximizer/docs/CODEX_MAX_COMBINED_PLAN.md`
- 実行粒度の旧タスク分解: `/Users/kondogenki/AI Agent Maximizer/docs/EXECUTION_TASK_BREAKDOWN.md`
- 初期の次タスク一覧: `/Users/kondogenki/AI Agent Maximizer/docs/NEXT_TASKS.md`

## Now

- `compact_state_helper` を実運用フローへ組み込み、次ターン開始時の入力テンプレートを固定する
- `handoff_helper` の Markdown を `verifier-contract.md` に寄せた貼り付けテンプレートへ整える
- `one_shot_orchestrator` を実タスクで継続 dogfood して、手動介入点を記録する

## Next

- `compact_state` から `recovery_next_helper` / `handoff_helper` へ渡す `resume-input` 変換 helper を追加する
- `preflight guard` / `post-run guard` の stop reason を運用通知に繋ぐ薄い通知層を追加する
- `verifier-cmd` の運用ルールを固定し、`PASS / PARTIAL / FAIL` の扱いを実験結果で詰める

## Safety

- loop guard の preflight / post-run を実タスクで再確認する
- `attempt_count`, `max_retries`, `escalate_after_n`, `stop_condition` を `recovery-playbook.md` とズレなく保つ
- single-pass を壊す自動再試行はまだ入れない

## Later

- true `/compact` 相当の compaction layer を入れる
- transcript ではなく state/evidence/next-actions を残す context reduction を強化する
- full automation 前提の loop guard 拡張を検討する
- Team Runtime の本実装化対象と `~/.codex` 運用層の境界を再整理する

## Not Now

- Codex 本体 fork
- full auto loop
- trigger / worktree の本実装
- memory の本格実装
