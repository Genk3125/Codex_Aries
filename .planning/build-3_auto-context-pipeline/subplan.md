# Subplan: 自動 context パイプライン

## メタ情報

- **Phase ID**: `build-3_auto-context-pipeline`
- **Master Flow 位置**: Build（Phase 14）
- **依存先**: Phase 8（daily-driver）, Phase 9（context-reduction）
- **主対象ファイル**: `scripts/run-task.sh` 拡張, `poc/context_compactor.py`
- **推定ワークロード**: 1-2 セッション
- **ステータス**: `not_started`

---

## 1. 目的

Phase 8 の daily-driver パイプラインと Phase 9 の context_compactor を統合し、「context が膨張したら自動で圧縮して継続」する自律パイプラインを完成させる。

## 2. 背景・前提

- Phase 8 で run-task.sh / resume-task.sh が動いている
- Phase 9 で context_compactor が動いている
- **未接続**: 両者が独立に存在し、手動で compactor を呼ぶ必要がある

## 3. 具体的な作業ステップ

### Step 1: run-task.sh に context 監視を組み込む

- orchestrator 出力の JSON サイズを監視
- 閾値（例: 50KB）を超えたら自動で context_compactor を呼ぶ
- 圧縮後の compact.md を次ターン用に保存

### Step 2: resume-task.sh に圧縮済み context を自動入力

- resume 時に compacted-context.json があればそちらを優先使用
- compact.json との差分がある場合は警告表示

### Step 3: 自動圧縮 → 自動再開の連結テスト

- 意図的に大きな出力を生成するタスクで実行
- 閾値超過 → 自動圧縮 → resume → 完走 のフルパスを検証

## 4. 完了判定（Exit Criteria）

- [ ] context 膨張時に自動で compactor が呼ばれる
- [ ] 圧縮後に resume が自動で正しい context を使う
- [ ] 手動介入なしで「膨張 → 圧縮 → 継続」が動作する

## 5. リスク・注意

- 自動圧縮のタイミングが早すぎると必要な情報を捨てる → 閾値を保守的に設計
- 圧縮後に resume が失敗するケースへの fallback → 圧縮前の raw JSON を保持

## 6. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
