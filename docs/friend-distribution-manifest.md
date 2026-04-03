# Friend Distribution Manifest

_Updated: 2026-04-03_

## 1) 配布対象の切り分け

### Repo に残すもの（cloneで取得）
- runtime/kernel 実装:
  - `poc/codex_runtime_adapter.py`
  - `src/team_runtime/`
  - `poc/*.py`（helper / orchestrator 群）
- custom agent 原本:
  - `coordinator.toml`
  - `verifier.toml`
- verifier 契約:
  - `verifier-contract.md`
- 配布用セットアップ:
  - `scripts/bootstrap-friend-codex.sh`
  - `docs/friend-codex-setup-runbook.md`
  - `docs/friend-distribution-manifest.md`

### `~/.codex` に配置するもの（bootstrapで生成）
- runtime profile dir:
  - `~/.codex/runtime-adapter-<profile>/runtime-adapter-<profile>.env`
  - `~/.codex/runtime-adapter-<profile>/codex-runtime-<profile>`
  - `~/.codex/runtime-adapter-<profile>/verifier-contract.md`
  - `~/.codex/runtime-adapter-<profile>/install-manifest.json`
- skill:
  - `~/.codex/skills/runtime-adapter-ops-<profile>/SKILL.md`
- agents（既存と衝突しない別名）:
  - `~/.codex/agents/coordinator-<profile>.toml`
  - `~/.codex/agents/verifier-<profile>.toml`

## 2) friend 環境で可変にする項目

- `--codex-home`: Codex Home（通常 `~/.codex`）
- `--profile`: 共存用サフィックス（例: `amax-friend`）
- `--repo-root`: friend の clone 先絶対パス
- `--store-root`: runtime state 保存先
- `--python-cmd`: Python 実行コマンド

## 3) path 依存の扱い

- repo 絶対パス依存は、bootstrap 実行時に `runtime-adapter-<profile>.env` へ固定値として書き出す。
- helper/orchestrator 参照先は env で上書きする:
  - `CODEX_RUNTIME_HELPER_RUNTIME_CMD`
  - `CODEX_ORCH_*_SCRIPT`
- 既存運用への影響防止:
  - 既存 `~/.codex/runtime-adapter/` や既存 agent 名は変更しない
  - 配布用は `<profile>` 付き別 wrapper/別 env/別 agent 名のみ使う

## 4) 非破壊ルール

- bootstrap はデフォルトで **既存ファイルを上書きしない**。
- 既存ファイルがある場合は `skip` する。
- 明示的に更新したい場合のみ `--force` を使う。
