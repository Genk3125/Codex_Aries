# Claude Code Slash Command Inventory Report

- Date: 2026-04-04
- Target snapshot: `/Users/kondogenki/Downloads/claude-code-main`
- Output location: `/Users/kondogenki/Codex_Aries/docs/claude-code-slash-command-inventory-report.md`

## 1. Purpose

This report inventories the slash command surface visible in the `claude-code-main` snapshot and separates it into:

- public built-in commands
- aliases
- bundled skill commands
- feature-gated or internal-only commands
- dynamic command sources that cannot be fully enumerated statically

The immediate purpose is to support comparison work for `Codex_Aries` slash command planning without conflating Claude Code public UX with internal-only or environment-dependent command sources.

## 2. Scope

Included:

- static command registry defined in `/Users/kondogenki/Downloads/claude-code-main/src/commands.ts`
- command definitions under `/Users/kondogenki/Downloads/claude-code-main/src/commands`
- bundled skill registration under `/Users/kondogenki/Downloads/claude-code-main/src/skills/bundled`

Excluded:

- runtime-discovered plugin commands
- user/project-local skills
- plugin skills loaded from external markdown
- environment-specific workflow-generated commands
- command names whose implementation files are absent from this snapshot and cannot be confirmed beyond import-path inference

## 3. Method

The inventory was produced by read-only inspection of:

- `/Users/kondogenki/Downloads/claude-code-main/src/commands.ts`
- `/Users/kondogenki/Downloads/claude-code-main/src/types/command.ts`
- `/Users/kondogenki/Downloads/claude-code-main/src/utils/plugins/loadPluginCommands.ts`
- `/Users/kondogenki/Downloads/claude-code-main/src/skills/loadSkillsDir.ts`
- `/Users/kondogenki/Downloads/claude-code-main/src/skills/bundled/index.ts`
- command and skill definition files under `src/commands` and `src/skills/bundled`

Static extraction was preferred over inference. Where a slash name could not be confirmed from a concrete `name:` field, it is labeled as inferred.

## 4. Public Built-in Commands

The following commands are directly registered in `COMMANDS()` in `/Users/kondogenki/Downloads/claude-code-main/src/commands.ts#L258`.

- `/add-dir`
- `/advisor`
- `/agents`
- `/branch`
- `/btw`
- `/chrome`
- `/clear`
- `/color`
- `/compact`
- `/config`
- `/context`
- `/copy`
- `/cost`
- `/desktop`
- `/diff`
- `/doctor`
- `/effort`
- `/exit`
- `/export`
- `/extra-usage`
- `/fast`
- `/feedback`
- `/files`
- `/heapdump`
- `/help`
- `/hooks`
- `/ide`
- `/init`
- `/insights`
- `/install-github-app`
- `/install-slack-app`
- `/keybindings`
- `/login`
- `/logout`
- `/mcp`
- `/memory`
- `/mobile`
- `/model`
- `/output-style`
- `/passes`
- `/permissions`
- `/plan`
- `/plugin`
- `/pr-comments`
- `/privacy-settings`
- `/rate-limit-options`
- `/release-notes`
- `/reload-plugins`
- `/remote-env`
- `/rename`
- `/resume`
- `/review`
- `/ultrareview`
- `/rewind`
- `/sandbox`
- `/security-review`
- `/session`
- `/skills`
- `/stats`
- `/status`
- `/statusline`
- `/stickers`
- `/tag`
- `/tasks`
- `/terminal-setup`
- `/theme`
- `/think-back`
- `/thinkback-play`
- `/upgrade`
- `/usage`
- `/vim`

## 5. Public Aliases

Aliases confirmed from command definition files:

- `/allowed-tools` -> `/permissions`
- `/android` -> `/mobile`
- `/app` -> `/desktop`
- `/bashes` -> `/tasks`
- `/bug` -> `/feedback`
- `/checkpoint` -> `/rewind`
- `/continue` -> `/resume`
- `/ios` -> `/mobile`
- `/marketplace` -> `/plugin`
- `/new` -> `/clear`
- `/plugins` -> `/plugin`
- `/quit` -> `/exit`
- `/remote` -> `/session`
- `/reset` -> `/clear`
- `/settings` -> `/config`

Conditional alias:

- `/fork` -> `/branch` only when standalone `/fork` is not present. This behavior is defined in `/Users/kondogenki/Downloads/claude-code-main/src/commands/branch/index.ts#L1`.

## 6. Bundled Skill Commands

Bundled skills are registered at startup via `/Users/kondogenki/Downloads/claude-code-main/src/skills/bundled/index.ts#L1` and are also part of the slash command surface.

Always registered in this snapshot:

- `/batch`
- `/debug`
- `/lorem-ipsum`
- `/remember`
- `/simplify`
- `/skillify`
- `/stuck`
- `/update-config`
- `/verify`

Conditionally registered:

- `/claude-api`
- `/claude-in-chrome`
- `/loop`
- `/schedule`

Hidden bundled skill:

- `/keybindings-help`

`/keybindings-help` is registered but marked `userInvocable: false`, so it should not be treated as normal public slash UX.

## 7. Feature-Gated Public Commands

These commands are clearly named in source, but only included when feature flags are enabled.

Confirmed by direct `name:` definition:

- `/brief`
- `/remote-control`
- `/voice`
- `/web-setup`

Confirmed alias:

- `/rc` -> `/remote-control`

Referenced in the registry but not directly confirmable from this snapshot because the implementation files are not present here:

- `/assistant`
- `/buddy`
- standalone `/fork`
- `/peers`
- `/proactive`
- `/torch`
- `/workflows`

These should be treated as likely real commands, but not as fully confirmed from this repository snapshot alone.

## 8. Internal-Only Commands

`INTERNAL_ONLY_COMMANDS` is defined in `/Users/kondogenki/Downloads/claude-code-main/src/commands.ts#L224`.

Directly confirmed by concrete `name:` definitions:

- `/bridge-kick`
- `/commit`
- `/commit-push-pr`
- `/init-verifiers`
- `/ultraplan`
- `/version`

Present only as stubbed exports or import-path references in this snapshot, so names below are inferred from path/import identity rather than a confirmed `name:` field:

- `/agents-platform`
- `/ant-trace`
- `/autofix-pr`
- `/backfill-sessions`
- `/break-cache`
- `/bughunter`
- `/ctx_viz`
- `/debug-tool-call`
- `/env`
- `/good-claude`
- `/issue`
- `/mock-limits`
- `/oauth-refresh`
- `/onboarding`
- `/perf-issue`
- `/reset-limits`
- `/share`
- `/summary`
- `/teleport`
- `/subscribe-pr`
- `/force-snip`

Unresolved internal command:

- `remoteControlServerCommand` is included in the registry path, but the exact slash name is not recoverable from this snapshot.

## 9. Dynamic Slash Command Sources

The snapshot also supports slash commands that are not statically enumerable from the built-in registry alone.

Dynamic sources:

- skill directory commands loaded from settings/workspace
- plugin commands loaded from markdown
- plugin skills
- bundled skills already discussed above
- workflow-generated commands when workflow support is enabled
- MCP-provided skill commands
- dynamic skills discovered during file operations

Relevant loader entry points:

- `/Users/kondogenki/Downloads/claude-code-main/src/utils/plugins/loadPluginCommands.ts`
- `/Users/kondogenki/Downloads/claude-code-main/src/skills/loadSkillsDir.ts`
- `/Users/kondogenki/Downloads/claude-code-main/src/commands.ts#L353`

Important implication:

There is no single static list of "all slash commands" at runtime. The most accurate statement is that Claude Code has:

- a static built-in slash command set
- a static bundled-skill set
- a feature-gated set
- an internal-only set
- several dynamic extension sources

## 10. Key Findings

1. The public built-in slash surface is already broad and stable enough to use as a comparison baseline for `Codex_Aries`.
2. Bundled skills are operationally part of the slash surface and should be counted separately from built-in commands.
3. Internal-only commands are mixed into the same registry shape, so public-vs-internal separation must be explicit in migration or gap analysis.
4. Dynamic plugin and skill loading means a complete runtime inventory cannot be produced from static source alone.
5. The `/fork` name is special because it can appear either as a standalone command or as an alias of `/branch`, depending on feature flags.

## 11. Recommended Use For Codex_Aries

When using this report for `Codex_Aries` planning:

- compare first against the public built-in commands
- treat bundled skills as a second layer, not as core runtime commands
- do not model internal-only commands as initial parity targets
- do not assume dynamic plugin/skill commands belong in the first slash layer milestone
- treat `/branch` vs `/fork` behavior as a specific compatibility decision, not as a naming footnote

## 12. Verification Notes

This report was generated from read-only inspection only.

Commands used:

- `find`
- `rg`
- `sed`
- `nl`

No code execution from `claude-code-main` was performed, and no assumptions were made about feature flags beyond what is visible in source.
