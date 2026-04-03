# Subplan: 評価ベースライン構築

## メタ情報

- **Phase ID**: `harden-2_eval-baseline`
- **Master Flow 位置**: Harden（Phase 16）
- **依存先**: Phase 15（E2E テスト通過後）
- **主対象ファイル**: 新規 `eval/` ディレクトリ
- **推定ワークロード**: 1-2 セッション
- **ステータス**: `not_started`

---

## 1. 目的

CODEX_MAX_COMBINED_PLAN の Stream F (Eval) で定義された指標を実測し、「Tengu 級」の定量的ベースラインを確立する。Ship phase 前に「どこが弱いか」を数値で把握する。

## 2. 指標（COMBINED_PLAN Section 5 から）

| 指標 | 定義 | 目標値 |
|------|------|--------|
| task_success_rate | タスク完走率 | ≥ 80% |
| first_valid_output_time | 初回有効出力までの時間 | ≤ 5 min |
| self_recovery_rate | 自動復旧成功率 | ≥ 50% |
| rework_cycles_per_task | 1 タスクあたりの手戻り回数 | ≤ 2 |
| verification_pass_rate | verifier PASS 率 | ≥ 70% |
| team_completion_rate | team タスク完走率 | ≥ 60% |

## 3. 具体的な作業ステップ

### Step 1: 評価タスクセット 10 件を固定

- 難易度: easy (3), medium (4), hard (3)
- 種類: bugfix, feature add, refactor, docs update, UI change
- 再現可能にするため、入力を `eval/tasks/` に固定

### Step 2: ベースライン測定

- 10 タスクを run-task.sh で実行
- 各指標を記録
- `eval/baseline-results.md` に結果を書き出し

### Step 3: ウィークポイント分析

- 目標値を下回った指標を特定
- 改善策を eval/baseline-results.md に記録
- Ship phase に進む前に対応する

## 4. 完了判定（Exit Criteria）

- [ ] 10 件のタスクセットが `eval/tasks/` に固定されている
- [ ] 6 指標のベースライン値が測定されている
- [ ] 各指標が目標値を上回っている、または改善策が明確

## 5. リスク・注意

- タスクの難易度が偏ると指標が歪む → easy/medium/hard のバランスを守る
- ベースライン測定中にパイプラインのバグが見つかる可能性がある → Phase 15 で洗い出し済みのはず

## 6. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
