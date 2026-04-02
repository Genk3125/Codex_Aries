# team_member_add / team_member_remove — 設計メモ

- Version: 0.2
- Date: 2026-04-03
- 対象ファイル: `poc/team_control_plane.py`, `poc/codex_runtime_adapter.py`

## 1. 目的

Control Plane に member の追加・削除操作を追加し、  
Message Bus の direct message が「実在 member」宛に成功するための前提を作る。

---

## 2. 実装した操作

### team_member_add

| 項目 | 内容 |
|---|---|
| 入力 | `team_id`, `agent_id`, `role` (default: "member"), `idempotency_key` (optional) |
| lifecycle 初期値 | `"running"` |
| 一意性 | `agent_id` が既存 members に存在すると `MEMBER_ALREADY_EXISTS` エラー |
| team status ガード | `deleting` / `deleted` の場合 `TEAM_NOT_MUTABLE` で拒否 |
| idempotency | `idempotency_key` 指定時、同一キーの2回目は保存済みレスポンスを返す |
| 永続化 | `team-{id}.json` の members リストに追記、`_save_team` で version/updated_at を更新 |
| イベントログ | `team_member_add` イベントを `team-events.log` に記録 |

**lifecycle = "running" を選んだ理由:**  
Message Bus の `_evaluate_recipient_delivery` は lifecycle が `running` / `idle` の場合にのみ `delivered` にする。  
追加直後に宛先として使えるようにするため、初期値を `running` とした。

---

### team_member_remove

| 項目 | 内容 |
|---|---|
| 入力 | `team_id`, `agent_id`, `reason` (optional) |
| 動作 | member の lifecycle を `"shutdown"` にセット（物理削除しない） |
| 冪等性 | 既に `shutdown` なら `already_removed: true` で成功応答 |
| team status ガード | `deleted` チームは `TEAM_NOT_FOUND` で拒否。`deleting` は許可（削除途中でも明示 remove を受け付ける） |
| 存在チェック | member が見つからない場合 `MEMBER_NOT_FOUND` |
| リーダー削除 | `LEADER_REMOVAL_NOT_ALLOWED` で拒否（leader invariant を壊さない） |
| イベントログ | `team_member_remove` イベントを記録 |

**物理削除しない理由:**  
`_finalize_delete` が lifecycle を `shutdown` にセットする既存パターンと一致させる。  
メッセージ履歴・監査・orphan owner 検出のため記録を残す。

---

## 3. 各コンポーネントへの影響

### Message Bus への影響

| 状態 | send_message 結果 |
|---|---|
| member 未登録 | `failed` / `RECIPIENT_NOT_FOUND` |
| member_add 後（lifecycle: running） | `delivered` |
| member_remove 後（lifecycle: shutdown） | `failed` / `RECIPIENT_NOT_DELIVERABLE:shutdown` |

**send_message の失敗を減らすには:**  
`send_message` を呼ぶ前に `team_member_add` で宛先を確実に登録すること。  
lifecycle: running の member にのみ送ることで `RECIPIENT_NOT_FOUND` は撲滅できる。  
`RECIPIENT_NOT_DELIVERABLE:shutdown` は remove 後の送信で発生するため、  
remove 後は Message Bus のレコンシール（`message_startup_reconcile`）で pending を処理することを想定。

### Task Bus への影響

remove された member が task の owner だった場合:  
- Task Bus は自動検出しない（今回の範囲外）
- `startup_reconcile_orphan_owners` を実行することで `lifecycle: shutdown` の owner を孤立検出し、  
  `owner_member_id: null` に更新する

### leader removal 方針（採用）

今回は **leader removal を拒否** する方針を採用。  
理由:
1. `leader_agent_id` と `members` の整合を壊さないため（stale leader を許容しない）。
2. leader 再選出・handoff が未実装の段階での安全側動作にするため。
3. Message Bus / Task Bus 連携時の孤立状態を増やさないため。

このため `team_member_remove` は leader 対象時に `LEADER_REMOVAL_NOT_ALLOWED` を返す。

---

## 4. 既存機能との共存

| 機能 | 影響 |
|---|---|
| team_create | 変わらず leader を lifecycle: running で作成。互換あり |
| team_delete / _finalize_delete | members を shutdown にする既存ロジックは変わらず動く。member_add で追加されたメンバーも同様に shutdown される |
| startup_reconcile (control plane) | deleting チームを finalize するだけ。member_add で増えたメンバーも cleanup_summary.members_closed に含まれる |
| startup_reconcile (message bus) | pending delivery の再評価。member_remove 後の shutdown lifecycle も正しく判定される |
| startup_reconcile_orphan_owners (task bus) | remove 後の owner が shutdown なら孤立検出される。動作は変わらず |

---

## 5. 今回やっていないこと

- approval: add/remove に承認フローなし
- broadcast: member 変更を他 member に通知しない
- 自動再割当: remove 後の task owner を自動で別 member に変えない
- UI / trigger / worktree: なし
- leader 再選出: 未実装（leader remove 自体を拒否）

---

## 6. 修正起点（検知 → 確定）

今回の修正（leader removal 方針変更 / idempotency schema 整合）は、次の2段階で確定した。

1. **違和感の検知（一次トリガー）**  
   `/Users/kondogenki/Downloads/team-member-impl-summary.md` の内容を読み、  
   「leader removal を許可するが `leader_agent_id` は更新しない」方針に不整合リスクを検知。
2. **実装確認での確定（二次トリガー）**  
   `poc/team_control_plane.py` を精査し、以下を直接の修正対象として確定。
   - `team_member_remove` 本体（`poc/team_control_plane.py:406` 以降）
   - warning-only だった leader removal 分岐（旧 `poc/team_control_plane.py:434` 付近）
   - `_read_idempotency` の default schema 不整合（`poc/team_control_plane.py:132`）

このため、今回の最小修正では以下を採用した。
- leader removal は `LEADER_REMOVAL_NOT_ALLOWED` で拒否
- `_read_idempotency()` は `team_member_add` を含む shape に正規化

---

## 7. 動作確認手順

```bash
cd /Users/kondogenki/AI\ Agent\ Maximizer/poc

# 1. team 作成
python team_control_plane.py --store-root /tmp/cp-demo team-create --team-name demo --leader-agent-id leader_x
# team_id を控える (例: team_abc123)

# 2. member 追加
python team_control_plane.py --store-root /tmp/cp-demo member-add --team-id <team_id> --agent-id worker_y

# 3. member 確認
python team_control_plane.py --store-root /tmp/cp-demo list-teams

# 4. Message Bus で追加した member に送信 -> delivered
python team_message_bus.py \
  --store-root /tmp/mb-demo \
  --control-plane-store-root /tmp/cp-demo \
  send-direct \
  --team-id <team_id> \
  --from-member-id leader_x \
  --to-member-id worker_y

# 5. member 削除
python team_control_plane.py --store-root /tmp/cp-demo member-remove --team-id <team_id> --agent-id worker_y --reason done

# 6. 削除後に送信 -> RECIPIENT_NOT_DELIVERABLE:shutdown
python team_message_bus.py \
  --store-root /tmp/mb-demo \
  --control-plane-store-root /tmp/cp-demo \
  send-direct \
  --team-id <team_id> \
  --from-member-id leader_x \
  --to-member-id worker_y

# 7. runtime adapter 経由
python codex_runtime_adapter.py op --name team_member_add \
  --args-json '{"team_id":"<team_id>","agent_id":"worker_z","role":"member"}'

python codex_runtime_adapter.py op --name team_member_remove \
  --args-json '{"team_id":"<team_id>","agent_id":"worker_z"}'

# 8. ops 一覧に含まれることを確認
python codex_runtime_adapter.py ops | python -c "import json,sys; d=json.load(sys.stdin); print('add' in str(d), 'remove' in str(d))"
```
