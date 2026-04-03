# Master Flow v2

_Updated: 2026-04-03_

この文書は `.planning/` 配下の subplans を読む順序と役割を定義する。
上位構想ではなく、**現在の実装カーネルを前提にした運用フロー**として使う。

参照先:
- 上位構想: `docs/CODEX_MAX_COMBINED_PLAN.md`
- 短期優先順位: `ToDo.md`

## 位置づけ

- `docs/CODEX_MAX_COMBINED_PLAN.md`: 何を作るか
- `ToDo.md`: 今どこを進めるか
- `.planning/MASTER_FLOW.md`: どの subplan をどの順で開くか
- `.planning/*/subplan.md`: 実装エージェントに渡す超具体 plan

## 完了の定義

> **「自分が日常で使う Codex 上で、Tengu 的な強さが実運用で再現され、継続利用されている」**

これは具体的には以下の全てを満たす状態:
1. セッション再開時に手動フォーマット変換が不要
2. 失敗時に recovery → escalation → 再開が自動分岐する
3. context が肥大化しても自動で圧縮され、品質が落ちない
4. computer-use（ブラウザ操作、UI 検証）がフロー内で使える
5. team runtime を使って 3+ agent の並列タスクが完走する
6. 上記が PoC ではなく日常タスクで実際に動いている

---

## Phase 1-7: Milestone 1（完了）

Stream A: Operating System for Better Runs の基盤確立。

| Phase | Status | 成果 |
|-------|--------|------|
| now-1 | `done` | compact_state --output-markdown |
| now-2 | `done` | handoff 6-section verifier-contract 整合 |
| now-3 | `done` | dogfood 3 タスク + 介入パターン類型化 |
| safety | `done` | loop guard 整合 + auto-retry 非混入確認 |
| next-1 | `done` | --from-compact を recovery_next + handoff に追加 |
| next-2 | `done` | notify_helper 新規実装 |
| next-3 | `done` | verifier exit code 規約 (0/1/2/3+) |

---

## Phase 8-18: Milestone 2（本番）

PoC → 日常運用 → Tengu 級自律性の実現。

### Settle: 運用定着（Phase 8-9）

| Phase | Status | subplan |
|-------|--------|--------|
| 8 | `not_started` | `settle-1_daily-driver-pipeline` |
| 9 | `not_started` | `settle-2_context-reduction` |

### Scope: 境界整理（Phase 10-11）

| Phase | Status | subplan |
|-------|--------|--------|
| 10 | `not_started` | `scope-1_team-runtime-boundary` |
| 11 | `not_started` | `scope-2_computer-use-freeze` |

### Build: 本実装（Phase 12-14）

| Phase | Status | subplan |
|-------|--------|--------|
| 12 | `not_started` | `build-1_computer-use-mcp-poc` |
| 13 | `not_started` | `build-2_team-runtime-mvp` |
| 14 | `not_started` | `build-3_auto-context-pipeline` |

### Harden: 検証 + 統合（Phase 15-16）

| Phase | Status | subplan |
|-------|--------|--------|
| 15 | `not_started` | `harden-1_e2e-integration-test` |
| 16 | `not_started` | `harden-2_eval-baseline` |

### Ship: 日常運用移行（Phase 17-18）

| Phase | Status | subplan |
|-------|--------|--------|
| 17 | `not_started` | `ship-1_daily-dogfood-30days` |
| 18 | `not_started` | `ship-2_milestone-closeout` |

---

## 実行順と依存

```
Phase 8 (daily-driver) ──→ Phase 9 (context-reduction)
                                │
Phase 10 (team-boundary) ───────┤  ← 並走可
Phase 11 (CU scope freeze) ─────┤
                                │
                                ▼
Phase 12 (CU MCP PoC) ──→ Phase 15 (E2E integration)
Phase 13 (team MVP)    ──→ Phase 15
Phase 14 (auto-context)──→ Phase 15
                                │
                                ▼
                          Phase 16 (eval baseline)
                                │
                                ▼
                          Phase 17 (30-day dogfood)
                                │
                                ▼
                          Phase 18 (closeout)
```

**最優先**: Phase 8 `settle-1_daily-driver-pipeline`

## 原則

- master flow は薄く保つ
- 実装詳細は subplan に押し込む
- 1 subplan = 1 実行単位
- Settle → Scope → Build → Harden → Ship の順を壊さない
- PoC で終わらせない。Ship phase まで到達して初めて完了
