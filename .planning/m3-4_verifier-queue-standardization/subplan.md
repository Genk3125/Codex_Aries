# Subplan: Verifier Queue / Async Request Standardization

## メタ情報

- **Phase ID**: `m3-4_verifier-queue-standardization`
- **Master Flow 位置**: Milestone 3 / Phase 22
- **依存先**: `m3-2_trigger-layer-mvp`, `m3-3_worktree-runtime-tools-mvp`（片方先行可）
- **主対象ファイル**: `poc/verifier_queue.py`（新規）, `poc/verifier_gate_helper.py`, `verifier-contract.md`, `docs/agent-setup-runbook.md`, `tests/e2e/verifier_queue_mvp.py`（新規）
- **共通契約参照**: `docs/runtime-shared-contract.md`, `docs/schemas/runtime-shared-contract.v1.json`
- **推定ワークロード**: 2 セッション
- **ステータス**: `not_started`

---

## 1. 目的

verifier の起動要求を同期実行から「非同期キュー要求」に標準化し、長時間タスクの詰まりを減らす。

## 2. 背景・前提

- 現状は gate から直接 verifier 実行するケースがある
- 失敗時の材料整理はできるが、実行待ち管理が弱い
- verifier の判定ロジック自体は変更しない
- shared contract freeze（Phase 20-22 共通）を先に固定してから実装に入る

### 2.1 Shared Contract Freeze（実装前提）

- store layout は `verifier-queue/` 配下に固定（`docs/runtime-shared-contract.md`）
- schema version は `schema_version=1` に固定
- idempotency key 形式は共通 regex に固定
- strict/fail-open は adapter 共通 envelope 規約に従う
- operation 名は `verifier_request_create|get|list|claim_once` で固定
- retry/priority はこの phase では入れない

## 3. 具体的な作業ステップ

### Step 1: Queue schema を固定
- **対象**: `poc/verifier_queue.py`
- **やること**:
  - `request_id`, `status(requested/running/succeeded/failed/cancelled)`, `payload_ref`, `created_at`, `schema_version` を定義
  - store layout を `store_root/verifier-queue/` に固定
  - idempotency key を `request_create` に追加
- **検証**: queue item JSON が schema に一致

### Step 2: enqueue/dequeue API を実装
- **対象**: `poc/verifier_queue.py`, `poc/codex_runtime_adapter.py`
- **やること**:
  - `verifier_request_create`, `verifier_request_get`, `verifier_request_list`, `verifier_request_claim_once`
  - claim は single-pass（自動再試行なし）
- **検証**: 同時 claim で二重実行が起きない

### Step 3: gate 連携を追加
- **対象**: `poc/verifier_gate_helper.py`, `poc/chain_helper.py`
- **やること**:
  - direct verifier 実行を残したまま、`--verifier-queue` オプションで enqueue を選択可能にする
  - fail-open/strict の透過維持
- **検証**: queue モード時に gate 判定は不変

### Step 4: E2E と運用規約
- **対象**: `tests/e2e/verifier_queue_mvp.py`, `verifier-contract.md`, `docs/agent-setup-runbook.md`
- **やること**:
  - request→claim→result 記録を検証
  - exit code 規約（0/1/2/3+）との対応を追記
  - shared contract 参照を runbook に追記
- **検証**: E2E PASS + contract に矛盾なし

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| request_create | 重複要求 | idempotency map を確認 |
| claim_once | 競合 | status 遷移ログを確認 |
| gate 連携 | 判定の変化有無 | queue on/off で trigger codes を比較 |

## 5. 完了判定（Exit Criteria）

- [ ] verifier queue の create/get/list/claim が動く
- [ ] queue モードでも gate 判定は不変
- [ ] strict/fail-open を壊さない
- [ ] E2E が PASS
- [ ] shared contract freeze（store/schema/idempotency/strict/op 名）への逸脱がない

## 6. リスク・注意

- queue と verifier 本体判定を混ぜない
- 自動再試行を先に入れない
- trigger 連携は phase 20 の成果に依存しすぎない
- priority queue 化はこの phase では入れない

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
