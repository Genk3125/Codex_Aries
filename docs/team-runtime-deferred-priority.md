# Team Runtime Deferred Items Priority (Phase 23)

_Date: 2026-04-04_

## 1. Deferred Items Inventory

| # | Item | Source | Dependency | Known Risk |
|---|------|--------|-----------|------------|
| D1 | Leader handoff（leader 交代プロトコル） | control_plane.py L54 stub | team_delete/member_remove 安定後 | handoff 中の race condition |
| D2 | Task auto-reassign（owner 離脱時の自動再割当） | task_bus.py reconcile | task state machine 安定後 | 二重割当リスク |
| D3 | Message retry（配信失敗時の再送） | message_bus.py deferred | claim_once 安定後 | 重複配信リスク |
| D4 | Broadcast（全メンバー一斉送信） | message_bus.py 未実装 | Message Bus 安定後 | 大規模チームで N 倍送信 |
| D5 | Approval workflow（control message での承認フロー） | message_bus.py 未実装 | control type 安定後 | UX が複雑化するリスク |
| D6 | ControlPlane ↔ MessageBus/TaskBus 統合（stub 解消） | control_plane.py _message_bus_stub / _task_bus_stub | Phase 20-22 完了後 | 統合後の整合性検証コスト |
| D7 | Verifier Queue の gate/chain opt-in 接続 | verifier_gate_helper.py | verifier_queue.py (Phase 22) 完了後 | gate フロー変更で既存動作に影響 |

## 2. Priority Scoring Matrix

評価軸: Impact(1-5) / Risk(1-5 高=危険) / Effort(1-5 高=大) / Operability(1-5 高=良い)
**Priority Score = Impact × Operability / (Risk × Effort)**（高いほど優先）

| # | Item | Impact | Risk | Effort | Operability | Score | Rank |
|---|------|--------|------|--------|-------------|-------|------|
| D6 | ControlPlane stub 解消 | 4 | 3 | 3 | 4 | 1.78 | **1** |
| D7 | Verifier Queue gate opt-in | 4 | 2 | 2 | 4 | 4.00 | **2** |
| D2 | Task auto-reassign | 3 | 3 | 3 | 3 | 1.00 | **3** |
| D3 | Message retry | 3 | 4 | 3 | 3 | 0.75 | 4 |
| D1 | Leader handoff | 3 | 4 | 4 | 2 | 0.38 | 5 |
| D4 | Broadcast | 2 | 3 | 2 | 3 | 1.00 | 3※ |
| D5 | Approval workflow | 2 | 3 | 4 | 2 | 0.33 | 6 |

※D2とD4はスコア同値。D2はcore機能なので優先。

## 3. 次フェーズへの反映（上位3件）

**Phase 26 候補（next milestone）:**
1. **D7: Verifier Queue gate/chain opt-in** — Phase 22完了直後でコスト最小、fail-open/strict 透過を確認しながら接続
2. **D6: ControlPlane stub 解消** — MessageBus/TaskBus 統合で runtime 整合性が上がる
3. **D2: Task auto-reassign** — deferred owner が増えると daily-driver に影響するため早期対応価値あり

**Backlog（現時点では着手しない）:**
- D3 Message retry, D1 Leader handoff, D4 Broadcast, D5 Approval workflow

## 4. 根拠ノート

- D7を最優先にする理由: Phase 22 で verifier_queue.py が完成したため接続コストが最小。dogfood 中に verifier を queue 経由で叩く実績が取れる
- D6を次にする理由: stub のまま放置すると control_plane と message_bus/task_bus の乖離が広がる
- D1/D3 は high risk のため、基盤が安定してから着手
