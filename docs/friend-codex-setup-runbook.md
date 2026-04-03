# Friend Codex Setup Runbook

_Updated: 2026-04-03_

## 目的

この repo を友人環境に配布し、`~/.codex` 配下へ必要物を再現可能に導入する。  
既存の個人セットアップとは共存させ、破壊的上書きは行わない。

## 0. 前提

- friend がこの repo を clone 済み
- `python3` が利用可能
- Codex Home は通常 `~/.codex`（別パスでも可）

## 1. 最短導入手順

```bash
cd "<friendのclone先>/Codex_Aries"

./scripts/bootstrap-friend-codex.sh \
  --codex-home "$HOME/.codex" \
  --profile "amax-friend" \
  --repo-root "$(pwd)" \
  --store-root "$HOME/.codex/runtime-spike-amax-friend"
```

このコマンドで profile 分離された以下が生成される:
- `~/.codex/runtime-adapter-amax-friend/`
- `~/.codex/skills/runtime-adapter-ops-amax-friend/`
- `~/.codex/agents/coordinator-amax-friend.toml`
- `~/.codex/agents/verifier-amax-friend.toml`

## 2. 初回確認手順（最小）

```bash
source "$HOME/.codex/runtime-adapter-amax-friend/runtime-adapter-amax-friend.env"
"$HOME/.codex/runtime-adapter-amax-friend/codex-runtime-amax-friend" ops
```

`ops` が成功すれば、Codex セッションから wrapper を呼べる状態。

追加の疎通確認（任意）:
```bash
"$HOME/.codex/runtime-adapter-amax-friend/codex-runtime-amax-friend" team-create "friend-alpha" "friend-alpha-1"
"$HOME/.codex/runtime-adapter-amax-friend/codex-runtime-amax-friend" reconcile-all
```

## 3. 友人環境向けに変える箇所

- profile 名: `--profile`
- runtime state 保存先: `--store-root`
- clone 先パス: `--repo-root`
- Python 実行コマンド: `--python-cmd`

変更値は以下へ反映される:
- `runtime-adapter-<profile>.env`
- `codex-runtime-<profile>`

## 4. 既存セットアップと共存するためのルール

- 配布用 wrapper は `codex-runtime-<profile>` を使う（既存 `codex-runtime` を使わない）
- 配布用 agent は `coordinator-<profile>` / `verifier-<profile>` を使う
- 既存 `~/.codex/runtime-adapter/` や既存 skill/agent ファイルは変更しない

## 5. トラブル時の切り分け

1. adapter パス確認:
   - `echo "$AMAX_RUNTIME_ADAPTER_PATH"`
2. wrapper 参照確認:
   - `echo "$AMAX_RUNTIME_WRAPPER_PATH"`
3. store root 確認:
   - `echo "$AMAX_RUNTIME_STORE_ROOT"`
4. manifest 確認:
   - `cat "$HOME/.codex/runtime-adapter-<profile>/install-manifest.json"`

## 6. Distribution Synchronization Note

`~/.codex` に wrapper、slash command、skill、agent を直接追加した場合は、友人配布前に `bootstrap-friend-codex.sh` と関連 runbook へ同じ導線を反映する。`~/.codex` の手元追加だけで共有完了と扱わない。
