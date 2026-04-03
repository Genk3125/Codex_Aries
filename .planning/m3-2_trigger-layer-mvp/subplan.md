# Subplan: Trigger Layer MVP（cron / remote / sleep）

## メタ情報

- **Phase ID**: `m3-2_trigger-layer-mvp`
- **Master Flow 位置**: Milestone 3 / Phase 20
- **依存先**: `m3-1_real-world-30day-dogfood`（並走可だが finalization 後に統合）
- **主対象ファイル**: `src/team_runtime/trigger_layer.py`（新規）, `poc/codex_runtime_adapter.py`, `docs/rfc-trigger-layer.md`, `tests/e2e/trigger_layer_mvp.py`（新規）
- **推定ワークロード**: 2-3 セッション
- **ステータス**: `not_started`

---

## 1. 目的

cron / remote trigger / sleep を 1 つの薄い runtime 層で扱い、既存 adapter から一貫操作できるようにする。

## 2. 背景・前提

- RFC (`docs/rfc-trigger-layer.md`) は存在
- 現在は手動実行中心で、非同期起動の入口が不足
- 新しい判断主体は導入しない（実行判定のみ）

## 3. 具体的な作業ステップ

### Step 1: Trigger state schema を固定
- **対象**: `src/team_runtime/trigger_layer.py`
- **やること**:
  - `trigger_id`, `kind`, `schedule`, `status`, `last_run_at`, `next_run_at` を固定
  - idempotency key を create/update に追加
- **検証**: schema バージョン付き JSON が保存される

### Step 2: 最小 API を実装
- **対象**: `src/team_runtime/trigger_layer.py`, `poc/codex_runtime_adapter.py`
- **やること**:
  - `trigger_create`, `trigger_list`, `trigger_delete`, `trigger_fire_due`
  - strict/fail-open を adapter で透過
- **検証**: CLI から 4 操作が呼べる

### Step 3: startup reconcile を追加
- **対象**: `src/team_runtime/trigger_layer.py`
- **やること**:
  - pending trigger の再評価
  - deleting/deleted team は fire 対象外にする
- **検証**: 再起動後に orphan trigger が増えない

### Step 4: E2E と runbook
- **対象**: `tests/e2e/trigger_layer_mvp.py`, `docs/agent-setup-runbook.md`
- **やること**:
  - one-shot / recurring / sleep の 3 ケース検証
  - 失敗時の手動回復手順を追記
- **検証**: E2E が PASS、runbook から再現可能

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| `trigger_fire_due` | 重複発火 | idempotency key と run log 比較 |
| `startup_reconcile` | 取りこぼし | 起動前後の trigger count 比較 |
| adapter `op` 分岐 | strict での停止条件 | exit code と envelope を確認 |

## 5. 完了判定（Exit Criteria）

- [ ] Trigger schema + store が安定
- [ ] 4 操作（create/list/delete/fire_due）が adapter から実行可能
- [ ] reconcile 後の pending 増加がない
- [ ] E2E 3 ケース PASS

## 6. リスク・注意

- cron 精度を最初から追いすぎない（MVP は分単位で十分）
- remote trigger を認可ロジックと混ぜない（認可は後段）
- full auto loop を入れない

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
