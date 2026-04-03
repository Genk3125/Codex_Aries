# Codex_Aries

## Master Goal
Claude Code でオープンソース化されたデータ・コード資産を活用し、`codex CLI` の実運用能力（正確性・速度・自律性・再現性）を最大化する。

## Definition of “Maximize”
以下の 4 指標を継続改善する。
- **Quality**: タスク完了率、修正往復回数、レビュー指摘数
- **Speed**: 要件受領から初回有効アウトプットまでの時間
- **Reliability**: 失敗時の自己復旧率、再現可能な実行率
- **Leverage**: Skill/Automation 再利用率、横展開可能なテンプレート数

## Strategy
1. **Asset Ingestion**: Claude 側の公開資産を収集・分類・正規化  
2. **Capability Mapping**: Claude 資産 → Codex CLI 機能へ対応表を作成  
3. **Execution System**: Skill、テンプレート、評価ハーネスを実装  
4. **Closed-loop Improvement**: 実行ログに基づき改善を継続

## Current Status
- Milestone 1: 完了
- Milestone 2: 実装完了 / Ship provisional
- Milestone 3: Phase 19 `real-world 30-day dogfood` 着手準備済み

この repo には以下が含まれる。
- single-pass runtime kernel
- Team Runtime MVP
- computer-use evidence collector
- compact / handoff / recovery / notify / guard helpers
- friend 向け非破壊 bootstrap

## Immediate Next Actions
- real-world 30-day dogfood を開始し、Milestone 2 Ship を `final` 化する
- Trigger / Worktree / verifier queue の Milestone 3 phases を進める
- docs / status / release boundary を同期する

## Current Source Dataset
- Claude snapshot path: `/Users/kondogenki/Downloads/claude-code-main`
- 最新インテイク結果: `data/raw/claude-source-intake-latest.md`
- 変換優先度定義: `docs/CLAUDE_TO_CODEX_MIGRATION.md`

## Intake Command
```bash
./scripts/intake_claude_source.sh /Users/kondogenki/Downloads/claude-code-main data/raw/claude-source-intake-latest.md
```

## Project Artifacts
- `README.md`: プロジェクト全体方針
- `MASTER_PLAN.md`: 実行ロードマップと成果物定義
- `.planning/MASTER_FLOW.md`: 現在の実行フロー親文書
- `ToDo.md`: 今の最優先作業
- `scripts/intake_claude_source.sh`: 公開コードの構造インテイク
- `docs/CLAUDE_TO_CODEX_MIGRATION.md`: 移植優先順位
- `scripts/bootstrap-friend-codex.sh`: 友人環境向けの非破壊セットアップ
- `docs/friend-codex-setup-runbook.md`: 配布導入手順

## Distribution Synchronization Note

`~/.codex` に新しい wrapper、slash command、skill、agent を直接追加した場合は、その変更を friend/bootstrap 導線にも反映してから共有完了とみなす。
