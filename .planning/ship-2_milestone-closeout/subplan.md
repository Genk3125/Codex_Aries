# Subplan: Milestone 2 クローズアウト

## メタ情報

- **Phase ID**: `ship-2_milestone-closeout`
- **Master Flow 位置**: Ship（Phase 18 — 最終）
- **依存先**: Phase 17（30 日 dogfood 成功）
- **主対象ファイル**: `MASTER_FLOW.md`, `ToDo.md`, `docs/CODEX_MAX_COMBINED_PLAN.md`
- **推定ワークロード**: 0.5 セッション
- **ステータス**: `not_started`

---

## 1. 目的

Milestone 2 を正式に閉じ、成果物を棚卸しし、次のフェーズ（Milestone 3 or 長期運用）への接続点を整理する。

## 2. 具体的な作業ステップ

### Step 1: 成果物の棚卸し

以下を一覧化して記録:
- 作成した Python ファイル（総行数、機能概要）
- 作成したドキュメント
- 作成した計画文書
- 達成した指標値

### Step 2: ToDo.md の更新

- Now / Next / Safety / Later を全面的に書き換え
- Phase 1-18 で解決したものを削除
- 新しい未解決課題を Later に追加

### Step 3: MASTER_FLOW.md の完了記録

- Phase 18 を `done` にマーク
- 完了日を記録
- 「完了の定義」の各項目にチェックを入れる

### Step 4: リトロスペクティブ

以下を記録:
- **うまくいったこと**: 再利用したいプロセスやツール
- **うまくいかなかったこと**: 次のマイルストーンで変えるべきこと
- **学んだこと**: 予想外の発見
- **次にやるべきこと**: Milestone 3 の方向性

### Step 5: Git commit + tag

```bash
git add -A
git commit -m "milestone-2: complete — Tengu-level daily ops achieved"
git tag milestone-2-complete
```

## 3. 完了判定（Exit Criteria）

- [ ] 成果物棚卸しが完了
- [ ] ToDo.md が最新状態に更新
- [ ] MASTER_FLOW.md で「完了の定義」全項目にチェック
- [ ] リトロスペクティブが記録されている
- [ ] git tag `milestone-2-complete` が打たれている

## 4. リスク・注意

- クローズアウトを急いで省略すると、次のマイルストーンで同じ失敗を繰り返す
- Phase 17 の 30 日 dogfood を「だいたい良い」で終わらせない — 数値で判定する

## 5. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
