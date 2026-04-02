# Team Task Bus PoC (Minimal)

- Version: 0.1
- Date: 2026-04-03
- Scope: Task Bus の最小形（Message Bus とは疎結合）

## 1. 実装ファイル
- `/Users/kondogenki/AI Agent Maximizer/poc/team_task_bus.py`

## 2. 実装範囲
- `task-create`
- `task-get`
- `task-list`
- `task-update`
- owner
- state transitions
- `blocked_reason`
- `result_reference`
- create/update の最小 idempotency
- startup 時の orphan owner 再評価（`startup-reconcile-orphans`）

## 3. persistence 設計（最小）
既定保存先: `./.runtime/task-bus`

- `tasks/task-<task_id>.json`: task 本体
- `idempotency.json`: create/update の key/response 保存
- `task-events.log`: JSONL 監査ログ

## 4. state transition（PoC）
- `todo -> ready|cancelled`
- `ready -> in_progress|blocked|cancelled`
- `in_progress -> blocked|done|failed|cancelled`
- `blocked -> ready|cancelled`
- `failed -> ready|cancelled`
- `done/cancelled` は終端

`state=blocked` へ遷移する場合は `blocked_reason` 必須。

## 5. orphan owner 再評価
- owner が team から消失、または lifecycle が `shutdown/not_found` の場合に orphan と判定。
- 自動再割当はしない（今回の非対応）。
- owner は `null` にし、`state=in_progress` の task は `ready` へ戻す。
- `orphan_owner` に検出理由と元 owner を保存する。

## 6. Control Plane / Message Bus 接続点
- Control Plane: `TeamControlPlane.get_team(...)` で team status と member lifecycle を参照。
- team status が `deleting/deleted` のとき create/update を拒否。
- Message Bus: 直接API依存は持たず、任意で `--message-bus-store-root` を渡した場合のみ外部イベントヒントを発行（fail-open）。

## 7. 非対応（今回やらないこと）
- 自動再割当
- approval workflow
- verifier 連携の自動化
- UI
- trigger 連携

## 8. 動作確認手順
以下はプロジェクトルートで実行:

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_control_plane.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-tasktest \
  team-create --team-name task-alpha --idempotency-key cp-task-alpha-1
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_task_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/task-bus-tasktest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-tasktest \
  --message-bus-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/message-bus-tasktest \
  task-create --team-id <TEAM_ID> --title "draft spec" --owner-member-id <LEADER_ID> \
  --state ready --idempotency-key task-create-1
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_task_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/task-bus-tasktest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-tasktest \
  task-create --team-id <TEAM_ID> --title "draft spec" --owner-member-id <LEADER_ID> \
  --state ready --idempotency-key task-create-1
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_task_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/task-bus-tasktest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-tasktest \
  task-update --task-id <TASK_ID> --state in_progress --idempotency-key task-update-1
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_task_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/task-bus-tasktest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-tasktest \
  task-update --task-id <TASK_ID> --state blocked --blocked-reason "waiting for input"
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_task_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/task-bus-tasktest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-tasktest \
  task-update --task-id <TASK_ID> --state ready --idempotency-key task-update-2
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_task_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/task-bus-tasktest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-tasktest \
  task-update --task-id <TASK_ID> --state in_progress --idempotency-key task-update-3
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_control_plane.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-tasktest \
  team-delete --team-id <TEAM_ID>
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_task_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/task-bus-tasktest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-tasktest \
  startup-reconcile-orphans
```

期待値:
- create/update の同一 idempotency key は同一レスポンスを返す。
- invalid state transition は拒否される。
- team 削除後の orphan owner は `owner_member_id=null` になり、`in_progress` なら `ready` へ戻る。
