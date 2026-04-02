# Codex Runtime Adapter (PoC Bridge)

- Version: 0.1
- Date: 2026-04-03
- Goal: Control Plane / Message Bus / Task Bus PoC を `~/.codex` 運用から呼べる薄い adapter 層

## 1. 実装ファイル
- `/Users/kondogenki/AI Agent Maximizer/poc/codex_runtime_adapter.py`

## 2. 設計方針（短いメモ）
- 既存 PoC を直接書き換えず、adapter は operation ルーティングのみ担当。
- `store_root` は CLI 引数か `CODEX_RUNTIME_STORE_ROOT` で設定可能（固定パスにしない）。
- fail-open を既定にし、エラー時も JSON envelope を返して終了コードは 0（`--strict` で fail-close）。
- Message Bus 連携は Task Bus からの外部イベントヒントまで（疎結合）。

## 3. Codex から起動する入口
共通入口: `op --name <operation>`

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/codex_runtime_adapter.py op \
  --name runtime_info
```

主要 operation:
- `team_create`
- `team_delete`
- `team_list`
- `send_message`
- `message_list`
- `task_create`
- `task_get`
- `task_list`
- `task_update`
- `runtime_reconcile_all`

## 4. `~/.codex` から呼ぶ最小設定例

### 4.1 `~/.codex/runtime-adapter.env`（例）
```bash
export CODEX_RUNTIME_ADAPTER_PATH="/Users/kondogenki/AI Agent Maximizer/poc/codex_runtime_adapter.py"
export CODEX_RUNTIME_STORE_ROOT="$HOME/.codex/runtime-spike"
```

### 4.2 `~/.zshrc` へ最小 alias（例）
```bash
source "$HOME/.codex/runtime-adapter.env"
alias codex-runtime='python3 "$CODEX_RUNTIME_ADAPTER_PATH" --store-root "$CODEX_RUNTIME_STORE_ROOT"'
```

### 4.3 実行例
```bash
codex-runtime op --name team_create --args-json '{"team_name":"alpha","idempotency_key":"alpha-1"}'
```

```bash
codex-runtime op --name send_message --args-json '{"team_id":"team_xxx","from_member_id":"leader_xxx","to_member_id":"leader_xxx","message_type":"direct","payload":{"text":"hello"}}'
```

```bash
codex-runtime op --name task_create --args-json '{"team_id":"team_xxx","title":"first task","owner_member_id":"leader_xxx","state":"ready"}'
```

## 5. 実行手順（統合最小）
1. team 作成
2. direct message 送信
3. task 作成
4. task 更新（`in_progress`）
5. team delete（`deleting` シミュレーション）
6. `runtime_reconcile_all`

## 6. 出力形式（共通 envelope）
```json
{
  "operation": "team_create",
  "ok": true,
  "fail_open": true,
  "result": {...},
  "error": null
}
```

エラー時（fail-open既定）:
```json
{
  "operation": "send_message",
  "ok": false,
  "fail_open": true,
  "result": null,
  "error": {"code":"TEAM_NOT_SENDABLE","message":"..."}
}
```

## 7. 今回やらないこと
- Codex 本体 fork
- UI
- 自動 verifier 起動
- worktree
- trigger
- 完全自動 orchestration
