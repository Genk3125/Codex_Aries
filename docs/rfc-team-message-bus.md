# RFC: Team Message Bus

- Status: Draft
- Version: 0.1
- Date: 2026-04-02
- Owner: Codex CLI Maximizer

## 1. 目的
Team 内の agent 間通信を、`direct` / `broadcast` / `control` に分離して扱う Message Bus を定義する。  
本RFCは **メッセージ配送と制御メッセージの意味論** に責務を限定する。

## 2. スコープ

### In Scope
- direct message（1対1）
- broadcast message（1対多）
- control messages（approval, shutdown, escalation）
- delivery semantics（到達保証・重複・順序）
- audit 可能な envelope 仕様

### Out of Scope（別RFCへ委譲）
- task CRUD / owner / state machine（Task Bus RFC）
- team lifecycle create/delete/persistence（Control Plane RFC）
- runtime state object の正規モデル（State Model RFC）

## 3. 設計原則
- **責務分離**: Message Bus は「通信」、Task Bus は「作業状態」を扱う。
- **明示的制御**: shutdown や approval は通常メッセージと別カテゴリにする。
- **再送安全**: `message_id` と `idempotency_key` で重複処理を避ける。
- **監査可能性**: すべての control message を永続ログに記録する。

## 4. Message Envelope

```json
{
  "message_id": "msg_...",
  "team_id": "team_...",
  "type": "direct|broadcast|control",
  "subtype": "text|approval_request|approval_response|shutdown|escalation|status",
  "from_member_id": "agent_...",
  "to_member_ids": ["agent_..."],
  "correlation_id": "optional-request-id",
  "idempotency_key": "optional-key",
  "created_at": "ISO-8601",
  "payload": {}
}
```

## 5. 配送モデル

## 5.1 Direct
- 送信先は1 member。
- 既定は `at-least-once`（重複許容、受信側で `message_id` 重複除去）。
- 同一 `(team_id, from_member_id, to_member_id)` の FIFO を保証する。

## 5.2 Broadcast
- 送信時に team の active member snapshot を固定し fan-out する。
- member ごとに配送状態を持つ（`pending|delivered|failed|expired`）。
- 新規参加 member には過去 broadcast を自動再配送しない（非対応）。

## 5.3 Delivery Semantics
- 既定: `at-least-once` + per-recipient ack。
- timeout 後は最大 N 回再送（N は runtime 設定）。
- 最終失敗時は `DELIVERY_EXHAUSTED` を event 化し escalation 対象にする。
- `control.shutdown` は best-effort ではなく ack 必須。

## 6. Control Messages

## 6.1 Approval
- `approval_request` は `correlation_id` 必須。
- `approval_response` は `approved|rejected|needs_clarification` を持つ。
- timeout 時は `approval_timeout` として escalation に回す。

## 6.2 Shutdown
- `shutdown` は `graceful|force` を明示。
- `graceful` は in-flight 処理完了待ち、`force` は即中断。
- 全 member ack 受領または timeout 到達で Control Plane の delete/cleanup に接続。

## 6.3 Escalation
- 失敗分類（delivery failure, approval timeout, member unresponsive）を添えて leader に通知。
- leader 未応答なら root/coordinator へ再エスカレート。
- escalation 自体も control message として監査対象。

## 7. エラーモデル
- `MESSAGE_SCHEMA_INVALID`
- `RECIPIENT_NOT_FOUND`
- `TEAM_NOT_ACTIVE`
- `CONTROL_MESSAGE_REJECTED`
- `DELIVERY_EXHAUSTED`
- `CORRELATION_NOT_FOUND`

## 8. Control Plane 依存
- member 一覧・lifecycle 取得は Control Plane を参照。
- team が `deleting`/`deleted` なら新規 message enqueue を拒否。
- shutdown 完了判定は Control Plane の member state と照合して確定。

## 9. Task Bus に委ねること
- task 作成/更新/完了の永続状態。
- task owner 変更・blocked reason・result reference。
- message と task の論理リンクは `correlation_id` で接続し、task state 変更自体は Task Bus が担う。

## 10. 破綻しやすい箇所
- broadcast 中の membership 変化による配送漏れ。
- approval request の多重送信で競合応答が発生するケース。
- shutdown 中に通常メッセージが流入し続けるケース。
- restart 後の重複再送で副作用が二重適用されるケース。

## 11. ロールアウト
1. Phase 1: direct + control(shutdown) の最小実装
2. Phase 2: approval/escalation と audit 強化
3. Phase 3: broadcast fan-out の耐障害化
