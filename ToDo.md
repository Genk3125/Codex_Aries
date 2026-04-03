# ToDo

_Updated: 2026-04-03_

このファイルは、現在の実装カーネルを前提にした「次にやること」だけを短く持つ。

参照先:
- 上位方針: `docs/CODEX_MAX_COMBINED_PLAN.md`
- 実行フローの親: `.planning/MASTER_FLOW.md`

## Done (Milestone 1: Phase 1-7)

- ~~`compact_state_helper` を実運用フローへ組み込み、次ターン開始時の入力テンプレートを固定する~~
- ~~`handoff_helper` の Markdown を `verifier-contract.md` に寄せた貼り付けテンプレートへ整える~~
- ~~`one_shot_orchestrator` を実タスクで継続 dogfood して、手動介入点を記録する~~
- ~~`compact_state` から各 helper へ渡す `--from-compact` 変換を追加する~~
- ~~通知層 `notify_helper` を追加する~~
- ~~`verifier-cmd` の運用ルール固定 (exit code 0/1/2/3+)~~
- ~~loop guard の整合確認 + auto-retry 非混入保証~~

## Now (Milestone 2: Settle)

- daily-driver パイプライン（run-task.sh / resume-task.sh）を作り、毎日使う状態にする（Phase 8）
- context reduction を実装し、context 膨張の自動圧縮を可能にする（Phase 9）

## Next (Milestone 2: Scope + Build)

- Team Runtime 本実装化の境界を決定する（Phase 10）
- computer-use の scope を凍結する（Phase 11）
- computer-use MCP PoC を実装する（Phase 12）
- Team Runtime MVP を本実装する（Phase 13）
- auto-context パイプラインを daily-driver に統合する（Phase 14）

## Later (Milestone 2: Harden + Ship)

- E2E 統合テスト 5 シナリオ（Phase 15）
- eval ベースライン 6 指標測定（Phase 16）
- 30 日間 daily dogfood（Phase 17）
- Milestone 2 クローズアウト（Phase 18）

## Not Now

- Codex 本体 fork
- full auto loop
- trigger / worktree の本実装
- memory の本格実装
- cron / remote trigger / sleep
