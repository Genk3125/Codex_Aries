# MASTER PLAN

## 0) North Star
**目的**: Claude Code の公開資産を再利用して、Codex CLI の成果品質と開発速度を継続的に引き上げる。

## 1) Phase 1 — Source & Compliance Foundation
### Deliverables
- 公開資産インベントリ（リポジトリ、ドキュメント、サンプル、評価データ）
- ライセンス分類表（利用可否、要帰属、再配布条件）
- 取り込み優先順位（Impact × Effort）

### Current Inputs
- Claude snapshot: `/Users/kondogenki/Downloads/claude-code-main`
- Intake report: `data/raw/claude-source-intake-latest.md`
- Priority map: `docs/CLAUDE_TO_CODEX_MIGRATION.md`

### Exit Criteria
- 優先度 A/B/C が付与された収集リストが存在する
- 利用不可資産が除外ルールとして明文化されている

## 2) Phase 2 — Capability Mapping
### Deliverables
- Claude 資産の要素分解（プロンプト設計、ツール呼び出し、評価方法）
- Codex CLI 対応マップ（再利用可能 / 要変換 / 非対応）
- ギャップ一覧（追加実装が必要な機能）

### Exit Criteria
- 上位 20 ユースケースに対する対応方針が確定している

## 3) Phase 3 — System Implementation
### Deliverables
- Codex CLI 向け Skill セット（用途別）
- 実行テンプレート（調査、実装、検証、デプロイ）
- 評価ハーネス（成功率・速度・再現性を測定）

### Exit Criteria
- ベースライン比で定量改善が確認できる（最低 1 指標）

## 4) Phase 4 — Continuous Optimization
### Deliverables
- 失敗パターン辞書（原因・再発防止・回避策）
- 改善ループ（週次レビュー + 重点改善）
- 再利用可能な「勝ちパターン」カタログ

### Exit Criteria
- 連続 2 サイクル以上で改善トレンドが維持される

## Metrics (Starter Set)
- `task_success_rate`
- `first_valid_output_time`
- `self_recovery_rate`
- `rework_cycles_per_task`
- `template_reuse_rate`

## Repo Bootstrap (Suggested)
```text
.
├── README.md
├── MASTER_PLAN.md
├── data/
│   ├── raw/
│   └── normalized/
├── skills/
├── evals/
└── logs/
```

## This Week (Concrete)
1. `PermissionContext` / `tools.ts` / `commands.ts` の設計差分メモを作成  
2. Codex CLI 側で再利用する frontmatter スキーマの最小仕様を決定  
3. 評価タスク 10 件を作成（難易度を 3 段階）  
4. 初回ベースライン評価を実行し、結果を `logs/` に保存
