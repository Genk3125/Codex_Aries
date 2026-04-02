# RFC: Team Task Bus

- Status: Draft
- Version: 0.1
- Date: 2026-04-02
- Owner: Codex CLI Maximizer

## 1. 目的
Team 実行で扱う作業単位を、通信（Message Bus）から分離して **永続可能な task state** として管理する。  
本RFCは task CRUD と state transition を定義する。

## 2. スコープ

### In Scope
- task CRUD
- owner 管理
- state transitions
- blocked reason
- result reference
- idempotency

### Out of Scope
- agent 間の送受信仕様（Message Bus RFC）
- team create/delete/cleanup（Control Plane RFC）
- 共通 runtime state 正規モデル（State Model RFC）

## 3. なぜ Message Bus だけでは足りないか
- Message Bus は「伝達履歴」だが、Task Bus は「現在の責務状態」を保持する。
- retry や resume で必要なのは最新 task 状態であり、メッセージ列の再解釈だけでは高コストかつ不安定。
- owner/blocked/result は業務意味を持つため、message payload に埋め込まず first-class に持つ必要がある。

## 4. Task モデル

```json
{
  "task_id": "task_...",
  "team_id": "team_...",
  "title": "short summary",
  "description": "optional",
  "owner_member_id": "agent_...",
  "state": "todo|ready|in_progress|blocked|done|cancelled|failed",
  "blocked_reason": null,
  "result_reference": null,
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "version": 1,
  "idempotency_key": "optional"
}
```

## 5. API 仕様

## 5.1 Create
- 入力: `title`, `owner_member_id?`, `idempotency_key?`, `description?`
- 出力: `task_id`, 初期 state（既定 `todo`）
- 規則: 同一 `idempotency_key` は同一レスポンスを返す

## 5.2 Read
- `get_task(task_id)`, `list_tasks(team_id, filters)`
- filters: `state`, `owner_member_id`, `updated_since`

## 5.3 Update
- 更新対象: `owner_member_id`, `state`, `blocked_reason`, `result_reference`, `description`
- `version` 一致必須（楽観ロック）

## 5.4 Delete
- 物理削除しない。`state=cancelled` + tombstone event 記録を既定とする。

## 6. State Transition ルール

```
todo -> ready -> in_progress -> done
                 \-> blocked -> ready
in_progress -> failed
* -> cancelled
```

- `blocked` へ遷移する場合 `blocked_reason` 必須。
- `done` へ遷移する場合 `result_reference` 推奨（実行ログ/PR/artifact）。
- `cancelled` は終端状態。

## 7. Owner モデル
- owner は `member_id` で参照（Control Plane の member 実在チェック必須）。
- owner 不在（member shutdown）時は `ready` へ戻し、`owner_member_id=null` にする。
- leader は owner 再割当の最終責任を持つ。

## 8. Idempotency
- Create: `idempotency_key` で重複作成防止。
- Update: `version` + `idempotency_key`（任意）で二重更新防止。
- 同一更新の再送は no-op として成功扱い。

## 9. Result Reference
- `result_reference` は実成果物への参照を保持する。
- 例: `log://...`, `artifact://...`, `pr://...`, `file:///...`
- Task Bus は参照整合性を厳密検証しない（存在確認は verifier へ委譲）。

## 10. Message Bus との接続
- task の割当依頼/進捗報告通知は Message Bus で運ぶ。
- task state 変更の正本は Task Bus。
- `correlation_id` で message と task event を相互参照可能にする。

## 11. 破綻しやすい箇所
- owner 変更と state 変更の競合更新。
- blocked_reason を更新しないまま `blocked` へ遷移する不整合。
- resume 後に stale version で更新し続けるケース。
- `done` だが `result_reference` が空で検証不能なケース。

## 12. ロールアウト
1. Phase 1: CRUD + 最小 state machine
2. Phase 2: version/idempotency 強化
3. Phase 3: Message Bus / verifier 連携の監査強化
