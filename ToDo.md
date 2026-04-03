# ToDo

_Updated: 2026-04-03_

このファイルは、現在の実装カーネルを前提にした「次にやること」だけを短く持つ。

参照先:
- 上位方針: `docs/CODEX_MAX_COMBINED_PLAN.md`
- 実行フローの親: `.planning/MASTER_FLOW.md`

## 状態ラベルの定義

- `実装完了`: コード/テスト/文書が揃っている状態
- `実運用完了`: real-world 運用証跡まで揃っている状態
- `provisional`: 実装完了だが、実運用完了の証跡が未充足

## Now（最優先）

- Phase 19 `m3-1_real-world-30day-dogfood` を開始し、Milestone 2 Ship を `final` 化する
- Phase 19 は `ready_to_run`（Step 1 完了）。Day 1 は 2026-04-06 JST、Step 2（日次運用記録）待ち

## Milestone 2（実装完了 / Ship provisional）

### Done
- ~~daily-driver パイプライン（run-task.sh / resume-task.sh）を作り、毎日使う状態にする（Phase 8）~~
- ~~context reduction を実装し、context 膨張の自動圧縮を可能にする（Phase 9）~~
- ~~Team Runtime 本実装化の境界を決定する（Phase 10）~~
- ~~computer-use の scope を凍結する（Phase 11）~~
- ~~computer-use MCP PoC を実装する（Phase 12）~~
- ~~Team Runtime MVP を本実装する（Phase 13）~~
- ~~auto-context パイプラインを daily-driver に統合する（Phase 14）~~
- ~~E2E 統合テスト 5 シナリオ（Phase 15）~~
- ~~eval ベースライン 6 指標測定（Phase 16）~~
- ~~compressed 30 cycles dogfood（Phase 17 provisional）~~
- ~~Milestone 2 provisional closeout（Phase 18 provisional）~~

### Pending（Ship finalization）
- real-world 30-day dogfood（calendar days）で最終 Ship 判定を確定する

## Milestone 3（95% 仕上げ）

### Done（Track B/C 実装完了）
- ~~Phase 20: trigger-layer-mvp — E2E PASS~~
- ~~Phase 21: worktree-runtime-tools-mvp — E2E 8/8 PASS~~
- ~~Phase 22: verifier-queue-standardization — E2E 6/6 PASS~~
- ~~Phase 23: team-runtime-deferred-priority — docs作成済み~~
- ~~Phase 24: docs-status-release-sync — check-status-sync.sh OK~~
- ~~Phase 25: ts-boundary-decision — Stay Python 確定~~

### Pending（Track A — 時間依存）
- Phase 19: real-world 30-day dogfood（Day 1 = 2026-04-06）

### Next（Phase 26 候補）
- Verifier Queue gate/chain opt-in（docs/team-runtime-deferred-priority.md D7）

## Not Now

- Codex 本体 fork
- full auto loop（multi-pass自動再試行）
- memory の本格実装
- TypeScript 移行（ts-boundary-decision.md で Stay Python 確定）
