# Slash Command Layer (`/agent_team` Complete)

- Version: 0.3
- Date: 2026-04-04
- Status: Step 1 + Step 2 implemented

## 1. Goal

`/agent_team` を slash 入口として追加し、既存 `poc/agent_team_command.py` へ委譲する。  
preview-first を維持しつつ、`--apply` 明示時のみ apply delegate を実行する。

## 2. Fixed Slash/CLI Contract (Implemented)

preview（デフォルト）:

```bash
python3 /Users/kondogenki/Codex_Aries/poc/slash_command_adapter.py \
  /agent_team \
  --input-file /tmp/agent-team.json
```

apply（明示指定時のみ）:

```bash
python3 /Users/kondogenki/Codex_Aries/poc/slash_command_adapter.py \
  /agent_team \
  --apply \
  --input-file /tmp/agent-team.json \
  --store-root /tmp/agent-team-runtime
```

固定ルール（実装済み）:
- `--apply` がない限り常に `preview`
- slash layer は state を持たない
- slash layer は parse -> validate -> route -> render だけ

## 3. Responsibility Split

- `poc/slash_command_adapter.py`
  - CLI parse
  - payload load
  - stage envelope render
- `src/slash_commands/router.py`
  - slash name parse
  - mode resolve (`preview` default)
  - request build / route
- `src/slash_commands/commands/agent_team.py`
  - payload shape の最小検証
  - `agent_team_command.py` subprocess 委譲
  - delegate result の透過返却
- `poc/agent_team_command.py`
  - team 定義、plan/apply、runtime 呼び出しの本体責務

## 4. Codex 実接続 (`~/.codex`)

以下を追加し、Codex 側から `/agent_team` を呼べる状態にした。

- `/Users/kondogenki/.codex/commands/agent_team.md`
  - slash command 定義（preview default / apply explicit）
- `/Users/kondogenki/.codex/runtime-adapter/codex-agent-team`
  - 実行ラッパー（`poc/slash_command_adapter.py` へ委譲）

非破壊方針:
- 既存 `runtime-adapter/` 内に新規ファイルを追加するだけ
- 既存ファイルを上書きしない
- 既存 daily-driver / friend bootstrap 導線に影響を与えない

## 5. Output Envelope (Adapter)

```json
{
  "mode": "preview",
  "command_name": "agent_team",
  "ok": true,
  "stages": {
    "parse": {},
    "validate": {},
    "route": {},
    "render": {}
  },
  "result": {
    "delegate_output": {}
  },
  "error": null
}
```

## 6. Stateless / Stateful Boundary

stateless（slash layer）:
- `poc/slash_command_adapter.py`
- `src/slash_commands/*`
- `~/.codex/commands/agent_team.md`
- `~/.codex/runtime-adapter/codex-agent-team`

stateful（runtime kernel）:
- `poc/agent_team_command.py` apply
- `poc/codex_runtime_adapter.py`
- `--store-root` 配下の control/message/task stores

## 7. Guardrails

- slash layer は runtime state を保存しない
- slash layer は team/task/message ロジックを再実装しない
- preset 解決ロジックは `agent_team_command.py` に委譲
- daily-driver / Phase 19 系の既存フローを変更しない

## 8. Next Step

- `~/.codex/commands` を friend bootstrap に取り込み、他環境でも同じ導線を再現する
- `agent_team` 以外の slash command を同じ adapter 契約で追加する
