# Subplan: TS Boundary Decision（必要時のみ実装着手）

## メタ情報

- **Phase ID**: `m3-7_ts-boundary-decision`
- **Master Flow 位置**: Milestone 3 / Phase 25
- **依存先**: `m3-6_docs-status-release-sync`
- **主対象ファイル**: `docs/ts-boundary-decision.md`（新規）, `docs/CODEX_MAX_COMBINED_PLAN.md`, `ToDo.md`
- **推定ワークロード**: 1 セッション
- **ステータス**: `not_started`

---

## 1. 目的

Python 実装を維持するか、TS へ寄せる境界を設けるかを判断し、以降の技術方針を固定する。

## 2. 背景・前提

- 現在の kernel は Python 中心で安定している
- TS 移行は効果もあるが、運用コスト増のリスクがある
- ここでは **意思決定** のみ行い、移行実装は別フェーズに分離する

## 3. 具体的な作業ステップ

### Step 1: 境界候補を抽出
- **対象**: runtime adapter / helpers / docs
- **やること**:
  - TS 化候補（CLI front / adapter interface / runtime core）を列挙
  - 各候補の依存と影響範囲を明記
- **検証**: 候補一覧が重複なく整理される

### Step 2: 比較評価（維持 vs 移行）
- **対象**: `docs/ts-boundary-decision.md`
- **やること**:
  - 開発速度、保守性、運用リスク、テスト容易性で比較
  - fail-open/strict 互換性の観点を必須化
- **検証**: 比較表と結論が 1 文書にまとまる

### Step 3: 判定と次アクション固定
- **対象**: `ToDo.md`, `docs/CODEX_MAX_COMBINED_PLAN.md`
- **やること**:
  - `Go TS boundary` か `Stay Python` を明示
  - どちらでも次の 1 フェーズを定義
- **検証**: 次手が一意に決まる

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| 候補抽出 | 見落とし | runtime/kernel/helper を横断レビュー |
| 比較表 | バイアス | 同一評価軸で採点 |
| 最終判定 | 曖昧さ | Go/No-Go を明示する |

## 5. 完了判定（Exit Criteria）

- [ ] TS 境界候補の一覧化
- [ ] 維持/移行の比較表完成
- [ ] Go/No-Go の明示判定
- [ ] ToDo/Plan へ次フェーズ反映

## 6. リスク・注意

- 実装議論に入りすぎて phase が肥大化しやすい
- 「なんとなく TS」判断を避ける
- 決めた後は 1 フェーズ分は方針を固定する

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
