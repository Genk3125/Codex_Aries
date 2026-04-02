# Subplan: verifier-cmd 運用ルール固定

## メタ情報

- **Phase ID**: `next-3_verifier-cmd-rules`
- **Master Flow 位置**: Next（最後）
- **依存先**: `now-3`（dogfooding で PARTIAL の実運用パターンが判明していること）, `now-2`（handoff 整合）
- **主対象ファイル**: `verifier-contract.md`
- **副対象**: `poc/verifier_gate_helper.py`, `docs/one-shot-orchestrator-experiment-report.md`
- **推定ワークロード**: 1-2 セッション
- **ステータス**: `not_started`

---

## 1. 目的

verifier-cmd の verdict（PASS / PARTIAL / FAIL）の扱いを実験結果に基づいて固定し、orchestrator がどの verdict でどう分岐するかを明文化する。

## 2. 背景・前提

- 実験レポートで PARTIAL が `TASK_STATE_MISMATCH` として出現（medium シナリオ）
- fail-open ではフロー継続、strict では停止 — この判断は正しかったが、ルールが暗黙的
- **未解決問題**:
  - PARTIAL の「条件付き続行」とは何か？
  - verifier-cmd の exit code 規約は？
  - verifier-cmd の stdout に verdict 以外の情報をどこまで許可するか？

### 現在の暗黙ルール（実験から推定）
```
PASS   → 続行
PARTIAL → fail-open: 続行, strict: 停止
FAIL   → 常に停止
```

## 3. 具体的な作業ステップ

### Step 1: 実験結果から PARTIAL の実パターンを収集

- **やること**:
  1. 実験レポート（`docs/one-shot-orchestrator-experiment-report.md`）から PARTIAL が出たケースを再確認
  2. now-3 dogfooding の journal から PARTIAL が出たケースを収集
  3. パターンを類型化: PARTIAL が出る条件と、その後のフロー結果
- **出力**: `.planning/next-3_verifier-cmd-rules/partial-patterns.md`

### Step 2: verdict 分岐ルールを文書化

- **やること**: 以下のルール表を fixed にする
  ```
  | Verdict | fail-open 時 | strict 時 | 条件 |
  |---------|-------------|----------|------|
  | PASS    | 続行        | 続行      | 該当なし |
  | PARTIAL | 続行        | 停止      | 未検証項目を Unverified Items に記録 |
  | PARTIAL | ??? 条件付き続行 ??? | 停止 | ← この行を固定する |
  | FAIL    | 停止        | 停止      | 該当なし |
  ```
- **決定事項**: 「条件付き続行」を認めるか、PARTIAL は一律 fail-open=続行とするか

### Step 3: verifier-cmd インターフェース規約を固定

- **やること**: 以下を `verifier-contract.md` に追記する
  - **exit code 規約**:
    - `0` = PASS
    - `1` = FAIL
    - `2` = PARTIAL
    - `3+` = UNKNOWN（verifier 自体の異常）
  - **stdout 規約**:
    - 1 行目: `PASS` / `PARTIAL` / `FAIL`（verdict 判定に使用）
    - 2 行目以降: 自由形式（人間向け詳細。パースされない）
  - **stderr 規約**: デバッグ専用。verdict 判定に使用しない

### Step 4: verifier_gate_helper の実装を規約に合わせる

- **対象**: `poc/verifier_gate_helper.py`
- **やること**:
  1. exit code の判定ロジックが Step 3 の規約と一致しているか確認
  2. stdout 1 行目のパースが正しいか確認
  3. 差分があれば修正
- **検証**:
  ```bash
  # mock_verifier で各 exit code をテスト
  echo "PASS" > /tmp/mock_pass.sh && chmod +x /tmp/mock_pass.sh
  echo -e '#!/bin/bash\necho "PARTIAL"\nexit 2' > /tmp/mock_partial.sh && chmod +x /tmp/mock_partial.sh
  echo -e '#!/bin/bash\necho "FAIL"\nexit 1' > /tmp/mock_fail.sh && chmod +x /tmp/mock_fail.sh
  ```

### Step 5: 規約を verifier-contract.md に正式追記

- **対象**: `verifier-contract.md`
- **やること**: Step 2-3 の決定事項を `## verifier-cmd インターフェース規約` セクションとして追記
- **検証**: `verifier-contract.md` を読んだ第三者が、verifier-cmd を実装できること

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| `verifier_gate_helper.py`: verifier-cmd 実行直後 | stdout / stderr / exit_code の全文 | `[DEBUG][vgate] stdout=, stderr=, exit=` を stderr |
| `verifier_gate_helper.py`: verdict パース | パース結果が PASS/PARTIAL/FAIL のいずれかか | パース失敗時に `[DEBUG][vgate] UNKNOWN verdict` を stderr |
| orchestrator: verdict 分岐 | どの分岐に入ったか | `[DEBUG][orch] verdict=X, mode=strict/fail-open, action=continue/stop` を stderr |

## 5. 完了判定（Exit Criteria）

- [ ] PARTIAL の実パターンが 2 件以上収集されている
- [ ] verdict 分岐ルール表が確定し、曖昧な行がゼロ
- [ ] exit code / stdout / stderr の規約が `verifier-contract.md` に追記されている
- [ ] verifier_gate_helper が規約通りに動作することがテストされている
- [ ] mock verifier 3 パターン（PASS/PARTIAL/FAIL）で E2E が通る

## 6. リスク・注意

- PARTIAL の扱いを厳格にしすぎると、fail-open の利便性が下がる → バランスが重要
- 外部 verifier-cmd の品質は制御できない → 「verifier 自体の異常」と「検証結果としての FAIL」を区別する必要がある（exit code 3+ で対応）
- この規約は decision record として残すべき（後から「なぜこう決めたか」を追跡できるように）

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
