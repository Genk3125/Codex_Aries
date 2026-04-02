# RFC: Agent Team Control Plane

- Status: Draft
- Version: 0.1
- Date: 2026-04-02
- Owner: Codex CLI Maximizer

## 1. 目的
`subagent` 単位の実行を、`team` 単位の継続運用に拡張するための Control Plane を定義する。  
本RFCは **チームの生成/削除/永続化/再開** に責務を限定する。

## 2. スコープ

### In Scope
- `team_create`
- `team_delete`
- leader/member model
- persistence（永続化）
- cleanup（正常終了/異常終了）
- resume semantics（セッション再開時の意味論）

### Out of Scope（別RFCへ委譲）
- Team内メッセージ仕様（Message Bus RFC）
- Team内タスク仕様（Task Bus RFC）
- scheduler/trigger（cron/sleep/remote trigger）

## 3. 設計原則
- **単一責務**: Control Plane は team lifecycle/state のみ扱う。
- **冪等性**: create/delete は再実行に強い設計にする。
- **クラッシュ耐性**: 中断後の resume で矛盾を最小化する。
- **可観測性**: 主要状態遷移をイベント化する。

## 4. API 仕様

## 4.1 `team_create`

### 入力
- `team_name: string`（必須）
- `description?: string`
- `leader_agent_id?: string`（未指定時は root/coordinator から生成）
- `idempotency_key?: string`（同一要求の重複作成防止）

### 出力
- `team_id: string`
- `team_name: string`
- `leader_agent_id: string`
- `status: "active"`
- `created_at: string(ISO-8601)`

### 失敗
- `TEAM_ALREADY_EXISTS`（同名teamがactive）
- `TEAM_CREATE_CONFLICT`（同時作成競合）
- `PERSISTENCE_WRITE_FAILED`

### 仕様ノート
- 同一 thread/context で active team は1つまで。
- `idempotency_key` 一致時は既存成功レスポンスを返す（再作成しない）。

## 4.2 `team_delete`

### 入力
- `team_id: string`（必須）
- `mode: "graceful" | "force"`（既定: `graceful`）
- `reason?: string`

### 出力
- `team_id: string`
- `status: "deleted"`
- `deleted_at: string(ISO-8601)`
- `cleanup_summary`
  - `members_closed: number`
  - `orphans_detected: number`
  - `errors: string[]`

### 失敗
- `TEAM_NOT_FOUND`
- `TEAM_DELETE_IN_PROGRESS`
- `CLEANUP_PARTIAL_FAILURE`

### 仕様ノート
- `graceful` は member停止→state flush→削除の順。
- `force` は未停止memberを orphan として記録し先に削除を完了。

## 5. Leader / Member モデル

## 5.1 Team
- `team_id`
- `team_name`
- `status: active | deleting | deleted`
- `leader_agent_id`
- `members: Member[]`
- `created_at / updated_at / deleted_at?`
- `version`（楽観ロック用）

## 5.2 Member
- `agent_id`
- `role: leader | member`
- `lifecycle: pending_init | running | idle | interrupted | shutdown | not_found`
- `joined_at`
- `last_heartbeat_at?`
- `metadata?`（model/cwd/worktree/thread_path など）

## 5.3 不変条件（Invariants）
- leader は常に1人。
- member は同一team内で `agent_id` 一意。
- `team.status=deleted` のとき active member は0。

## 6. Persistence

## 6.1 保存単位
- `team-{team_id}.json`（team本体）
- `active-team-index.json`（thread/context → team_id）
- `team-events.log`（監査イベント）

## 6.2 保存方式
- atomic write（`tmp -> fsync -> rename`）
- `version` による compare-and-swap 更新
- 破損検知時は fail-closed（復旧モードに遷移）

## 6.3 互換性
- `schema_version` を持ち、将来の Message/Task Bus 連携で後方互換維持。

## 7. Cleanup

## 7.1 正常系（graceful）
1. `status=deleting` に遷移
2. member 停止要求（timeout付き）
3. active index を解除
4. team 状態を `deleted` で確定
5. audit event を記録

## 7.2 異常系
- 停止不能memberは orphan として記録し、再起動時に回収対象にする。
- `deleting` でクラッシュした場合、resume時に cleanup-reconcile を再実行。

## 8. Resume Semantics

## 8.1 同一threadの再開
- `active-team-index` から team を復元する。
- 復元後、`list_agents` 相当で実在memberを再照合し `lifecycle` を補正する。

## 8.2 fork/resume
- 既定では team context を fork に自動継承しない（split-brain防止）。
- 明示フラグ `inherit_team=true` がある場合のみ継承可能（将来拡張）。

## 8.3 中断復旧
- `team.status=deleting` のteamを検知したら cleanup を継続。
- `leader not_found` のactive teamは `interrupted` 扱いで運用者に通知。

## 9. Message Bus / Task Bus に委ねること
- Message payload schema、routing、broadcast、approval/shutdown control message の詳細。
- Task CRUD、task state machine、owner/blocking/result linkage。
- Control Plane は team/member の参照と lifecycle event 発火のみ提供する。

## 10. 破綻しやすい箇所（先に潰すべき）
- **同時 `team_create` 競合**: 同名/同threadの二重作成。
- **delete途中クラッシュ**: `deleting` のまま取り残される。
- **orphan member**: team削除後もagentが稼働し続ける。
- **resume時の不整合**: 永続状態と実ランタイム状態がズレる。
- **fork時のsplit-brain**: team context を複数threadで共有してしまう。

## 11. ロールアウト
1. Phase 1: single-team per thread（feature flag）
2. Phase 2: cleanup-reconcile と orphan回収
3. Phase 3: Message Bus / Task Bus 統合

## 12. Open Questions
- team state の保存先（thread単位 or workspace単位）の最終決定。
- orphan回収の自動化タイミング（startupのみ or 定期）。
- `inherit_team` をいつ解放するか（fork運用の実績待ち）。
