# Codex CLI Maximizer 統合プラン v2.0

_Date: 2026-04-03_

## Milestone 2 Closeout Snapshot (2026-04-03)

- closeout report: `docs/milestone-2-closeout.md`
- baseline metrics: `eval/baseline-results.md`（6/6 target 達成）
- daily dogfood: `logs/daily-dogfood-30.md`（compressed 30 cycles で PASS / Ship provisional）
- e2e integration: `tests/e2e/results/2026-04-03T21-25-25/summary.md`（5/5 PASS）

次フェーズは Milestone 3 として Trigger / Worktree / Automation 拡張を優先する。

## 0) 結論

**最適解は二段構え。**

1. **短期**: `AGENTS.md`、custom agents、verification discipline、`/plan`、`/compact` で運用品質をすぐ上げる  
2. **中期**: Claude Code にあって Codex に薄い **Team / Task / Trigger / Runtime Control Plane** を実装して、長時間・並列・非同期運用を安定化する

この順番が重要。  
先に運用規律だけ入れると即効性がある。先に hooks や memory に振り切ると、実験機能に依存して不安定になりやすい。

---

## 1) 評価

## ver1 の強い点

- **Plan / Execute 分離**の発想が正しい
- **Recovery Loop** を明示しているのが良い
- **coordinator / verifier** の役割分離は、そのまま採用価値が高い
- `AGENTS.md` で思考規律を注入する方針は、最短で効く
- `/compact` を運用対象として扱っているのも良い

## ver1 の弱い点

- **運用レイヤーに寄りすぎ**で、Claude 優位の本丸である **Team / Task / Trigger** が相対的に弱い
- `auto-memory` をやや早く置きすぎている
- hooks 前提の設計が多く、**experimental 依存リスク**が高い
- `AGENTS.md` が大きすぎて、最初から全部入れると効き目と副作用を切り分けづらい

## ver2 の強い点

- **Claude と Codex の差分に優先順位を付けている**
- **WS-B Team Runtime P0** を中核に置いているのが正しい
- **評価系を並走**させているのが良い
- **worktree / plan mode / scheduler** を runtime 拡張として分離していて整理が良い

## ver2 の弱い点

- 短期即効レイヤーがやや薄い
- `coordinator / verifier / recovery discipline` の思想面が ver1 より弱い
- 「どこまでが Codex 既存機能で、どこからが追加実装か」の境界がもう少し明確な方がよい

## 統合判断

**採るべき核は次の3つ。**

1. ver1 の **運用規律**
2. ver2 の **差分実装優先順位**
3. Claude 調査結果から見えた **Team Runtime first** の方針

---

## 2) 前提整理

## 既に Codex にあるもの

- subagents
- `/plan`
- `/agent`
- MCP
- hooks
- skills
- plugins
- `/compact`

したがって、`subagent を入れる` はテーマではない。  
本当のテーマは **subagent を team として継続運用できるようにすること**。

## Claude 側で優位なもの

- **Team create/delete**
- **team message bus**
- **team task bus**
- **model-callable worktree enter/exit**
- **model-callable plan mode enter/exit**
- **cron / remote trigger / sleep**
- **team-aware memory / session memory**
- **coordinator 用の専用 runtime と structured output 契約**

---

## 3) 統合設計原則

1. **運用改善と基盤改善を分離する**
   すぐ効くものと、作り込むべきものを混ぜない。

2. **P0 は Team Runtime**
   Claude 的な粘り強さの源泉はここ。memory ではない。

3. **hooks は補助輪として扱う**
   中核機能を hooks に依存させない。

4. **AGENTS.md は Mini → Full の二段階**
   一気に肥大化させず、効く規律だけ先に入れる。

5. **評価を同時に走らせる**
   改善を体感で判定しない。

---

## 4) 最高版ロードマップ

## Stream A: Operating System for Better Runs

### 目的

コード変更なし、または最小変更で **成功率・再現性・検証品質** を上げる。

### 内容

1. `AGENTS.md` Mini を作る
   - Plan / Execute 分離
   - 理解してから動く
   - read は並列、write は直列
   - Recovery Loop
   - 検証未実施を隠さない

2. custom agents を整備
   - `coordinator`
   - `verifier`
   - 必要なら `explorer` 相当の repo 調査役

3. verifier contract を固定
   - `PASS | PARTIAL | FAIL`
   - 実行コマンド
   - 実出力
   - 未検証項目

4. `/compact` 運用ルールを決める
   - いつ compact するか
   - compact 後に何を残すか

### Exit Criteria

- 同一タスクの再実行でブレが減る
- verifier の出力形式が安定する
- 大タスクで `/plan` を経由する率が上がる

### 優先度

**最優先**

---

## Stream B: Team Runtime Core

### 目的

Codex を「subagent があるツール」から **team を運用できるツール** に引き上げる。

### 内容

1. **Team Control Plane**
   - `team_create`
   - `team_delete`
   - leader/member metadata
   - persistent state

2. **Team Message Bus**
   - direct message
   - broadcast
   - structured control messages
   - shutdown / approval / escalation

3. **Team Task Bus**
   - task create/get/list/update/stop
   - owner
   - status transition
   - blocked reason
   - result pointer

4. **Team-aware lifecycle**
   - idle
   - running
   - waiting
   - closed
   - resume semantics

### Exit Criteria

- 3-agent 以上の継続タスクを team 単位で完走できる
- leader が task list を使って work assignment できる
- team state を跨いで resume しても破綻しない

### 優先度

**P0 本命**

---

## Stream C: Runtime Control Extensions

### 目的

実行戦略の切替コストを下げ、Claude 的な運用柔軟性を Codex 側に持ち込む。

### 内容

1. **model-callable worktree tools**
   - `enter_worktree`
   - `exit_worktree`

2. **model-callable plan mode transitions**
   - `enter_plan_mode`
   - `exit_plan_mode`
   - 既存 collaboration mode と整合

3. **structured final output**
   - coordinator が最終出力を組み立てやすい contract
   - verifier / worker の成果を正規化

### Exit Criteria

- 実装戦略を model から切り替えられる
- worktree 隔離を operator ではなく runtime が扱える
- team output の最終集約フォーマットが安定する

### 優先度

**P1**

---

## Stream D: Trigger Layer

### 目的

非同期・夜間・定期運用を可能にする。

### 内容

1. `cron_create`
2. `cron_delete`
3. `cron_list`
4. `remote_trigger`
5. `sleep`

### Exit Criteria

- 定期ジョブと一回限りジョブを扱える
- unattended run の最低限の運用が可能
- team/task runtime と接続できる

### 優先度

**P1**

---

## Stream E: Memory & Recovery

### 目的

セッション跨ぎの再説明コストと、失敗からの立て直しコストを下げる。

### 内容

1. **Recovery Playbook**
   - 1回目失敗: same agent retry
   - 2回目失敗: independent verification
   - 2回失敗で escalate

2. **failure taxonomy**
   - permission
   - sandbox
   - stale context
   - hidden dependency
   - flaky test
   - bad delegation

3. **auto-memory 近似実装**
   - Stop hook 起点
   - fail-open
   - scope 限定
   - 明示的に experimental 扱い

### Exit Criteria

- self_recovery_rate が改善する
- 再開時の再説明コストが下がる
- memory 失敗が主処理を壊さない

### 優先度

**P2**

---

## Stream F: Eval, Rollout, Compliance

### 目的

改善を数値で判定し、危険な機能を段階的に有効化する。

### 指標

- `task_success_rate`
- `first_valid_output_time`
- `self_recovery_rate`
- `rework_cycles_per_task`
- `verification_pass_rate`
- `team_completion_rate`

### ロールアウト

1. local PoC
2. canary repo
3. default-on candidate
4. rollback rehearsal

### ガードレール

- hooks 機能は feature flag 前提
- write 並列は禁止、worktree 使用時のみ例外化
- Claude 実装の直移植はしない
- ライセンス境界未確認のコードは取り込まない

### 優先度

**全期間並走**

---

## 5) 実装順序

1. **Stream A**
2. **Stream B**
3. **Stream F を並走開始**
4. **Stream C**
5. **Stream D**
6. **Stream E**

この順番の理由:

- A は最速で効く
- B が Claude 差分の本丸
- C/D は B がないと活きにくい
- E は重要だが、先にやると experimental 依存が強くなる

---

## 6) 直近2週間の具体タスク

1. `AGENTS.md` Mini を作る
2. `coordinator.toml` と `verifier.toml` を作る
3. baseline eval を 10 件固定する
4. Team Runtime RFC を 3 本書く
   - `docs/rfc-agent-team-control-plane.md`
   - `docs/rfc-team-message-bus.md`
   - `docs/rfc-team-task-bus.md`
5. Team Runtime の state model を決める
   - team
   - member
   - task
   - message
6. recovery playbook の運用版を先に文書化する

---

## 7) 最終判断

**あなたの ver1 は「どう運用すると強いか」を押さえていて良い。**  
**既存 ver2 は「何を作ると Claude 差分を埋められるか」を押さえていて良い。**

最高版は、

- ver1 の **思考規律 / coordinator / verifier / recovery**
- ver2 の **Team Runtime 中心の優先順位**
- 差分調査で判明した **subagent は既にあるので、team/task/trigger を主戦場にする**

この3つを合わせたものです。
