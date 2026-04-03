# TS Boundary Decision (Phase 25)

_Date: 2026-04-04_

## 1. TS化候補の抽出

| 候補層 | 現状 | TS化の動機 | 依存/影響範囲 |
|--------|------|-----------|--------------|
| CLI front (run-task.sh / resume-task.sh) | bash | 型安全な arg parsing、テスト容易性 | scripts/ 全体 |
| Adapter interface (codex_runtime_adapter.py) | Python | Claude Code との型整合、SDK統合 | poc/ 全体、E2E tests |
| Runtime core (src/team_runtime/*.py) | Python | Claude Code coordinatorMode との統合 | 全 Phase 依存 |
| Slash commands (src/slash_commands/) | Python | Claude Code slash layer との型整合 | slash_command_adapter.py |
| Helpers (poc/compact_state_helper.py 等) | Python | 再利用性向上 | daily-driver pipeline |

## 2. 比較評価

| 評価軸 | Python 維持 | TS 移行 |
|--------|------------|---------|
| 開発速度 | ◎ 現在の実装ペース維持 | △ 移行コスト + 学習コスト |
| 保守性 | ○ 一言語統一 | △ 二言語混在リスク |
| 運用リスク | ◎ 既存 daily-driver 無影響 | △ 全スクリプト再検証必要 |
| テスト容易性 | ○ pytest で統一済み | ○ Jest/Vitest + 型安全 |
| fail-open/strict 互換 | ◎ 現行 envelope 規約が Python で安定 | △ 移行時に規約再実装リスク |
| Claude Code 統合 | △ 型定義なし | ◎ SDK の型が直接使える |

## 3. 判定

**判定: Stay Python（全層で Python 維持）**

### 根拠

1. **Phase 19 dogfood が進行中** — runtime を移行して daily-driver を壊すリスクが高い
2. **fail-open/strict envelope** が Python で安定稼働中。移行時の再実装リスクを取る必要がない
3. **Claude Code 統合の必要性は低い** — Codex CLI は Python adapter 経由で Claude Code を呼ぶ構造であり、内部を TS にする直接的な利点がない
4. **Slash commands 層は最小限** — src/slash_commands/ は現時点で 1 コマンドのみ。TS化する規模でない

### TS を検討すべきタイミング（条件）

- Codex CLI を Claude Code SDK に直接統合する要件が発生した場合
- Python runtime の型安全性が原因のバグが繰り返し発生した場合
- 複数チームで開発規模が拡大し、型定義なしの保守が困難になった場合

## 4. 次フェーズへの反映

- **Next phase**: Phase 26 = Verifier Queue gate/chain opt-in（D7、team-runtime-deferred-priority.md 参照）
- TypeScript 移行は `Not Now` リストへ追加
