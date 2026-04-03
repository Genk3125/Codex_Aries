# Slash Command: `/agent_team` (Final Contract)

- Version: 0.3
- Date: 2026-04-04
- Status: preview + apply delegate connected

## 1. Purpose

`/agent_team` を slash 層から `agent_team_command.py` へ委譲する。  
デフォルトは preview、apply は明示指定時のみ。

## 2. Input Schema

slash adapter に渡す payload は `agent_team_command.py` と同じ。

```json
{
  "team_name": "demo-team",
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
      "role": "implementation",
      "model_preset": "fast",
      "reasoning_preset": "medium",
      "initial_prompt": "optional"
    }
  ],
  "initial_task": {
    "title": "optional",
    "state": "ready",
    "owner": "main"
  },
  "initial_messages": [
    {
      "to_member_id": "worker-1",
      "text": "optional"
    }
  ]
}
```

## 3. Mode Rules (Fixed)

- preview: default (`--apply` なし)
- apply: `--apply` 指定時のみ
- `--strict`, `--store-root`, `--runtime-cmd`, `--idempotency-prefix` は apply 時に委譲

## 4. Codex 側導線

実接続は以下の2ファイルで固定する。

- `/Users/kondogenki/.codex/commands/agent_team.md`
- `/Users/kondogenki/.codex/runtime-adapter/codex-agent-team`

`/agent_team` 発火時の実行面:

```bash
/Users/kondogenki/.codex/runtime-adapter/codex-agent-team /agent_team ...
```

## 5. Delegation Contract

slash layer が行うこと:
- command parse
- payload validate（最小）
- route
- render

slash layer が行わないこと:
- team/task/message/state ロジックの再実装
- model preset 解決
- runtime state 保存

`result.delegate_output` は `agent_team_command.py` の JSON をそのまま保持する。

## 6. Example

preview:

```bash
python3 /Users/kondogenki/Codex_Aries/poc/slash_command_adapter.py \
  /agent_team \
  --input-file /tmp/agent-team.json
```

apply:

```bash
python3 /Users/kondogenki/Codex_Aries/poc/slash_command_adapter.py \
  /agent_team \
  --apply \
  --input-file /tmp/agent-team.json \
  --store-root /tmp/agent-team-runtime \
  --idempotency-prefix slash-demo
```

## 7. Non-Goals

- command 自然言語解析
- 新 orchestration core
- daily-driver/Phase 19 フローへの介入
