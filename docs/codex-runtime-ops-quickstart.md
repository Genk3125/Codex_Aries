# Codex Runtime Ops Quickstart

- Version: 0.1
- Date: 2026-04-03
- Purpose: Codex セッション中に runtime adapter を迷わず実行するための最小運用メモ

## 1. 責務分離
- **repo 側**（仕様/実装）:
  - `/Users/kondogenki/AI Agent Maximizer/poc/codex_runtime_adapter.py`
  - `/Users/kondogenki/AI Agent Maximizer/poc/team_control_plane.py`
  - `/Users/kondogenki/AI Agent Maximizer/poc/team_message_bus.py`
  - `/Users/kondogenki/AI Agent Maximizer/poc/team_task_bus.py`
- **`~/.codex` 側**（実戦運用）:
  - `/Users/kondogenki/.codex/runtime-adapter/runtime-adapter.env`
  - `/Users/kondogenki/.codex/runtime-adapter/codex-runtime`
  - `/Users/kondogenki/.codex/skills/runtime-adapter-ops/SKILL.md`

## 2. セッション開始時（最小）
```bash
source /Users/kondogenki/.codex/runtime-adapter/runtime-adapter.env
alias codex-runtime='/Users/kondogenki/.codex/runtime-adapter/codex-runtime'
codex-runtime ops
```

## 3. 4操作の最短コマンド
```bash
codex-runtime team-create "alpha" "alpha-1"
codex-runtime send-message <team_id> <from_member_id> <to_member_id> "hello" "msg-1"
codex-runtime task-create <team_id> "first task" <owner_member_id> ready "task-1"
codex-runtime reconcile-all
```

## 4. fail-open / strict の使い分け
- fail-open（既定）:
  - 失敗時も JSON envelope を返し、終了コードは `0`
  - 対話運用中の継続性を優先
- strict:
  - `--strict` を先頭に付ける
  - 失敗時は non-zero で止めたい CI / スクリプト向け

例:
```bash
codex-runtime send-message <team_id> <from_member_id> <to_member_id> "hello"
codex-runtime --strict send-message <team_id> <from_member_id> <to_member_id> "hello"
```

## 5. 代表フロー例
1. `team-create` で team を作る
2. `send-message` で direct message を1回送る
3. `task-create` で初期 task を作る
4. `reconcile-all` で startup 相当の再整合を回す

期待値:
- 出力 JSON に `ok`, `fail_open`, `result`, `error` が揃う
- store root 配下に `control-plane/`, `message-bus/`, `task-bus/` が生成される
