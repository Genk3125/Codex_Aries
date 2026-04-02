# RFC: Trigger Layer

- Status: Draft
- Version: 0.1
- Date: 2026-04-02
- Owner: Codex CLI Maximizer

## 1. 目的
`one-shot` / `recurring` / `remote trigger` / `sleep/wait` を単一レイヤーで扱い、  
team/task runtime に安全に接続する trigger 実行面を定義する。

## 2. スコープ

### In Scope
- one-shot trigger
- recurring trigger
- remote trigger
- sleep / wait
- unattended risk control
- Team Runtime / Task Runtime 接続

### Out of Scope
- 外部認証基盤の詳細実装
- 高度な cron parser 拡張
- business workflow DSL

## 3. Trigger モデル

```json
{
  "trigger_id": "trg_...",
  "kind": "one_shot|recurring|remote|sleep",
  "target": {
    "team_id": "team_...",
    "task_id": "task_..."
  },
  "schedule": {},
  "policy": {
    "max_concurrency": 1,
    "requires_approval": false,
    "unattended_guard": "strict"
  },
  "state": "scheduled|running|paused|completed|failed|cancelled"
}
```

## 4. 実行種別

## 4.1 One-shot
- 指定時刻または即時で1回だけ実行。
- 実行後 `completed` で終端。

## 4.2 Recurring
- 固定周期で繰り返し実行。
- 同一 target の重複実行は `max_concurrency` で制限。

## 4.3 Remote Trigger
- 外部イベント（webhook 等）で起動。
- 署名検証失敗時は破棄し audit に記録。

## 4.4 Sleep / Wait
- running task を一時停止し、指定条件（時間/イベント）で再開。
- timeout 到達時の fallback action（retry/escalate/fail）を必須指定。

## 5. Unattended Risk Control
- unattended 実行は既定 read-heavy task のみに許可。
- write系 task は policy で `requires_approval=true` を強制可能。
- 失敗連鎖時に circuit breaker（連続失敗閾値）で自動停止。
- すべての unattended 実行に trace id を付与し追跡可能にする。

## 6. Team/Task Runtime との接続
- Trigger 起動時に team status が `active` か検証。
- task が `blocked/cancelled/deleted` の場合は実行しない。
- 実行開始時に Task Bus を `in_progress` へ更新し、終了時に `done|failed` へ反映。
- Message Bus へ `trigger_start/trigger_end/trigger_fail` を通知する。

## 7. 依存する runtime
- Control Plane（team existence / lifecycle）
- Task Bus（task state / ownership）
- Message Bus（通知・approval・escalation）
- Runtime State Model（reconcile と監査）

## 8. 危険なケース
- recurring 実行が backlog を溜め続けるケース。
- remote trigger の重放送で同じ task が多重起動するケース。
- sleep 復帰後に owner 不在で task が漂流するケース。
- unattended write が誤設定で大量変更を起こすケース。

## 9. ロールアウト
1. Phase 1: one-shot + sleep
2. Phase 2: recurring + guardrail
3. Phase 3: remote trigger +署名検証 + idempotency 強化
