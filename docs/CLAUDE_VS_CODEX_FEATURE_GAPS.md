# Claude Code vs Codex CLI: Feature Gap Extraction (Planning)

_As of 2026-04-02_

比較対象:
- Claude source: `/Users/kondogenki/Downloads/claude-code-main`
- Codex source: `/tmp/codex-main` (`openai/codex`)

## 0) 先に重要な訂正

- **Sub agents 自体は Codex に既にある**（差分ではない）。
  - `spawn_agent`, `send_message`, `assign_task`, `wait_agent`, `close_agent`, `list_agents`
    - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:380`
    - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:385`
    - `/tmp/codex-main/codex-rs/tools/src/agent_tool.rs:29`
    - `/tmp/codex-main/codex-rs/tools/src/agent_tool.rs:139`

## 1) Claude にはあり、Codex には見当たらない（高優先）

### A. Agent Team のライフサイクル管理（team create/delete）
- Claude は team 専用ツールを持ち、team state を永続化して cleanup まで実装。
  - team tools registry:
    - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:63`
    - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:67`
  - team作成・team context/cleanup:
    - `/Users/kondogenki/Downloads/claude-code-main/src/tools/TeamCreateTool/TeamCreateTool.ts:74`
    - `/Users/kondogenki/Downloads/claude-code-main/src/tools/TeamCreateTool/TeamCreateTool.ts:177`
    - `/Users/kondogenki/Downloads/claude-code-main/src/tools/TeamDeleteTool/TeamDeleteTool.ts:32`
    - `/Users/kondogenki/Downloads/claude-code-main/src/tools/TeamDeleteTool/TeamDeleteTool.ts:101`
- Codex の multi-agent registry には team create/delete 相当がない。
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:343`
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:385`

### B. Team向け mailbox + 構造化メッセージ（broadcast, shutdown, plan approval）
- Claude `SendMessageTool` は `"*"` broadcast、`shutdown_request/response`、`plan_approval_response` を持つ。
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools/SendMessageTool/SendMessageTool.ts:46`
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools/SendMessageTool/SendMessageTool.ts:69`
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools/SendMessageTool/SendMessageTool.ts:191`
- Codex `send_message` は target+text の最小仕様。
  - `/tmp/codex-main/codex-rs/tools/src/agent_tool.rs:120`
  - `/tmp/codex-main/codex-rs/tools/src/agent_tool.rs:140`

### C. Team内タスク運用ツール（TaskCreate/Get/List/Update + teammate許可）
- Claude は teammate向け task CRUD と cron を allowlist で明示管理。
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:82`
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:85`
  - `/Users/kondogenki/Downloads/claude-code-main/src/constants/tools.ts:77`
  - `/Users/kondogenki/Downloads/claude-code-main/src/constants/tools.ts:85`
- Codex は `assign_task`（agentに仕事を投げる）を持つが、Claude型の task list CRUD tool 群は見当たらない。
  - `/tmp/codex-main/codex-rs/tools/src/agent_tool.rs:153`
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:382`

### D. モデル呼び出し可能な Worktree 切替（Enter/ExitWorktree）
- Claude はセッション中に worktree へ入る/戻る専用ツールを提供。
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:79`
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:80`
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools/EnterWorktreeTool/EnterWorktreeTool.ts:52`
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools/ExitWorktreeTool/ExitWorktreeTool.ts:148`
- Codex 側 registry には `enter_worktree` / `exit_worktree` は存在しない。
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:140`
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:487`

### E. モデル呼び出し可能な Planモード遷移（Enter/ExitPlanMode）
- Claude は `EnterPlanModeTool` / `ExitPlanModeV2Tool` を持ち、承認フローも実装。
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:78`
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:57`
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools/EnterPlanModeTool/EnterPlanModeTool.ts:36`
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools/ExitPlanModeTool/ExitPlanModeV2Tool.ts:147`
- Codex は collaboration mode として Plan/Default を持つが、tool で enter/exit する方式ではない。
  - `/tmp/codex-main/codex-rs/protocol/src/config_types.rs:390`
  - `/tmp/codex-main/codex-rs/protocol/src/config_types.rs:412`
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:185`

### F. Scheduled/Proactive 実行（Sleep + Cron + Remote Trigger）
- Claude は `SleepTool`, `CronCreate/Delete/List`, `RemoteTriggerTool` を tool pool に持つ。
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:25`
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:29`
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:36`
- Codex registry にはこれら相当ツールがない（`wait_agent` は「別agent通知待ち」で scheduler ではない）。
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:365`
  - `/tmp/codex-main/codex-rs/tools/src/agent_tool.rs:231`

### G. Coordinator用 `SyntheticOutput` 契約
- Claude は coordinator allowlist に `SYNTHETIC_OUTPUT_TOOL_NAME` を含める。
  - `/Users/kondogenki/Downloads/claude-code-main/src/tools.ts:97`
  - `/Users/kondogenki/Downloads/claude-code-main/src/constants/tools.ts:107`
- Codex registry には synthetic-output相当の専用toolは見当たらない。
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:343`

## 2) 差分ではない（Codex に既にある）

- Sub agents 基盤:
  - `/tmp/codex-main/codex-rs/tools/src/agent_tool.rs:22`
  - `/tmp/codex-main/codex-rs/tools/src/agent_tool.rs:243`
- MCP resources:
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:164`
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:182`
- Tool discovery (`tool_search`):
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:230`
  - `/tmp/codex-main/codex-rs/tools/src/tool_registry_plan.rs:246`

## 3) Codex CLI maximize 向け優先度（実装前プラン）

### P0（最優先）
1. **Agent Team Control Plane**
   - `team_create`, `team_delete`, team metadata/persistence, leader/member role
2. **Team Message Bus**
   - broadcast/structured control messages（shutdown, approval）
3. **Team Task Bus**
   - task CRUD + list/state model（agent orchestrationの共通状態）

### P1
1. **Worktree Runtime Tools**
   - `enter_worktree`, `exit_worktree` をモデルから呼べる形で追加
2. **Plan Mode Transition Tools**
   - `enter_plan_mode`, `exit_plan_mode`（UI modeとの整合を取りつつ）
3. **Scheduled Trigger Layer**
   - `cron_*`, `remote_trigger`, `sleep`

### P2
1. **Synthetic Output Contract**
2. **Workflow Script/Automation Integration**

## 4) これで何が可能になるか

- 「subagentを複数動かす」から一段進んで、**teamとして継続運用**できる。
- チーム内の依頼/承認/停止が **プロトコル化** され、長時間タスクが安定する。
- タスクとスケジュールを持てるため、**非同期オーケストレーション** が可能になる。
- worktree・plan mode をモデルから制御でき、**実行戦略の切替コスト** を下げられる。
