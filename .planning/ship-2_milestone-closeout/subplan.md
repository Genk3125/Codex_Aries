# Subplan: Milestone 2 クローズアウト（provisional）

## メタ情報

- **Phase ID**: `ship-2_milestone-closeout`
- **Master Flow 位置**: Ship（Phase 18 — provisional closeout）
- **依存先**: Phase 17（compressed validation 成功、real-world 30-day は pending）
- **主対象ファイル**: `MASTER_FLOW.md`, `ToDo.md`, `docs/CODEX_MAX_COMBINED_PLAN.md`
- **推定ワークロード**: 0.5 セッション
- **ステータス**: `provisional`

---

## 1. 目的

Milestone 2 を **provisional** として閉じ、成果物を棚卸しし、real-world 30-day dogfood 完了までの残課題を明示する。

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

### Step 3: MASTER_FLOW.md の provisional 記録

- Phase 18 を `provisional` にマーク
- 完了日を記録
- 「compressed validation 完了 / real-world pending」を併記する

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

- [x] 成果物棚卸しが完了
- [x] ToDo.md が最新状態に更新
- [x] MASTER_FLOW.md で Milestone 2 provisional 状態が記録されている
- [x] リトロスペクティブが記録されている
- [x] git tag `milestone-2-complete` は運用ポリシーにより未実施（手動運用項目として明記）
- [ ] real-world calendar 30-day dogfood 完了後に final closeout へ更新する

## 4. リスク・注意

- クローズアウトを急いで省略すると、次のマイルストーンで同じ失敗を繰り返す
- Phase 17 の 30 日 dogfood を「だいたい良い」で終わらせない — 数値で判定する

## 5. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| 2026-04-03 | 成果物棚卸し + レトロスペクティブ文書を `docs/milestone-2-closeout.md` に作成 | 実装/評価/運用ログを統合し、Milestone 2 終了条件を明文化 | MASTER_FLOW/ToDo を同期 |
| 2026-04-03 | `MASTER_FLOW.md` の Ship フェーズを provisional として記録し、完了サマリを追記 | real-world 30-day pending を明示 | ToDo 更新 |
| 2026-04-03 | `ToDo.md` を Milestone 3 向け backlog + Ship finalization タスクへ刷新 | 未解決課題（real-world dogfood/trigger/worktree/full-auto/memory）を整理 | provisional closeout 完了 |
