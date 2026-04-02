# Team Runtime State Model

- Status: Draft
- Version: 0.1
- Date: 2026-04-02
- Owner: Codex CLI Maximizer

## 1. 目的
Control Plane / Message Bus / Task Bus を接続する共通 runtime state を定義し、  
resume・reconcile・監査で同じ語彙を使えるようにする。

## 2. 接続するRFC
- Control Plane: `docs/rfc-agent-team-control-plane.md`
- Message Bus: `docs/rfc-team-message-bus.md`
- Task Bus: `docs/rfc-team-task-bus.md`

## 3. 共通状態オブジェクト

```json
{
  "runtime_version": 1,
  "team": {},
  "members": [],
  "tasks": [],
  "messages": [],
  "lifecycle": {},
  "reconcile_cursor": {}
}
```

## 4. エンティティ定義

## 4.1 Team
- `team_id`
- `status: active|deleting|deleted|interrupted`
- `leader_member_id`
- `created_at|updated_at|deleted_at?`
- `schema_version`

## 4.2 Member
- `member_id`
- `role: leader|member`
- `lifecycle: pending_init|running|idle|interrupted|shutdown|not_found`
- `last_heartbeat_at`
- `runtime_context`（model/cwd/worktree/path）

## 4.3 Task
- `task_id`
- `owner_member_id?`
- `state: todo|ready|in_progress|blocked|done|cancelled|failed`
- `blocked_reason?`
- `result_reference?`
- `version`

## 4.4 Message
- `message_id`
- `type: direct|broadcast|control`
- `subtype`
- `from_member_id`
- `to_member_ids[]`
- `delivery_status_by_member`
- `correlation_id?`

## 4.5 Lifecycle
- team lifecycle:
  - 通常系: `active -> deleting -> deleted`
  - 中断系: `active -> interrupted -> active`
  - 優先順位: `deleting/deleted` が `interrupted` より常に優先
- member lifecycle: `running -> idle|interrupted|shutdown`
- task lifecycle: Task Bus state machine に準拠
- message lifecycle: `queued -> delivered|failed|expired`

## 4.6 Team status 遷移条件
- `active -> interrupted`
  - leader が `not_found|interrupted` になり、自動再接続できない。
  - startup reconcile で runtime 状態と永続状態の不整合が解消できない。
- `interrupted -> active`
  - leader が再実在化し、必須 invariants（leader一意、owner整合、未完了cleanupなし）を満たす。
  - reconcile が `can_resume=true` を判定した場合のみ復帰。
- `active|interrupted -> deleting`
  - 明示的 delete 要求を受けた場合。`interrupted` より `deleting` を優先して遷移。
- `deleting -> deleted`
  - cleanup 完了時にのみ遷移（終端）。

## 5. Invariants
- leader は team ごとに1人のみ。
- `team.status=deleted` のとき `members.lifecycle=running|idle` は存在しない。
- `task.owner_member_id` は active member か `null`。
- `task.state=blocked` のとき `blocked_reason` は非空。
- `message.type=control` は audit log へ必ず記録。

## 6. Reconcile Rules

## 6.1 Startup Reconcile
1. team をロードし `status` を確認
2. member 実在を runtime API で再照合
3. `deleting` の team は他状態より優先して cleanup を再開
4. `interrupted` の team は復帰条件を判定し、満たせば `active` に戻す
5. 復帰条件を満たせない場合は `interrupted` を維持し、operator へ要対応通知
6. orphan owner の task は `ready` へ戻す
7. `queued` message の再送可否を判定

## 6.2 Periodic Reconcile
- heartbeat timeout で member を `interrupted` に遷移。
- leader 不在が閾値を超えた場合は team を `interrupted` に遷移。
- `deleting` の team は `interrupted` 判定を行わず cleanup を継続。
- `delivery_exhausted` message は escalation を自動生成。
- 長時間 `blocked` の task は leader に再判断を要求。

## 6.3 Conflict Reconcile
- state 更新競合は `version` 優先（最新のみ採用）。
- team status と task update が衝突した場合、team status を優先し更新を拒否。
- status 競合は優先順位 `deleted > deleting > interrupted > active` で解決。

## 7. 境界条件
- fork thread へ team context 自動継承しない（split-brain 防止）。
- 強制 shutdown 中は新規 task 作成を拒否。
- `deleted` team への message/task 書き込みは禁止。

## 8. 破綻しやすい箇所
- member heartbeat と shutdown の競合で lifecycle が揺れる。
- broadcast 再送中に member が離脱するケース。
- reconcile が message/task を過剰修復して意図を壊すケース。
- interrupted team を誤って active に戻すケース。
