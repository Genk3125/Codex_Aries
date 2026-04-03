# Agent Team Command (Step 2)

- Version: 0.2
- Date: 2026-04-04
- Target: `poc/agent_team_command.py`
- Scope: `/agent_team` の command surface 固定（plan + thin apply）

## 1. このステップで固定するもの

- `plan` は Step 1 と同じく schema 固定。
- `apply` は既存 runtime adapter を順に呼ぶ薄い実行面を追加。
- `model_preset` / `reasoning_preset` は preset 名として保持し、実 model 名へは解決しない。
- slash 配置はまだ実装しない。

## 2. 入力 schema（固定）

`--input-json` か `--input-file` のどちらか一方で与える。

```json
{
  "team_name": "example-team",
  "objective": "optional",
  "main_agent": {
    "agent_id": "main-coordinator",
    "role": "brain/coordinator",
    "model_preset": "quality",
    "reasoning_preset": "high",
    "initial_prompt": "optional"
  },
  "sub_agents": [
    {
      "agent_id": "worker-1",
      "role": "delegated worker",
      "model_preset": "fast",
      "reasoning_preset": "medium",
      "initial_prompt": "optional"
    }
  ],
  "initial_task": {
    "title": "optional",
    "state": "ready",
    "owner": "main",
    "blocked_reason": "optional",
    "result_reference": "optional"
  },
  "initial_messages": [
    {
      "from_member_id": "main-coordinator",
      "to_member_id": "worker-1",
      "text": "optional custom kickoff message"
    }
  ]
}
```

バリデーション:
- `main_agent` は必須 1
- `sub_agents` は配列（空可）
- `agent_id` は team 内で一意
- `model_preset` / `reasoning_preset` は preset catalog に存在する値

## 3. plan 出力 schema（固定）

`plan` 成功時は以下のトップレベルキーを返す。

- `team_definition`
- `runtime_ops_plan`
- `initial_task_template`
- `initial_message_templates`
- `command_templates`

メタ情報:
- `ok`
- `mode`
- `helper`
- `ts`
- `apply_extension`

## 4. apply 実行仕様（Step 2）

apply は runtime adapter を `op --name ...` で順に呼ぶだけ。

実行順（最小）:
1. `team_create`（常に実行）
2. `team_member_add`（sub agent 数ぶん）
3. `task_create`（`initial_task` が与えられた場合。`--force-task-create` / `--skip-task-create` で上書き可）
4. `send_message`（`initial_messages` が与えられた場合。`--force-send-messages` / `--skip-send-messages` で上書き可）

特性:
- 新しい orchestration core は作らない
- `session_helper` は使わず direct に runtime adapter を呼ぶ
- strict / fail-open は runtime adapter に透過する

## 5. apply_result の shape

`apply` 成功/失敗にかかわらず、`apply_result` を返す。

主キー:
- `executed`
- `mode` (`strict` / `fail-open`)
- `runtime_cmd`
- `store_root`
- `idempotency_prefix`
- `requested_operations`（task_create/send_message の実行有無）
- `resolved_ids`（`team_id` / `leader_agent_id` / `task_id`）
- `operation_counts`
- `steps`（各 runtime 呼び出しの command / exit_code / envelope / result / error）
- `stopped`（失敗で停止した場合のみ）

## 6. 主要 CLI 引数

- `--runtime-cmd`: runtime adapter 実行コマンド文字列
- `--store-root`: runtime adapter へ透過する store root
- `--idempotency-prefix`: `team_create`, `team_member_add`, `task_create`, `send_message` の key prefix
- `--strict`: runtime strict 透過 + apply 失敗時 non-zero
- `--force-task-create` / `--skip-task-create`
- `--force-send-messages` / `--skip-send-messages`

## 7. 将来の接続点

- slash 配置（`~/.codex/...`）は別ステップで接続する。
- 次の薄い接続は `/agent_team` の slash surface から本コマンドの `plan/apply` を呼ぶだけに留める。
