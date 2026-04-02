# Codex Session Minimal Orchestration Experiment

- Version: 0.1
- Date: 2026-04-03
- Purpose: `~/.codex` の runtime adapter と custom agents（`coordinator` / `verifier`）で、実セッション運用フローを1本に固定する

## 1. 適用範囲
- 対象: Codex セッションでの手動オーケストレーション実験
- 使うもの:
  - `codex-runtime`（`~/.codex/runtime-adapter/codex-runtime`）
  - `coordinator`（`~/.codex/agents/coordinator.toml`）
  - `verifier`（`~/.codex/agents/verifier.toml`）
- 使わないもの:
  - 本体 fork / UI / trigger / worktree / 完全自動 orchestration

## 2. 事前準備（セッション開始時）
```bash
source /Users/kondogenki/.codex/runtime-adapter/runtime-adapter.env
alias codex-runtime='/Users/kondogenki/.codex/runtime-adapter/codex-runtime'
codex-runtime ops
```

確認:
- `ops` の出力に `team_create`, `send_message`, `task_create`, `runtime_reconcile_all` が含まれること。

## 3. 実運用フロー（順序固定）

### Step 0: coordinator 起動（計画担当）
- coordinator に「今回の変更目的・対象ファイル・完了条件」を渡す。
- ここでは **理解の合成** まで担当させる（最終検証はさせない）。

### Step 1: team_create
```bash
codex-runtime team-create "exp-alpha" "exp-alpha-1"
```
- 出力から `team_id` / `leader_agent_id` を控える。

### Step 2: task_create
```bash
codex-runtime task-create <team_id> "implement minimal change" <leader_agent_id> ready "exp-task-1"
```

### Step 3: send_message（direct 1回）
```bash
codex-runtime send-message <team_id> <leader_agent_id> <leader_agent_id> "start implementation" "exp-msg-1"
```

### Step 4: 実装（手動）
- coordinator の計画に沿って通常どおり実装を行う。
- このフェーズは runtime adapter の責務外。

### Step 5: verifier 実施（独立検証）
- verifier を起動し、`PASS/PARTIAL/FAIL` を取得する。
- `PARTIAL` / `FAIL` なら修正タスクを追加して Step 2 に戻る。

### Step 6: runtime_reconcile_all
```bash
codex-runtime reconcile-all
```
- startup 相当の再整合を手動で実施し、残タスク/owner/message の不整合を確認する。

## 4. fail-open / strict の使い分け

### fail-open（既定）
- 対話中の連続運用向き。
- エラー時も終了コード `0`、JSON envelope の `ok=false` / `error` で分岐判断する。

### strict
- 実験ゲート（成功条件）を明確にしたい時だけ使う。
- 例:
```bash
codex-runtime --strict send-message <team_id> <leader_agent_id> <leader_agent_id> "gate check"
```
- エラー時は non-zero で止まる。

## 5. 代表シナリオ（1本）
**シナリオ名**: Single-change orchestration smoke test

1. coordinator が変更計画を確定
2. `team-create`
3. `task-create`
4. `send-message`
5. 実装1件
6. verifier 判定取得
7. `reconcile-all`

成功条件:
- runtime 4操作がすべて実行できる
- verifier が verdict を返せる
- `reconcile-all` 後に致命的な不整合が残らない

## 6. 失敗時の recovery 分岐

### A. runtime adapter エラー（fail-open）
- 条件: `ok=false` かつ exit=0
- 対応:
  1. `error.code` を記録
  2. 同操作を `--strict` で再実行し再現確認
  3. 再現したら coordinator に復旧タスク化させる

### B. runtime adapter エラー（strict）
- 条件: exit non-zero
- 対応:
  1. その時点でフロー停止
  2. `team_list` / `task_list` / `message_list` で状態確認
  3. `reconcile-all` を先に実施して再試行

### C. verifier が PARTIAL/FAIL
- 条件: verifier verdict != PASS
- 対応:
  1. 追加修正を新タスク化（Step 2）
  2. 再実装
  3. verifier 再実行

## 7. 実施時チェックポイント（観測）
- コマンド出力 envelope:
  - `ok`, `fail_open`, `result`, `error` が常に存在
- runtime 保存状態:
  - `~/.codex/runtime-spike/.../control-plane/`
  - `~/.codex/runtime-spike/.../message-bus/`
  - `~/.codex/runtime-spike/.../task-bus/`
- verifier 出力:
  - `PASS/PARTIAL/FAIL`
  - 実行コマンド
  - 未検証項目

## 8. まだ手動な部分
- coordinator/verifier の起動・指示文作成
- `team_id` / `leader_agent_id` の受け渡し
- verifier 結果を task に反映する判断
- 実装と再実装のループ制御
