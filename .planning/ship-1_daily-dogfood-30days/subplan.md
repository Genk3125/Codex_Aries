# Subplan: 30 日間 daily dogfood

## メタ情報

- **Phase ID**: `ship-1_daily-dogfood-30days`
- **Master Flow 位置**: Ship（Phase 17）
- **依存先**: Phase 16（eval baseline 測定済み。目標値を上回っている、または改善策が実施済み）
- **主対象ファイル**: `logs/daily-dogfood-30.md`（新規）
- **推定ワークロード**: 30 日間（日々 15-30 分の記録）
- **ステータス**: `not_started`

---

## 1. 目的

**「Tengu 的な強さが日常運用で再現されている」ことを 30 日間の実績で証明する。**

PoC ではなく、E2E テストでもなく、**実際の日常開発タスクで 30 日間使い続けて**、安定性・有用性・改善サイクルを実証する。

## 2. 背景・前提

- Phase 8-16 で全コンポーネントが統合・検証済み
- eval baseline で 6 指標が測定済み
- **この Phase で初めて「使い続ける」ことを検証する**

## 3. 具体的な作業ステップ

### Step 1: daily log フォーマットを固定

```markdown
## Day N (YYYY-MM-DD)

### 使用タスク
- タスク名: ...
- flow: gate / chain / team
- 結果: 成功 / 失敗 → 復旧 / 失敗 → escalation

### 手動介入
- 回数: N
- 内容: ...

### 気づき
- ...

### 指標
- task_success: yes / no
- manual_interventions: N
- context_compression_triggered: yes / no
- computer_use_triggered: yes / no
```

### Step 2: 30 日間実行

- 毎日 1 つ以上のタスクを run-task.sh / team runtime で実行
- 結果を `logs/daily-dogfood-30.md` に記録
- 週次で指標を集計

### Step 3: 週次レビュー（Day 7, 14, 21, 28）

- 指標トレンドを確認
- 悪化している項目があれば修正を挿入
- 修正は MASTER_FLOW に hotfix phase として記録

### Step 4: 30 日完了時の最終判定

以下の全てを満たしたら Ship 成功:
1. 30 日中 25 日以上使用
2. task_success_rate ≥ 80%
3. 週次で指標が悪化トレンドでない
4. 「手動介入なしの日」が 50% 以上
5. 「computer-use を使ったタスク」が 5 回以上
6. 「team runtime を使ったタスク」が 3 回以上

## 4. 完了判定（Exit Criteria）

- [ ] 30 日間の daily log が存在する
- [ ] 上記 6 条件を全て満たす
- [ ] 最終判定が logs/daily-dogfood-30.md 末尾に記録されている

## 5. リスク・注意

- 30 日は長い — モチベーション維持が課題 → 週次レビューで短期フィードバックを入れる
- 途中でパイプラインが壊れたら修正に時間を取られる → 修正日はタスク実行日としてカウントする
- 30 日間に大きなリファクタを入れない（安定運用テスト中）

## 6. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
