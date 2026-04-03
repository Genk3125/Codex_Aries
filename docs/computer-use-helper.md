# Computer-use Helper (Phase 12 PoC)

`poc/computer_use_helper.py` は browser evidence collector。  
判定（PASS/PARTIAL/FAIL）は行わず、verifier に渡す材料だけを作る。

## Scope (frozen)
- URL を開いて screenshot を取得
- ページテキストを抽出
- orchestrator から任意で 1 回呼び出し

## Non-goals
- form 入力/送信
- 複雑クリック操作
- verdict 判定ロジック

## 実行例

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/computer_use_helper.py \
  --url "http://127.0.0.1:8000" \
  --operation both \
  --output-dir "/Users/kondogenki/AI Agent Maximizer/.runtime/computer-use-evidence" \
  --output-json "/tmp/computer-use.json"
```

## スクリーンショット戦略
- 第一選択: `npx playwright screenshot`（Chromium）
- fallback: HTML から要約テキストを描画した PNG を生成（evidence を欠落させない）

## orchestrator 接続
- `poc/one_shot_orchestrator.py` に以下を追加:
  - `--computer-use-url`
  - `--computer-use-operation`
  - `--computer-use-timeout-sec`
  - `--computer-use-timeout-ms`
  - `--computer-use-output-dir`
- 実行時、`results.computer_use_helper` に結果を記録。
- `verifier_gate_helper` / `chain_helper` へ `--computer-use-evidence-json` を透過。
- verifier 実行時は env `VERIFIER_GATE_COMPUTER_USE_EVIDENCE_JSON` で証跡パスが渡る。

## MCP 連携メモ
- Codex セッションで Playwright MCP が利用可能な場合は、MCP 取得画像を `--screenshot-path` で注入可能。
- helper 側は証跡 JSON の整形に集中し、MCP 依存を強制しない。

