# Claude Source → Codex CLI Migration Priorities

## Input Source
- Snapshot path: `/Users/kondogenki/Downloads/claude-code-main`
- Focus: `src/` (TypeScript/Bun CLI implementation)

## Strategic Principle
Claude Code のコードをそのまま移植するのではなく、**設計思想を抽出して Codex CLI の既存運用へ適応**する。

## Priority Matrix

### P0 (即時着手)
1. **Permission Decision Pipeline**
   - 参照: `src/hooks/toolPermission/PermissionContext.ts`
   - 目的: ツール実行前後の許可判定・ログ・フック連携の標準化
2. **Tool/Command Registry Determinism**
   - 参照: `src/tools.ts`, `src/commands.ts`
   - 目的: 有効化条件（feature/env）を明示化し、再現可能な実行構成を作る
3. **Skill Discovery & Frontmatter Contract**
   - 参照: `src/skills/loadSkillsDir.ts`
   - 目的: skill frontmatter のスキーマとロード順序を固定し、挙動のぶれを削減

### P1 (短期)
1. **Plugin Command/Skill Loader**
   - 参照: `src/utils/plugins/loadPluginCommands.ts`
   - 目的: プラグイン由来コマンドの名前空間衝突回避・重複排除
2. **Evaluation Harness**
   - 目的: task_success_rate / first_valid_output_time を計測する基盤を先に作る

### P2 (中期)
1. **Session Memory / Context Compaction**
2. **Remote/Bridge 運用モデル**
3. **Feature-flag build pruning の設計転用**

## Non-goals
- Claude の内部実装をそのまま再配布すること
- ライセンス/利用条件を未確認のままコードを取り込むこと

## Done Definition (このプロジェクト)
- 上位 3 テーマ (P0) で「設計差分メモ + PoC 実装 + 指標改善」を 1 サイクル完了
