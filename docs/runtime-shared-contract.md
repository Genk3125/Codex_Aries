# Runtime Shared Contract Freeze (Phase 20-22)

- Status: Frozen
- Version: 1
- Date: 2026-04-04
- Scope: `m3-2_trigger-layer-mvp`, `m3-3_worktree-runtime-tools-mvp`, `m3-4_verifier-queue-standardization`

## 1. 目的

Phase 20-22 の統合実装前に、Trigger / Worktree / Verifier Queue が共有する契約を先に固定する。
この文書は「仕様追加」ではなく「揺れ防止」のための freeze であり、実装拡張を目的にしない。

## 2. 今回の freeze でやらないこと

- Trigger の `trigger_fire_due` を本格実装しない（I/O 契約固定のみ）
- Worktree の enter/exit を本実装へ拡張しない（最小挙動の範囲）
- Verifier Queue の retry/priority を入れない
- `runtime_reconcile_all` を変更しない
- daily-driver / Phase 19 の挙動を変更しない

## 3. Store Layout（固定）

`<store_root>/` 配下で以下を固定する。

- 既存（変更しない）:
  - `control-plane/`
  - `message-bus/`
  - `task-bus/`
- 新規（Phase 20-22）:
  - `trigger-layer/`
    - `triggers/`
    - `idempotency.json`
    - `trigger-events.log`
  - `worktree-runtime/`
    - `worktrees/`
    - `idempotency.json`
    - `worktree-events.log`
  - `verifier-queue/`
    - `requests/`
    - `idempotency.json`
    - `claim-index.json`
    - `verifier-queue-events.log`

## 4. Schema Version（固定）

- Phase 20-22 で新規作成する JSON artifact はすべて `schema_version: 1` を持つ。
- freeze 中は schema migration を導入しない。
- 既存の Control Plane / Message Bus / Task Bus の `schema_version=1` と同じ世代に合わせる。

## 5. Idempotency Key Format（固定）

形式は共通で次を採用する。

- Format: `<domain>:<operation>:<scope>:<request_token>`
- Regex: `^(trigger|worktree|verifier_queue):[a-z][a-z0-9_]{2,31}:[a-z0-9][a-z0-9._-]{1,63}:[a-z0-9][a-z0-9._-]{7,63}$`

例:

- `trigger:trigger_create:team_abc123:req_20260404_0001`
- `worktree:worktree_enter:team_abc123.member_worker01:req_enter_0001`
- `verifier_queue:verifier_request_create:task_a1b2c3:req_verify_0001`

## 6. strict / fail-open（3機能共通）

- 3機能とも adapter envelope 規約をそのまま使う（個別分岐を作らない）。
- fail-open（既定）:
  - `ok=false` + `error` を返す
  - exit code は `0`
- strict:
  - envelope 形式は同じ
  - `error != null` の場合は exit code `2`
- Verifier verdict（PASS/PARTIAL/FAIL）の分岐規約は `verifier-contract.md` を正本とし、queue 側で再定義しない。

## 7. Adapter Operation Names（固定）

命名ルールは「ドメイン接頭辞 + 動詞」の `snake_case` とする。

- Trigger:
  - `trigger_create`
  - `trigger_list`
  - `trigger_delete`
  - `trigger_fire_due`
- Worktree:
  - `worktree_enter`
  - `worktree_exit`
  - `worktree_cleanup`
  - `worktree_list`
- Verifier Queue:
  - `verifier_request_create`
  - `verifier_request_get`
  - `verifier_request_list`
  - `verifier_request_claim_once`

alias は作らない。RFC 上の表現（`enter_worktree` など）は説明語彙として扱い、adapter operation 名は上記で固定する。

## 8. 3機能の責務境界（固定）

- Trigger:
  - 担当: trigger 定義の保存、due 判定の入口、実行要求の発火
  - 非担当: queue retry、priority 制御、認可本体
- Worktree:
  - 担当: worktree 入退場、path/branch 安全境界、cleanup の最小操作
  - 非担当: task ownership 判定、自動 merge、複雑 rollback
- Verifier Queue:
  - 担当: verifier 実行要求の enqueue/get/list/claim_once
  - 非担当: verifier 判定ロジック、retry/priority、自動修正

## 9. Review Invariants（固定）

PR review で最低限以下を満たすこと。

1. operation 名が本契約の固定名と一致している
2. 新規 JSON artifact に `schema_version: 1` がある
3. store layout が本契約の固定パスから逸脱していない
4. idempotency key が固定形式（format/regex）に一致している
5. strict/fail-open の挙動が adapter 共通規約と一致している
6. `runtime_reconcile_all` に変更が入っていない
7. Trigger `fire_due` の過剰実装、Worktree 本格実装拡張、Queue retry/priority が混入していない
8. daily-driver / Phase 19 の既存フローを壊す変更がない

## 10. 次に実装する順番

1. Phase 20: Trigger
   - store + schema + operation skeleton を契約通りに実装
   - `trigger_fire_due` は最小挙動に留める
2. Phase 21: Worktree
   - safety boundary を最優先に `worktree_*` 4操作を実装
3. Phase 22: Verifier Queue
   - request queue（create/get/list/claim_once）を実装
   - verifier 判定は `verifier-contract.md` を参照し queue 側で再定義しない
