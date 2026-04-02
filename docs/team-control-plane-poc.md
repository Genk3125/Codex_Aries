# Team Control Plane PoC (Minimal)

- Version: 0.1
- Date: 2026-04-02
- Scope: Control Plane のみ（Message Bus / Task Bus 非接続）

## 1. 実装ファイル
- `/Users/kondogenki/AI Agent Maximizer/poc/team_control_plane.py`

## 2. 実装範囲
- `team_create`
- `team_delete`
- persistence（JSON + event log）
- idempotency（`team_create` の最小対応）
- `deleting -> deleted` の状態遷移
- startup 時の `deleting` 検知と cleanup 継続（`startup-reconcile`）

## 3. persistence 設計（最小）
既定保存先: `./.runtime/control-plane`

- `teams/team-<team_id>.json`: team 本体
- `active-team-index.json`: `team_name -> team_id` の index
- `idempotency.json`: `team_create` の key/response 保存
- `team-events.log`: JSONL 監査ログ

書き込みは `tmp -> fsync -> rename` の atomic write で実装。

## 4. idempotency の最小仕様
- `team-create --idempotency-key <key>` を同じ key で再実行した場合、同じレスポンスを返す。
- 競合回避は単一プロセス前提（PoC段階）。分散ロックは未実装。

## 5. deleting cleanup / startup reconcile
- `team-delete` はまず `status=deleting` を永続化。
- その後 cleanup で `status=deleted` に確定。
- `--simulate-crash-after-marking-deleting` を使うと `deleting` で停止し、`startup-reconcile` で cleanup を再開できる。

## 6. 非対応（今回やらないこと）
- broadcast
- task CRUD
- approval
- worktree
- trigger
- memory

## 7. stub / TODO
`team_create` / `team_delete` の中で以下の stub を呼び出すのみ:
- `_message_bus_stub(...)`
- `_task_bus_stub(...)`

いずれも `team-events.log` に TODO イベントを書くだけで、実接続はしていない。

## 8. 動作確認手順
以下はプロジェクトルートで実行:

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_control_plane.py team-create \
  --team-name alpha \
  --idempotency-key create-alpha-1
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_control_plane.py team-create \
  --team-name alpha \
  --idempotency-key create-alpha-1
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_control_plane.py list-teams
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_control_plane.py team-delete \
  --team-id <TEAM_ID> \
  --simulate-crash-after-marking-deleting
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_control_plane.py startup-reconcile
```

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/team_control_plane.py team-delete \
  --team-id <TEAM_ID>
```

期待値:
- 同一 idempotency key の create は同一 `team_id` を返す。
- `startup-reconcile` 後、該当 team は `deleted` になる。
- `team-events.log` に create/delete/stub/reconcile の監査イベントが追記される。
