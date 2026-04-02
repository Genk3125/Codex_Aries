# Runtime Walkthrough Spike (Control Plane + Message Bus + Task Bus)

- Version: 0.1
- Date: 2026-04-03
- Scope: 3 PoC を一連で動かす統合スパイク（本番機能ではない）

## 1. 実装ファイル
- `/Users/kondogenki/AI Agent Maximizer/poc/runtime_walkthrough.py`

## 2. シナリオ（固定）
1. `team_create`（Control Plane）
2. `task_create`（Task Bus, owner=leader）
3. `direct message` 1回（Message Bus, `defer_delivery=true`）
4. `task state update`（`ready -> in_progress`）
5. `team_delete`（`deleting` で中断シミュレーション）
6. `startup reconcile` を順に実行
   - Control Plane: `deleting -> deleted`
   - Message Bus: pending delivery 再評価
   - Task Bus: orphan owner 再評価

## 3. 連携ポイント（見える化）
- Task Bus -> Control Plane
  - team status gate（`deleting/deleted` 拒否）
  - owner/member lifecycle 参照
- Message Bus -> Control Plane
  - send 時の team status gate
  - delivery 再評価時の recipient lifecycle 判定
- Task Bus -> Message Bus（疎結合）
  - 任意の external hint event 発行（fail-open）

## 4. 実行手順

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/runtime_walkthrough.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/walkthrough \
  --output-json /Users/kondogenki/AI\ Agent\ Maximizer/logs/walkthrough-output.json
```

再実行時に既存データを残す場合:

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/runtime_walkthrough.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/walkthrough \
  --no-reset
```

## 5. 期待される出力例（抜粋）
```json
{
  "flow_ids": {
    "team_id": "team_xxx",
    "task_id": "task_xxx",
    "message_id": "msg_xxx"
  },
  "steps": [
    {"step": "team_create", "...": "..."},
    {"step": "task_create", "...": "..."},
    {"step": "direct_message_send", "result": {"status": "pending"}},
    {"step": "task_state_update", "result": {"state": "in_progress"}},
    {"step": "team_delete_marked_deleting", "result": {"status": "deleting"}},
    {"step": "startup_reconcile", "...": "..."}
  ],
  "snapshots": {
    "teams": {"teams": [{"status": "deleted"}]},
    "messages": {"messages": [{"status": "rejected"}]},
    "tasks": {"tasks": [{"owner_member_id": null, "state": "ready"}]}
  }
}
```

## 6. 保存状態の追跡
walkthrough 実行後は以下を確認できる:
- `.../.runtime/walkthrough/control-plane/*`
- `.../.runtime/walkthrough/message-bus/*`
- `.../.runtime/walkthrough/task-bus/*`
- `logs/walkthrough-output.json`（全体サマリ）

## 7. 非対応（今回やらないこと）
- broadcast
- approval workflow
- worktree
- trigger
- verifier 自動起動
- UI
- 並列実行の本格対応
