# Subplan: Worktree Runtime Tools MVP

## メタ情報

- **Phase ID**: `m3-3_worktree-runtime-tools-mvp`
- **Master Flow 位置**: Milestone 3 / Phase 21
- **依存先**: `m3-2_trigger-layer-mvp`（独立実装可）
- **主対象ファイル**: `src/team_runtime/worktree_runtime.py`（新規）, `poc/codex_runtime_adapter.py`, `docs/rfc-worktree-runtime-tools.md`, `tests/e2e/worktree_runtime_mvp.py`（新規）
- **共通契約参照**: `docs/runtime-shared-contract.md`, `docs/schemas/runtime-shared-contract.v1.json`
- **推定ワークロード**: 2 セッション
- **ステータス**: `not_started`

---

## 1. 目的

model-callable な worktree 操作を最小実装し、並行作業の安全な足場を作る。

## 2. 背景・前提

- RFC はあるが実体がない
- 現在は手動で branch/path 管理しており誤操作リスクがある
- trigger と同様に、判断ではなく実行機構のみ提供する
- shared contract freeze（Phase 20-22 共通）に沿って operation 名と store/schema を固定する

### 2.1 Shared Contract Freeze（実装前提）

- store layout は `worktree-runtime/` 配下に固定（`docs/runtime-shared-contract.md`）
- schema version は `schema_version=1` に固定
- idempotency key 形式は共通 regex に固定
- strict/fail-open は adapter 共通 envelope 規約に従う
- adapter operation 名は `worktree_enter|worktree_exit|worktree_cleanup|worktree_list` で固定

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
  - `worktree_enter`, `worktree_exit`, `worktree_cleanup`, `worktree_list`
  - idempotency（同一 branch/path 呼び出し）
  - enter/exit 本体は最小機能を維持し、追加自動化は入れない
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
  - shared contract 参照を runbook に追記
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
- [ ] shared contract freeze（store/schema/idempotency/strict/op 名）への逸脱がない

## 6. リスク・注意

- Git 操作失敗時の rollback を簡潔にする（複雑化しない）
- worktree と task ownership を混ぜない（連携は後段）
- full automation 前提にしない
- enter/exit の本格機能拡張（自動 stash など）はこの phase では入れない

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
