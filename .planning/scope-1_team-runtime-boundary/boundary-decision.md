# Team Runtime Boundary Decision (Phase 10)

_Date: 2026-04-03_

## 1. Interface Inventory (PoC)

### `poc/team_control_plane.py`
- `team_create`
- `team_member_add`
- `team_member_remove`
- `team_delete`
- `startup_reconcile`
- `list_teams`

### `poc/team_message_bus.py`
- `send_message` (`direct` / minimal `control`)
- `startup_reconcile`
- `list_messages`
- `record_external_event` (task bus 連携ヒント)

### `poc/team_task_bus.py`
- `task_create`
- `task_get`
- `task_list`
- `task_update`
- `startup_reconcile_orphan_owners`

### `poc/codex_runtime_adapter.py` operation 対応
- Team: `team_create`, `team_member_add`, `team_member_remove`, `team_delete`, `team_list`, `team_startup_reconcile`
- Message: `send_message`, `message_list`, `message_startup_reconcile`
- Task: `task_create`, `task_get`, `task_list`, `task_update`, `task_startup_reconcile_orphans`
- Runtime: `runtime_reconcile_all`, `runtime_info`

## 2. Runtime Adapter との重複 / ギャップ

### 重複（そのまま昇格可能）
- Control Plane / Message Bus / Task Bus の API は adapter operation と 1:1 で整合。
- `runtime_reconcile_all` の起点となる startup reconcile 群が揃っている。

### ギャップ（MVP で補う）
- 実装配置が `poc/` に留まっている（本実装の import 安定性が弱い）。
- 3+ member の運用シナリオを回す回帰テストが不足。
- エラーコード契約はあるが、`src/` 側の型・docstring が不足。

### 受け入れる制約（MVP段階）
- Message Bus は direct + control 最小のみ（broadcast/approval は未実装）。
- Task Bus は orphan 検知のみ（自動再割当は未実装）。
- UI/trigger/worktree 連携は未実装。

## 3. In-Scope (Phase 13 実装対象)

- `team_create` / `team_member_add` / `team_member_remove` / `team_delete`
- `team_startup_reconcile`
- `send_message` (direct, control minimal)
- `message_startup_reconcile` / `message_list`
- `task_create` / `task_get` / `task_list` / `task_update`
- `task_startup_reconcile_orphans`
- `runtime_reconcile_all`

理由:
- 既存 one_shot orchestrator と日常運用（session/task/message/reconcile）に直結。
- 失敗復旧の最小カーネル（deleting cleanup / pending delivery / orphan owner）を維持できる。

## 4. Out-of-Scope (Milestone 2 ではやらない)

- broadcast messaging
- approval workflow 全量
- trigger layer（cron/remote/sleep）
- worktree enter/exit
- verifier 自動起動・自動修正

理由:
- 現在の daily-driver カーネルに必須でない。
- 境界を広げると Phase 13 の MVP を壊す。

## 5. Deferred (Milestone 3 候補)

- leader handoff / re-election
- task 自動再割当
- approval timeout policy
- worktree/runtime trigger の本実装

理由:
- MVP の責務外だが、運用成熟フェーズでは価値が高い。

## 6. Phase 13 への入力（確定スコープ）

1. `poc/` 実装を `src/team_runtime/` へ昇格（互換 API 維持）
2. `codex_runtime_adapter` の import を `src/team_runtime` 優先へ変更
3. 3-member 実行シナリオ + resume/reconcile 回帰を最低 1 本追加

