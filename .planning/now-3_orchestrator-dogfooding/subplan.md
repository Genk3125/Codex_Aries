# Subplan: one_shot_orchestrator 実タスク dogfooding

## メタ情報

- **Phase ID**: `now-3_orchestrator-dogfooding`
- **Master Flow 位置**: Now
- **依存先**: `now-1`, `now-2`（compact_state + handoff が安定していること）
- **主対象ファイル**: `poc/one_shot_orchestrator.py`
- **副対象**: `logs/dogfood-journal.md`（新規作成）
- **推定ワークロード**: 2-3 セッション
- **ステータス**: `not_started`

---

## 1. 目的

orchestrator を実タスクで使い倒し、手動介入が必要になるパターンを収集・類型化する。

## 2. 背景・前提

- orchestrator は実験 3 シナリオ（small/medium/recovery）で動作確認済み
- ただし「模擬タスク」での検証であり、実際の開発作業での利用は未実施
- **不明点**: 実タスクで strict/fail-open のどちらが適切か、gate/chain のどちらが実用的か

### 選定基準（dogfood タスク）
- 失敗しても被害が限定的なタスク
- 30 分以内で完了する粒度
- gate と chain の両方を試せる組み合わせ

## 3. 具体的な作業ステップ

### Step 1: dogfood タスク候補を 3 つ選定

- **やること**: 以下の条件で実タスクを 3 つ選ぶ
  1. **Gate 適合**: 単一ステップの検証タスク（例: docs の整合性チェック）
  2. **Chain 適合**: 複数ステップの連結タスク（例: helper spec と実装の diff 確認 → 修正）
  3. **Recovery 適合**: 意図的に失敗させられるタスク（例: 存在しないファイルへの操作）
- **出力**: タスク候補リストを `logs/dogfood-journal.md` の冒頭に記録

### Step 2: 各タスクを orchestrator 経由で実行

- **やること**: 各タスクについて以下を実施
  1. orchestrator コマンドを組み立てる
  2. 実行し、出力 JSON を保存
  3. compact_state を実行してテンプレートを生成（now-1 成果物を使用）
  4. 手動介入が必要になった場合、**即座に journal に記録**
- **記録フォーマット**:
  ```markdown
  ### Task: <タスク名>
  - **日時**: YYYY-MM-DD HH:MM
  - **flow-mode**: gate | chain
  - **strict**: yes | no
  - **結果**: 成功 | 失敗（手動介入あり）
  - **手動介入内容**: <何をしたか>
  - **介入の原因カテゴリ**: parameter_mismatch | verifier_ambiguity | json_schema_gap | other
  - **介入なしで済ませるには**: <改善案>
  ```

### Step 3: 手動介入パターンの類型化

- **やること**: 3 タスク完了後に journal を分析
  1. 介入回数を集計
  2. 原因カテゴリ別に分類
  3. 最も頻出のパターンを特定
  4. 各パターンに対する改善案（自動化 or パラメータデフォルト化 or ドキュメント化）を記載
- **出力**: `logs/dogfood-journal.md` の末尾に「分析セクション」を追記

### Step 4: 改善案の優先順位付け

- **やること**: 類型化した介入パターンを Impact × Effort で優先順位付け
- **出力**: 改善案が next-1 以降の subplan に反映可能な形で整理されていること

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| `one_shot_orchestrator.py`: 各 helper 呼び出し前後 | タイムスタンプ（ボトルネック特定） | `print(f"[DEBUG][orch] {helper} start={time.time()}", file=sys.stderr)` |
| `one_shot_orchestrator.py`: `results.<helper>.ok == false` | 失敗 helper の stderr 内容 | subprocess の stderr を capture して出力 |
| `one_shot_orchestrator.py`: `--strict` 停止時 | 停止理由の構造化 | exit code だけでなく、停止理由 JSON を stderr に出す |
| orchestrator → compact_state 接続 | JSON ファイルの完全性 | `jq '.' output.json` の exit code で破損検知 |

## 5. 完了判定（Exit Criteria）

- [ ] 3 タスク以上を orchestrator 経由で完走（成功 or 制御された失敗）
- [ ] 手動介入パターンが 2 カテゴリ以上で類型化されている
- [ ] 類型化結果が `logs/dogfood-journal.md` に記録されている
- [ ] 改善案が次フェーズ（next-1 以降）の入力として使える形になっている

## 6. リスク・注意

- dogfood タスクで実ファイルを壊さないよう、**書き込み系タスクは /tmp 下で実施**
- strict モードで想定外の停止が起きた場合、journal に記録してから fail-open で再試行
- 3 タスクで十分な類型化ができない場合は追加タスクを検討（ただし 5 タスクを上限とする）

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
