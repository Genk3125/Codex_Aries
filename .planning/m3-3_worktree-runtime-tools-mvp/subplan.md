# Subplan: Worktree Runtime Tools MVP

## メタ情報

- **Phase ID**: `m3-3_worktree-runtime-tools-mvp`
- **Master Flow 位置**: Milestone 3 / Phase 21
- **依存先**: `m3-2_trigger-layer-mvp`（独立実装可）
- **主対象ファイル**: `src/team_runtime/worktree_runtime.py`（新規）, `poc/codex_runtime_adapter.py`, `docs/rfc-worktree-runtime-tools.md`, `tests/e2e/worktree_runtime_mvp.py`（新規）
- **推定ワークロード**: 2 セッション
- **ステータス**: `not_started`

---

## 1. 目的

model-callable な `enter_worktree` / `exit_worktree` / `cleanup_worktree` を最小実装し、並行作業の安全な足場を作る。

## 2. 背景・前提

- RFC はあるが実体がない
- 現在は手動で branch/path 管理しており誤操作リスクがある
- trigger と同様に、判断ではなく実行機構のみ提供する

## 3. 具体的な作業ステップ

### Step 1: 安全境界の定義
- **対象**: `src/team_runtime/worktree_runtime.py`
- **やること**:
  - repo root 配下のみ許可
  - destructive cleanup は explicit flag 必須
  - team status deleting/deleted では新規 enter 拒否
- **検証**: unsafe path が拒否される

### Step 2: 最小操作の実装
- **対象**: `src/team_runtime/worktree_runtime.py`, `poc/codex_runtime_adapter.py`
- **やること**:
  - `enter_worktree`, `exit_worktree`, `cleanup_worktree`, `worktree_list`
  - idempotency（同一 branch/path 呼び出し）
- **検証**: 同一操作の再実行で重複が増えない

### Step 3: 状態保存と reconcile
- **対象**: `src/team_runtime/worktree_runtime.py`
- **やること**:
  - worktree state を JSON で永続化
  - startup 時に壊れた参照を cleanup 対象へ移す
- **検証**: 再起動後に state が復元される

### Step 4: E2E と運用メモ
- **対象**: `tests/e2e/worktree_runtime_mvp.py`, `docs/agent-setup-runbook.md`
- **やること**:
  - enter→list→exit→cleanup シナリオ
  - 危険ケース（未保存変更・削除失敗）を明記
- **検証**: runbook だけで再現可能

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| path validation | repo 外アクセス | 入力パスを正規化して比較 |
| cleanup | 削除漏れ | state と実 filesystem を diff |
| adapter | fail-open 透過 | envelope `ok/fail_open` を確認 |

## 5. 完了判定（Exit Criteria）

- [ ] 4 操作が adapter から呼べる
- [ ] unsafe path が拒否される
- [ ] startup reconcile で壊れた state を回復できる
- [ ] E2E シナリオが PASS

## 6. リスク・注意

- Git 操作失敗時の rollback を簡潔にする（複雑化しない）
- worktree と task ownership を混ぜない（連携は後段）
- full automation 前提にしない

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
