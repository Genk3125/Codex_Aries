# Team Message Bus PoC (Minimal)

- Version: 0.1
- Date: 2026-04-02
- Scope: Message Bus の最小形（Task Bus 非接続）

## 1. 実装ファイル
- `/Users/kondogenki/AI Agent Maximizer/poc/team_message_bus.py`

## 2. 実装範囲
- direct message（1対1）
- control message の最小形（`type=control` + `subtype`）
- `message_id`
- idempotency（`send_message` の最小対応）
- per-recipient delivery state
- team status が `deleting/deleted` のとき送信拒否
- startup 時に pending delivery を再評価（`startup-reconcile`）

## 3. persistence 設計（最小）
既定保存先: `./.runtime/message-bus`

- `messages/message-<message_id>.json`: message 本体
- `idempotency.json`: `send_message` の key/response 保存
- `message-events.log`: JSONL 監査ログ

## 4. delivery state（recipient単位）
各 recipient に以下を保持:
- `state`: `pending|delivered|failed|rejected`
- `attempt_count`
- `last_attempt_at`
- `delivered_at`
- `error`

## 5. startup reconcile
- `startup-reconcile` は `pending` recipient を再評価する。
- team が `deleting/deleted` なら `rejected` へ遷移。
- recipient lifecycle が `running/idle` なら `delivered`。
- recipient lifecycle が `pending_init/interrupted` は `pending` 維持。

## 6. team_control_plane.py との接続点
- `TeamControlPlane.get_team(...)` を呼び team status/member lifecycle を参照する。
- `send-direct` / `send-control` 実行時に team status gate を適用。
- `startup-reconcile` 実行時に control plane の最新状態で再判定する。

## 7. 非対応（今回やらないこと）
- broadcast
- approval workflow 全量
- task 連携
- remote trigger
- UI

## 8. stub / TODO
- Task Bus 接続は未実装（Message Bus 側に接続ポイントのみ）。
- 実 transport（実際の agent への配送）は未実装で、PoC では状態遷移のみ行う。

## 9. 動作確認手順
前提: Control Plane に team があること。

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_control_plane.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-msgtest \
  team-create --team-name bus-alpha --idempotency-key cp-alpha-1
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_message_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/message-bus-msgtest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-msgtest \
  send-direct --team-id <TEAM_ID> --from-member-id <LEADER_ID> --to-member-id <LEADER_ID> \
  --payload-json '{"text":"hello"}' --idempotency-key msg-1
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_message_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/message-bus-msgtest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-msgtest \
  send-direct --team-id <TEAM_ID> --from-member-id <LEADER_ID> --to-member-id <LEADER_ID> \
  --payload-json '{"text":"hello"}' --idempotency-key msg-1
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_control_plane.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-msgtest \
  team-delete --team-id <TEAM_ID> --simulate-crash-after-marking-deleting
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_message_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/message-bus-msgtest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-msgtest \
  send-control --team-id <TEAM_ID> --from-member-id <LEADER_ID> --to-member-id <LEADER_ID> \
  --subtype shutdown --payload-json '{"reason":"test"}'
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_message_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/message-bus-msgtest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-msgtest \
  send-direct --team-id <ANOTHER_TEAM_ID> --from-member-id <LEADER2> --to-member-id <LEADER2> \
  --payload-json '{"text":"deferred"}' --defer-delivery
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_message_bus.py \
  --store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/message-bus-msgtest \
  --control-plane-store-root /Users/kondogenki/AI\ Agent\ Maximizer/.runtime/control-plane-msgtest \
  startup-reconcile
```

期待値:
- 同一 idempotency key で同一 `message_id` が返る。
- `deleting/deleted` team への送信は `TEAM_NOT_SENDABLE` で拒否される。
- deferred で残した pending が `startup-reconcile` で再評価される。
