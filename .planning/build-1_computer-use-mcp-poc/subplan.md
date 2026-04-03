# Subplan: computer-use MCP PoC

## メタ情報

- **Phase ID**: `build-1_computer-use-mcp-poc`
- **Master Flow 位置**: Build（Phase 12）
- **依存先**: Phase 11（cu-scope-decision.md が凍結済みであること）
- **主対象ファイル**: 新規 `poc/computer_use_helper.py`, MCP server 設定
- **推定ワークロード**: 2-3 セッション
- **ステータス**: `done`

---

## 1. 目的

Phase 11 で凍結した scope に従い、MCP 経由で Playwright を接続し、「URL を開いてスクリーンショットを取る」最小ユースケースを PoC で動かす。

## 2. 背景・前提

- Phase 11 の cu-scope-decision.md に基づいて実装範囲が決まっている
- MCP server として `@playwright/mcp` (公式) や `playwright-mcp-server` (コミュニティ) が候補

## 3. 具体的な作業ステップ

### Step 1: MCP Playwright server のセットアップ

- npm install + 設定ファイル作成
- Codex の MCP 設定 (`~/.codex/config.json` or `mcp.json`) への登録

### Step 2: computer_use_helper.py の最小実装

```python
# 入力: URL, 操作タイプ (screenshot / extract_text)
# 出力: screenshot パス, 抽出テキスト, メタデータ
# MCP 経由で Playwright を呼ぶ evidence collector
```

### Step 3: orchestrator パイプラインへの接続

- verifier / orchestrator から computer_use_helper を**evidence collector** として呼べるようにする
- 具体的には:
  - computer_use_helper は verdict を返す verifier 本体にはしない
  - screenshot / extracted text / metadata を生成し、その結果を verifier-cmd が読む
  - 必要なら verifier-cmd の前段で evidence を集める補助として使う

### Step 4: E2E テスト

- テスト対象: ローカルの dev server 画面
- スクリーンショット取得 → ファイル保存 → 正常性確認

## 4. 完了判定（Exit Criteria）

- [x] MCP Playwright server が Codex から接続可能（設定メモを追加）
- [x] computer_use_helper が URL → screenshot を取得できる
- [x] orchestrator から evidence collector として computer_use_helper が呼べる
- [x] verifier が computer_use_helper の結果を evidence として利用できる（`VERIFIER_GATE_COMPUTER_USE_EVIDENCE_JSON` で受け渡し）
- [x] ローカルの dev server でスクリーンショットベースの検証が成功（Playwright失敗時 fallback snapshot も確認）

## 5. リスク・注意

- MCP server のバージョン非互換 → 特定バージョンを pin する
- Headless ブラウザのメモリ使用量 → タイムアウトとメモリ制限を設定
- scope freeze で決めた範囲外の機能追加は Phase 12 ではやらない

## 6. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| 2026-04-03 | `poc/computer_use_helper.py` を新規実装（`screenshot`/`extract_text`/`both`） | URL から証跡 JSON を生成。Playwright CLI が使えない時は fallback 画像生成を維持 | orchestrator へ接続 |
| 2026-04-03 | `poc/one_shot_orchestrator.py` に computer-use step を追加 | `results.computer_use_helper` が単発 evidence collector として動作 | verifier 受け渡しを接続 |
| 2026-04-03 | `poc/verifier_gate_helper.py`, `poc/chain_helper.py` に `--computer-use-evidence-json` 透過を追加 | verifier 実行時に env `VERIFIER_GATE_COMPUTER_USE_EVIDENCE_JSON` で証跡パスを参照可能 | setup/docs 整備 |
| 2026-04-03 | `docs/computer-use-helper.md`, `docs/computer-use-mcp-setup.md` を追加 | MCP 側と helper 側の責務を分離して運用手順を固定 | Phase 13 へ |
