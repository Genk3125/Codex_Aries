# Master Flow v2.1

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
2. 失敗時に recovery → escalation → 再開の分岐が**半自動以上**で成立し、operator が次アクションに迷わない
3. context が肥大化しても自動で圧縮され、品質が落ちない
4. computer-use（ブラウザ操作、UI 検証）がフロー内で使える
5. team runtime を使って 3+ agent の並列タスクが完走する
6. 上記が PoC ではなく日常タスクで実際に動いている

補足:
- Milestone 2 の完了時点では **full auto loop** までは必須にしない
- ただし、停止/エスカレーション/再開の判断材料が自動生成され、single-pass 運用で継続利用できることは必須

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

## Phase 8-18: Milestone 2（実装完了 / Ship provisional）

PoC → 日常運用 → Tengu 級自律性の実現。

### Settle: 運用定着（Phase 8-9）

| Phase | Status | subplan |
|-------|--------|--------|
| 8 | `done` | `settle-1_daily-driver-pipeline` |
| 9 | `done` | `settle-2_context-reduction` |

### Scope: 境界整理（Phase 10-11）

| Phase | Status | subplan |
|-------|--------|--------|
| 10 | `done` | `scope-1_team-runtime-boundary` |
| 11 | `done` | `scope-2_computer-use-freeze` |

### Build: 本実装（Phase 12-14）

| Phase | Status | subplan |
|-------|--------|--------|
| 12 | `done` | `build-1_computer-use-mcp-poc` |
| 13 | `done` | `build-2_team-runtime-mvp` |
| 14 | `done` | `build-3_auto-context-pipeline` |

### Harden: 検証 + 統合（Phase 15-16）

| Phase | Status | subplan |
|-------|--------|--------|
| 15 | `done` | `harden-1_e2e-integration-test` |
| 16 | `done` | `harden-2_eval-baseline` |

### Ship: 日常運用移行（Phase 17-18）

| Phase | Status | subplan |
|-------|--------|--------|
| 17 | `provisional` | `ship-1_daily-dogfood-30days` |
| 18 | `provisional` | `ship-2_milestone-closeout` |

**Milestone 2 状態**: 実装完了 / Ship provisional  
（compressed 30 cycles は完了、calendar 30-day dogfood は pending）

**M2 final 判定条件**: real-world calendar 30-day dogfood を完了し、Ship 判定を `final` に更新すること。

## Milestone 2 実装完了サマリ（provisional）

- closeout: `docs/milestone-2-closeout.md`
- baseline: `eval/baseline-results.md`
- e2e: `tests/e2e/results/2026-04-03T21-36-56/summary.md`
- daily dogfood（compressed 30 cycles）: `logs/daily-dogfood-30.md`

---

## Phase 19-25: Milestone 3（95% 仕上げ）

Milestone 3 は「新しい判断主体を増やさずに、既存 runtime kernel を実運用へ仕上げる」フェーズ。

### Track A: Ship Finalization（Phase 19）

| Phase | Status | subplan |
|-------|--------|--------|
| 19 | `in_progress` | `m3-1_real-world-30day-dogfood` |

### Track B: Runtime Capabilities（Phase 20-22）

| Phase | Status | subplan |
|-------|--------|--------|
| 20 | `not_started` | `m3-2_trigger-layer-mvp` |
| 21 | `not_started` | `m3-3_worktree-runtime-tools-mvp` |
| 22 | `not_started` | `m3-4_verifier-queue-standardization` |

### Track C: Scope / Release Discipline（Phase 23-25）

| Phase | Status | subplan |
|-------|--------|--------|
| 23 | `not_started` | `m3-5_team-runtime-deferred-priority` |
| 24 | `not_started` | `m3-6_docs-status-release-sync` |
| 25 | `not_started` | `m3-7_ts-boundary-decision` |

**次の最優先**: Phase 19 `m3-1_real-world-30day-dogfood`
- **準備状態**: `ready_to_run`（Step 1 完了、Day 1 = 2026-04-06 JST）

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
                     Phase 17 (compressed dogfood)
                                │
                                ▼
                 Phase 18 (provisional closeout)
                                │
                                ▼
                  Phase 19 (real 30-day dogfood)
                                │
                                ▼
            ┌───────────── Phase 20 (trigger mvp) ─────────────┐
            │                                                   │
            ├───────────── Phase 21 (worktree mvp) ─────────────┤
            │                                                   │
            └───────────── Phase 22 (verifier queue) ───────────┘
                                │
                                ▼
                    Phase 23 (deferred priority)
                                │
                                ▼
                    Phase 24 (docs/status sync)
                                │
                                ▼
                    Phase 25 (TS boundary decision)
```

## Milestone 3 完了の定義（95%）

1. Milestone 2 Ship が `final` になっている（real-world 30-day 実績）
2. Trigger / Worktree / Verifier queue が MVP として呼び出し可能
3. deferred team runtime 項目の優先順位が明文化され、次の実装順が固定
4. docs/status の差分が定期チェックで検出可能
5. TS へ寄せる境界が「やる/やらない」を判断済み

## 原則

- master flow は薄く保つ
- 実装詳細は subplan に押し込む
- 1 subplan = 1 実行単位
- Settle → Scope → Build → Harden → Ship の順を壊さない
- 実装完了と実運用完了を混同しない（`provisional` / `final` を明示する）
- PoC で終わらせない。Ship `final` 到達で初めて完了
