# Subplan: Docs / Status Full Sync & Release Readiness

## メタ情報

- **Phase ID**: `m3-6_docs-status-release-sync`
- **Master Flow 位置**: Milestone 3 / Phase 24
- **依存先**: `m3-5_team-runtime-deferred-priority`
- **主対象ファイル**: `.planning/MASTER_FLOW.md`, `ToDo.md`, `docs/milestone-2-closeout.md`, `docs/CODEX_MAX_COMBINED_PLAN.md`, `docs/agent-setup-runbook.md`, `scripts/check-status-sync.sh`（新規）
- **推定ワークロード**: 1-2 セッション
- **ステータス**: `not_started`

---

## 1. 目的

status / runbook / closeout の矛盾をゼロにし、95% 仕上げ段階で「何が完了で何が未完か」を一目で判別できる状態にする。

## 2. 背景・前提

- provisional/final ラベル導入後は文書間の同期ミスが起きやすい
- release readiness は機能実装よりも整合性が重要

## 3. 具体的な作業ステップ

### Step 1: source-of-truth を固定
- **対象**: `.planning/MASTER_FLOW.md`
- **やること**:
  - status の正本を MASTER_FLOW に限定
  - 他文書は参照方針を明記
- **検証**: 各文書に参照元が記載される

### Step 2: status sync チェックを自動化
- **対象**: `scripts/check-status-sync.sh`（新規）
- **やること**:
  - MASTER_FLOW / ToDo / closeout のラベル差分を検出
  - 不一致時は非ゼロ終了
- **検証**: 差分あり/なし両ケースを再現できる

### Step 3: runbook へ反映
- **対象**: `docs/agent-setup-runbook.md`
- **やること**:
  - 95% 時点の運用フロー（provisional handling）を追記
  - strict/fail-open の推奨使い分けを固定
- **検証**: runbook だけで運用手順が読める

### Step 4: release readiness checklist 作成
- **対象**: `docs/release-readiness-m3.md`（新規）
- **やること**:
  - 95% 到達判定項目をチェックリスト化
- **検証**: 1 回のレビューで判定可能

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| status checker | 誤検知/見逃し | テスト用差分ファイルで確認 |
| ToDo/Flow/closeout | ラベル不整合 | 同一語彙（done/provisional/final）で照合 |
| runbook | 手順の抜け | 初見手順でウォークスルー |

## 5. 完了判定（Exit Criteria）

- [ ] status checker が動く
- [ ] 主要 4 文書の status が一致
- [ ] release readiness checklist が作成済み
- [ ] runbook が 95% 運用に追随

## 6. リスク・注意

- 手動同期前提に戻さない
- status 語彙を増やしすぎない
- 機能仕様と運用文書を混ぜない

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
