# Codex Integration Caveats

_Updated: 2026-04-04_

## 目的

`Codex_Aries` を Codex Desktop / `~/.codex` に導入するときの実運用上の注意点をまとめる。  
特に「手元では動くが Codex から見えない」系のズレを防ぐ。

## 1. `~/.codex/commands` 直置きはこの build では正準ではない

- `~/.codex/commands/*.md` に置いても、Codex の slash command 一覧に出ない build がある。
- 今回の `/agent_team` はこのケースに当たった。
- この build では、slash command は **plugin 配下の `commands/`** から読まれる前提で扱う。

正準導線:
- plugin cache root: `~/.codex/plugins/cache/local/codex-aries/`
- command file: `~/.codex/plugins/cache/local/codex-aries/commands/agent_team.md`
- plugin manifest: `~/.codex/plugins/cache/local/codex-aries/.codex-plugin/plugin.json`
- plugin enable flag: `~/.codex/config.toml`
- optional marketplace metadata: `~/.agents/plugins/marketplace.json`

## 2. local plugin は 3 点セットで入れる

`/agent_team` のような Codex 側 slash command を見せたい場合、最低限これが必要。

1. plugin directory
2. marketplace entry
3. `config.toml` の plugin enable

どれか 1 つでも欠けると、Codex が command を発見しない可能性が高い。

## 3. Codex Desktop 再起動が必要

- plugin / command / config を追加した後は、Codex Desktop を完全に再起動する。
- 同じセッションのままでは slash command 一覧が更新されないことがある。

確認順:
1. Codex Desktop 再起動
2. 新しいスレッドを開く
3. `/` 一覧を開く
4. `/agent_team` を手入力でも試す

## 4. `~/.codex` に直接追加したものは bootstrap にも反映する

- 手元だけで `~/.codex` に wrapper / slash command / skill / agent を足しても、それだけでは共有完了ではない。
- friend 導入や再現性を考えるなら、同じ導線を `scripts/bootstrap-friend-codex.sh` と runbook に反映する。

## 5. profile と store root を混ぜない

- 自分用・friend 用・実験用で `store_root` を分ける。
- Phase 19 dogfood の runs/logs/store と、MVP 実験の store を混ぜない。
- `codex-runtime-<profile>` の profile 分離を維持する。

## 6. repo root ハードコードに注意

- repo 名変更や clone 先変更が入るので、実コードの default path は repo 相対か env override に寄せる。
- 過去ログの絶対パスは証跡なので残してよいが、**実コードの default path** は残さない。

## 7. slash layer は stateless のまま保つ

- slash layer の責務は `parse -> validate -> route -> render` に留める。
- runtime state や orchestration 判断は持たせない。
- `apply` は delegate 先が stateful であって、slash layer 自体は state を持たない。

## 8. plugin 導入時に見直す場所

- `~/.codex/plugins/cache/local/codex-aries/.codex-plugin/plugin.json`
- `~/.codex/plugins/cache/local/codex-aries/commands/*.md`
- `~/.agents/plugins/marketplace.json`
- `~/.codex/config.toml`
- `scripts/bootstrap-friend-codex.sh`
- `docs/friend-codex-setup-runbook.md`

## 9. 最低確認コマンド

```bash
rg -n 'codex-aries@local' ~/.codex/config.toml
cat ~/.agents/plugins/marketplace.json
cat ~/.codex/plugins/cache/local/codex-aries/.codex-plugin/plugin.json
cat ~/.codex/plugins/cache/local/codex-aries/commands/agent_team.md
```

## 10. 現時点の代表的な caveat

- `/agent_team` は wrapper 実装だけでは不十分で、Codex の command discovery に乗せる必要がある。
- `~/.codex/commands/agent_team.md` は保管用には使えても、この build では command 一覧の正準登録先ではない。
- local plugin は `~/.codex/plugins/cache/local/<plugin-name>/` に実体が必要。
- local plugin 化したら、Desktop 再起動前提で確認する。
