# Subplan: Team Runtime Deferred Items Priority

## メタ情報

- **Phase ID**: `m3-5_team-runtime-deferred-priority`
- **Master Flow 位置**: Milestone 3 / Phase 23
- **依存先**: `m3-2_trigger-layer-mvp`, `m3-3_worktree-runtime-tools-mvp`, `m3-4_verifier-queue-standardization`
- **主対象ファイル**: `docs/team-runtime-deferred-priority.md`（新規）, `ToDo.md`, `.planning/MASTER_FLOW.md`
- **推定ワークロード**: 1 セッション
- **ステータス**: `not_started`

---

## 1. 目的

deferred 項目（leader handoff / task auto-reassign / message retry など）の優先順位を定量化し、次の実装順を固定する。

## 2. 背景・前提

- 現在 deferred 項目は散在している
- 実装前に優先順位を決めないと scope が膨張する
- 新しい runtime 機能追加より、優先度の固定が先

## 3. 具体的な作業ステップ

### Step 1: deferred 項目の棚卸し
- **対象**: `docs/team-runtime-mvp.md`, `docs/milestone-2-closeout.md`, `ToDo.md`
- **やること**:
  - deferred 項目を 1 一覧へ集約
  - 各項目に依存関係と既知リスクを付与
- **検証**: 重複なしの一覧ができる

### Step 2: 優先度評価マトリクス作成
- **対象**: `docs/team-runtime-deferred-priority.md`
- **やること**:
  - Impact / Risk / Effort / Operability を 5 段階で採点
  - 総合スコアで上位 3 件を確定
- **検証**: 採点根拠が各項目に明記される

### Step 3: 実装準備の切り出し
- **対象**: `.planning/MASTER_FLOW.md`, `ToDo.md`
- **やること**:
  - 上位 2-3 件を future phase として追加
  - 下位項目は backlog に退避
- **検証**: next phase が一意に決まる

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| 項目一覧 | 抜け漏れ | docs 横断でキーワード検索 |
| 採点 | 主観偏り | 1 行根拠を必須化 |
| ToDo/Flow 反映 | 不整合 | 反映後に相互参照を確認 |

## 5. 完了判定（Exit Criteria）

- [ ] deferred 項目一覧が 1 文書に統合
- [ ] 優先度スコアと根拠が明記
- [ ] 上位項目が次フェーズへ反映
- [ ] MASTER_FLOW と ToDo が同期

## 6. リスク・注意

- 採点軸が曖昧だと合意形成できない
- 技術的難易度のみで優先を決めない（運用痛点を重視）
- 「今やらない理由」も明記する

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
