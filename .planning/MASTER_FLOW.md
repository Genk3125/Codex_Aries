# Master Flow

_Updated: 2026-04-03_

この文書は、`.planning/` 配下の subplans を読む順序と役割を定義する。
上位構想ではなく、**現在の実装カーネルを前提にした運用フロー**として使う。

参照先:
- 上位構想: `/Users/kondogenki/AI Agent Maximizer/docs/CODEX_MAX_COMBINED_PLAN.md`
- 現在の短期優先順位: `/Users/kondogenki/AI Agent Maximizer/ToDo.md`

## 位置づけ

- `docs/CODEX_MAX_COMBINED_PLAN.md`: 何を作るか
- `ToDo.md`: 今どこを進めるか
- `.planning/MASTER_FLOW.md`: どの subplan をどの順で開くか
- `.planning/*/subplan.md`: 実装エージェントに渡す超具体 plan

## 実行順

### Now

1. `now-1_compact-state-integration`
   - `/Users/kondogenki/AI Agent Maximizer/.planning/now-1_compact-state-integration/subplan.md`
2. `now-2_handoff-verifier-alignment`
   - `/Users/kondogenki/AI Agent Maximizer/.planning/now-2_handoff-verifier-alignment/subplan.md`
3. `now-3_orchestrator-dogfooding`
   - `/Users/kondogenki/AI Agent Maximizer/.planning/now-3_orchestrator-dogfooding/subplan.md`

### Next

1. `next-1_resume-input-helper`
   - `/Users/kondogenki/AI Agent Maximizer/.planning/next-1_resume-input-helper/subplan.md`
2. `next-2_notification-layer`
   - `/Users/kondogenki/AI Agent Maximizer/.planning/next-2_notification-layer/subplan.md`
3. `next-3_verifier-cmd-rules`
   - `/Users/kondogenki/AI Agent Maximizer/.planning/next-3_verifier-cmd-rules/subplan.md`

### Safety

- `safety_loop-guard-reconfirm`
  - `/Users/kondogenki/AI Agent Maximizer/.planning/safety_loop-guard-reconfirm/subplan.md`
  - `now-3` と並走する

## 使い方

1. `ToDo.md` を見て今の優先帯を決める
2. この文書で該当する subplan を開く
3. 実装エージェントには subplan 単位で渡す
4. 完了後は `ToDo.md` と subplan のステータスを更新する

## 原則

- master flow は薄く保つ
- 実装詳細は subplan に押し込む
- 1 subplan = 1 実行単位
- `Safety` は独立フェーズではなく、`Now` と並走で確認する
- `Later` / `Not Now` は `ToDo.md` と上位計画側で扱い、ここでは増やしすぎない

## 現状ステータス（2026-04-03 確認）

| Phase | Status | 備考 |
|-------|--------|------|
| now-1 | `not_started` | compact_state に Markdown 出力なし、orchestrator との自動接続なし |
| now-2 | `not_started` | handoff Markdown は独自形式。verifier-contract 6 セクション未対応 |
| now-3 | `not_started` | dogfood journal 未作成。実タスク使用記録なし |
| safety | `not_started` | guard パラメータ実装済みだが playbook との diff 未確認 |
| next-1 | `not_started` | resume_input_helper / --from-compact いずれも未実装 |
| next-2 | `not_started` | notify_helper 未実装 |
| next-3 | `not_started` | verifier exit code 規約未文書化。PARTIAL=2 の区別未実装 |

**最優先**: `now-1_compact-state-integration`（依存先なし、単独着手可能）

