# Execution Task Breakdown v1.0

_Date: 2026-04-02_

> 現在の実装カーネル基準の優先作業は `/Users/kondogenki/AI Agent Maximizer/ToDo.md` を最優先で参照。
> この文書は **初期実装フェーズの分解記録** として保持する。

## 0) 目的

この文書は、`docs/CODEX_MAX_COMBINED_PLAN.md` をそのまま実行に移すための:

- 具体的なタスク分解
- 実装順序
- 実装エージェントに渡す短いプロンプト

を定義する。

方針は単純:

- **短いプロンプトで振る**
- **成果物を明示する**
- **完了報告では「何ができるようになったか」を必ず書かせる**

## 0.5) 現在の位置づけ

- ここに書かれた初期タスクの多くは完了済み。
- 現在は RFC 中心ではなく、`poc/` と `~/.codex` を使った運用カーネルの強化段階に入っている。
- 新しい短期優先順位は `ToDo.md` に寄せる。

---

## 1) 実行順

1. A1: `AGENTS.md` Mini
2. A2: `coordinator` / `verifier` custom agents
3. A3: verifier contract
4. F1: baseline evals
5. B1: Team Control Plane RFC
6. B2: Team Message Bus RFC
7. B3: Team Task Bus RFC
8. B4: Team state model
9. C1: Worktree runtime RFC
10. C2: Plan mode runtime RFC
11. D1: Trigger layer RFC
12. E1: Recovery playbook
13. E2: Memory experiment design

---

## 2) タスク分解

## Phase A — Operating Layer

### A1. `AGENTS.md` Mini を作る

**目的**
- Codex の出力品質を最短で底上げする

**成果物**
- `AGENTS.md` または配置先の草案

**Done**
- Plan / Execute 分離がある
- read parallel / write serial がある
- Recovery Loop がある
- 検証未実施を隠さない規律がある
- 長すぎない

### A2. `coordinator` / `verifier` agent を作る

**目的**
- coordinator / verifier の役割を固定する

**成果物**
- `agents/coordinator.toml`
- `agents/verifier.toml`

**Done**
- 役割が重複していない
- verifier が read-only 前提になっている
- coordinator が「理解を委譲しない」前提になっている

### A3. verifier contract を作る

**目的**
- 検証結果を比較可能なフォーマットに統一する

**成果物**
- `verifier-contract.md`

**Done**
- `PASS | PARTIAL | FAIL`
- 実行コマンド
- 実出力
- 未検証項目
- 次の対応

---

## Phase F — Evaluation

### F1. baseline evals を固定する

**目的**
- 改善を数値で見られるようにする

**成果物**
- `evals/baseline-tasks.md`
- `logs/baseline-results-YYYYMMDD.md`

**Done**
- 少なくとも 10 タスク
- small / medium / large がある
- team orchestration 系の評価を含む
- success / speed / recovery を見られる

---

## Phase B — Team Runtime Core

### B1. Team Control Plane RFC

**目的**
- team の作成、削除、永続状態を仕様化する

**成果物**
- `docs/rfc-agent-team-control-plane.md`

**Done**
- `team_create`
- `team_delete`
- leader/member model
- persistence
- cleanup
- resume 方針

### B2. Team Message Bus RFC

**目的**
- team 内通信を protocol 化する

**成果物**
- `docs/rfc-team-message-bus.md`

**Done**
- direct
- broadcast
- control messages
- shutdown
- approval
- escalation

### B3. Team Task Bus RFC

**目的**
- shared task list を仕様化する

**成果物**
- `docs/rfc-team-task-bus.md`

**Done**
- task CRUD
- owner
- state transition
- blocked reason
- result reference

### B4. Team state model を固める

**目的**
- 3つの RFC を接続する共通状態を定義する

**成果物**
- `docs/team-runtime-state-model.md`

**Done**
- team
- member
- task
- message
- lifecycle
- invariants

---

## Phase C — Runtime Control

### C1. Worktree runtime RFC

**目的**
- worktree 切替を model-callable runtime として設計する

**成果物**
- `docs/rfc-worktree-runtime-tools.md`

**Done**
- `enter_worktree`
- `exit_worktree`
- path / branch / cleanup
- safety constraints

### C2. Plan mode runtime RFC

**目的**
- plan mode 遷移を model-callable に整理する

**成果物**
- `docs/rfc-plan-mode-runtime-tools.md`

**Done**
- `enter_plan_mode`
- `exit_plan_mode`
- approval semantics
- existing collaboration mode との整合

---

## Phase D — Trigger Layer

### D1. Trigger layer RFC

**目的**
- cron / remote trigger / sleep を同一レイヤーで整理する

**成果物**
- `docs/rfc-trigger-layer.md`

**Done**
- one-shot
- recurring
- remote trigger
- wait/sleep semantics
- unattended risk controls

---

## Phase E — Recovery / Memory

### E1. Recovery playbook

**目的**
- 失敗後の挙動を標準化する

**成果物**
- `docs/recovery-playbook.md`

**Done**
- retry 1回目
- independent verify
- 2回失敗で escalate
- failure taxonomy

### E2. Memory experiment design

**目的**
- hooks 依存を前提にしない形で memory 近似案を整理する

**成果物**
- `docs/rfc-memory-experiment.md`

**Done**
- scope
- fail-open
- trigger point
- rollback
- non-goals

---

## 3) エージェントプロンプトの型

以下の形式を基本にする。  
長い背景説明は避ける。

```text
目的:
成果物:
必須観点:
完了時に書くこと:
- 何を作ったか
- 何ができるようになったか
- 未解決の論点
```

---

## 4) 実装エージェント用プロンプト

## Prompt A1

```text
目的:
Codex 向けの AGENTS.md mini を作ってください。短く、効く規律だけに絞ってください。

成果物:
- AGENTS.md 草案

必須観点:
- Plan / Execute 分離
- read は並列、write は直列
- Recovery Loop
- 検証未実施を隠さない
- 長くしすぎない

完了時に書くこと:
- 何を作ったか
- 何ができるようになったか
- 削った規律とその理由
```

## Prompt A2

```text
目的:
coordinator と verifier の custom agent 定義を作ってください。

成果物:
- coordinator.toml
- verifier.toml

必須観点:
- coordinator は調査結果の合成が仕事
- verifier は read-only 前提
- 役割を重複させない

完了時に書くこと:
- 何を作ったか
- 何ができるようになったか
- まだ弱い点
```

## Prompt A3

```text
目的:
verifier の出力契約を文書化してください。

成果物:
- verifier-contract.md

必須観点:
- PASS / PARTIAL / FAIL
- 実行コマンド
- 実出力
- 未検証項目
- 次の対応

完了時に書くこと:
- 何を作ったか
- 何ができるようになったか
- 運用で迷いそうな点
```

## Prompt F1

```text
目的:
baseline eval タスクを定義してください。改善前後を比較できるようにしたいです。

成果物:
- baseline-tasks.md
- baseline-results template

必須観点:
- 少なくとも 10 タスク
- small / medium / large
- team orchestration を含む
- success / speed / recovery を見られる

完了時に書くこと:
- 何を作ったか
- 何が測れるようになったか
- 足りない評価観点
```

## Prompt B1

```text
目的:
Agent Team Control Plane の RFC を書いてください。

成果物:
- rfc-agent-team-control-plane.md

必須観点:
- team_create
- team_delete
- leader/member model
- persistence
- cleanup
- resume

完了時に書くこと:
- 何を設計したか
- 何ができるようになるか
- Message Bus / Task Bus に委ねたこと
```

## Prompt B2

```text
目的:
Team Message Bus の RFC を書いてください。

成果物:
- rfc-team-message-bus.md

必須観点:
- direct
- broadcast
- control messages
- shutdown
- approval
- escalation

完了時に書くこと:
- 何を設計したか
- 何ができるようになるか
- Control Plane との接点
```

## Prompt B3

```text
目的:
Team Task Bus の RFC を書いてください。

成果物:
- rfc-team-task-bus.md

必須観点:
- task CRUD
- owner
- state transitions
- blocked reason
- result reference

完了時に書くこと:
- 何を設計したか
- 何ができるようになるか
- Message Bus だけでは足りない理由
```

## Prompt B4

```text
目的:
Team Runtime の state model を定義してください。Control Plane, Message Bus, Task Bus をつなぐ共通状態が欲しいです。

成果物:
- team-runtime-state-model.md

必須観点:
- team
- member
- task
- message
- lifecycle
- invariants

完了時に書くこと:
- 何を定義したか
- 何が一貫して扱えるようになるか
- 破綻しやすい箇所
```

## Prompt C1

```text
目的:
model-callable worktree tools の RFC を書いてください。

成果物:
- rfc-worktree-runtime-tools.md

必須観点:
- enter_worktree
- exit_worktree
- branch / path
- cleanup
- safety

完了時に書くこと:
- 何を設計したか
- 何ができるようになるか
- 危険なケース
```

## Prompt C2

```text
目的:
model-callable plan mode tools の RFC を書いてください。

成果物:
- rfc-plan-mode-runtime-tools.md

必須観点:
- enter_plan_mode
- exit_plan_mode
- approval
- existing mode との整合

完了時に書くこと:
- 何を設計したか
- 何ができるようになるか
- UI / runtime の衝突点
```

## Prompt D1

```text
目的:
Trigger Layer の RFC を書いてください。cron, remote trigger, sleep を一つの観点で整理したいです。

成果物:
- rfc-trigger-layer.md

必須観点:
- one-shot
- recurring
- remote trigger
- sleep / wait
- unattended risk control

完了時に書くこと:
- 何を設計したか
- 何ができるようになるか
- Team Runtime との接続点
```

## Prompt E1

```text
目的:
Recovery Playbook を作ってください。失敗後の動き方を標準化したいです。

成果物:
- recovery-playbook.md

必須観点:
- first retry
- independent verify
- escalate
- failure taxonomy

完了時に書くこと:
- 何を作ったか
- 何ができるようになったか
- 自動化しにくい判断
```

## Prompt E2

```text
目的:
Memory の近似実装を experimental として設計してください。中核依存にはしません。

成果物:
- rfc-memory-experiment.md

必須観点:
- fail-open
- limited scope
- trigger point
- rollback
- non-goals

完了時に書くこと:
- 何を設計したか
- 何ができるようになるか
- なぜ P2 扱いなのか
```

---

## 5) 実装エージェントへの共通注意

- 背景説明を増やしすぎない
- 先に structure を決める
- 書いた文書の責務境界を明示する
- 他 RFC に委ねたことを明記する
- 完了報告では **「何ができるようになったか」** を必ず書く

推奨の締め:

```text
実装完了。

作成物:
- ...

できるようになったこと:
- ...

未解決:
- ...
```
