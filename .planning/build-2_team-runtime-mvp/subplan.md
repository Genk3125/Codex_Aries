# Subplan: Team Runtime MVP

## メタ情報

- **Phase ID**: `build-2_team-runtime-mvp`
- **Master Flow 位置**: Build（Phase 13）
- **依存先**: Phase 10（boundary-decision.md で scope 確定済み）
- **主対象ファイル**: 新規 `src/team_runtime/` ディレクトリ（PoC から昇格）
- **推定ワークロード**: 3-5 セッション
- **ステータス**: `done`

---

## 1. 目的

Phase 10 で確定した scope に基づき、PoC の Team Runtime コードを本実装に昇格させる。3+ agent がタスクを分担して完走できる MVP を作る。

## 2. 背景・前提

- `poc/team_control_plane.py`, `poc/team_message_bus.py`, `poc/team_task_bus.py` が既存
- Phase 10 の boundary-decision.md で In-Scope が確定している
- 本実装は `poc/` から `src/team_runtime/` に移動し、テスト付きにする

## 3. 具体的な作業ステップ

### Step 1: PoC → src への昇格（リファクタ）

- In-Scope 判定された機能のみを `src/team_runtime/` にコピー
- 型ヒント、docstring、error handling を本実装品質に引き上げ
- Out-of-Scope 機能は `poc/` に残し、Deprecated 扱い

### Step 2: orchestrator パイプラインとの接続

- one_shot_orchestrator が team_runtime を使ってメンバーにタスクを割り当てる
- leader → member へのメッセージ送信が team_message_bus 経由で動く

### Step 3: 3-agent タスクの完走テスト

テストシナリオ:
1. leader がタスクを 3 つ作成
2. 各 member にタスクを割り当て
3. 各 member が独立に orchestrator パイプラインを実行
4. leader が全タスクの結果を集約
5. verifier が最終判定

### Step 4: resume テスト

- 途中で停止 → team state を保存 → 再開 → 完走

## 4. 完了判定（Exit Criteria）

- [x] `src/team_runtime/` に本実装コードが存在する
- [x] 3-agent タスクのシナリオが完走する
- [x] team state を保存して resume できる
- [x] orchestrator パイプラインから team_runtime が呼べる

## 5. リスク・注意

- scope creep: Phase 10 の boundary-decision 外の機能を追加しない
- PoC から昇格する際に振る舞いが変わらないことを検証する
- 並列実行（3 agent 同時）のリソース管理に注意

## 6. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| 2026-04-03 | `poc/team_*` を `src/team_runtime/*` へ昇格し import を package へ調整 | control/message/task の API を維持したまま `src` 側に移行 | adapter 接続を更新 |
| 2026-04-03 | `poc/codex_runtime_adapter.py` を `src.team_runtime` 優先 import + PoC fallback に変更 | orchestrator からの operation 入口を壊さず昇格を反映 | 3-agent シナリオ検証へ |
| 2026-04-03 | `tests/e2e/team_runtime_mvp.py` を追加し 3-member task + delete/reconcile resume を検証 | 3 task 完走、message delivered、startup reconcile で deleting→deleted を確認 | Phase 14 へ |
