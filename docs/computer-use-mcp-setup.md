# Playwright MCP Setup (Phase 12 PoC)

## 目的
- Codex セッションから Playwright MCP を呼び、browser evidence を取得できる状態にする。

## 最小セットアップ例

`~/.codex/config.toml`（または利用中設定）に Playwright MCP を登録:

```toml
[mcp_servers.playwright]
command = "npx"
args = ["-y", "@playwright/mcp@latest"]
```

## 接続確認（Codex セッション）
1. MCP ツールで URL を開く
2. snapshot/screenshot を取得する
3. 取得した画像パスを `computer_use_helper.py --screenshot-path` に渡して evidence JSON を生成する

## 方針
- MCP は「実ブラウザ操作の入口」。
- `poc/computer_use_helper.py` は「証跡の標準化と orchestrator 接続」。
- verdict は verifier 契約に残す（helper 側で再実装しない）。

