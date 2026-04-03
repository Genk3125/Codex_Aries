# Subplan: E2E 統合テスト

## メタ情報

- **Phase ID**: `harden-1_e2e-integration-test`
- **Master Flow 位置**: Harden（Phase 15）
- **依存先**: Phase 12, 13, 14（Build フェーズ全完了）
- **主対象ファイル**: 新規 `tests/e2e/` ディレクトリ
- **推定ワークロード**: 2 セッション
- **ステータス**: `done`

---

## 1. 目的

Phase 8-14 で作った全コンポーネントを統合し、「日常タスク起動 → team 分担 → computer-use 検証 → context 圧縮 → 完走」のフルパスを E2E テストする。

## 2. 背景・前提

- 個別に動く: orchestrator, compact_state, handoff, notify, verifier_gate, computer_use, team_runtime, context_compactor
- **未検証**: 全部を連結して 1 つのタスクとして完走するかどうか

## 3. 具体的な作業ステップ

### Step 1: E2E テストシナリオ 5 本を設計

| # | シナリオ | 使用コンポーネント |
|---|---------|------------------|
| 1 | single-agent gate 成功 | run-task → orch → compact → notify |
| 2 | single-agent gate 失敗 → resume | run-task → fail → compact → resume → 成功 |
| 3 | single-agent + computer-use | run-task → orch → CU verifier → screenshot 検証 |
| 4 | 3-agent team タスク | run-task → team_runtime → 3x orch → leader 集約 |
| 5 | long-running + context 圧縮 | run-task → 3+ ターン → context 膨張 → 自動圧縮 → 完走 |

### Step 2: テストスクリプト作成

- `tests/e2e/run_all.sh` — 5 シナリオを順番に実行
- 各シナリオの PASS/FAIL 判定を明確に（exit code / 出力ファイルの存在で判定）

### Step 3: テスト実行 + 不具合修正

- 全 5 シナリオを実行し、失敗したものを修正
- 修正後に全テストを再実行して green を確認

## 4. 完了判定（Exit Criteria）

- [x] 5 シナリオの E2E テストスクリプトが存在する
- [x] 全 5 シナリオが PASS する
- [x] テスト結果が `tests/e2e/results/` に自動保存される

## 5. リスク・注意

- computer-use テストはヘッドレスブラウザが必要 → CI では skip 可能にする
- team runtime テストは 3 プロセス同時起動 → リソース制限に注意

## 6. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| 2026-04-03 | `tests/e2e/run_all.sh` を実装（5 シナリオを単発実行） | S1〜S5 を同一スクリプトで実行し、PASS/FAIL と成果物パスを集約 | 実行して調整 |
| 2026-04-03 | 初回実行で S5（resume優先判定）が失敗 | `rg` を fixed-string 判定へ修正（`-Fq`） | 再実行 |
| 2026-04-03 | 再実行で 5/5 PASS | `tests/e2e/results/2026-04-03T21-25-25/summary.md` へ保存 | Phase 16 へ |
