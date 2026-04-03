# Subplan: computer-use MCP PoC

## メタ情報

- **Phase ID**: `build-1_computer-use-mcp-poc`
- **Master Flow 位置**: Build（Phase 12）
- **依存先**: Phase 11（cu-scope-decision.md が凍結済みであること）
- **主対象ファイル**: 新規 `poc/computer_use_helper.py`, MCP server 設定
- **推定ワークロード**: 2-3 セッション
- **ステータス**: `not_started`

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
# 出力: screenshot パス or 抽出テキスト
# MCP 経由で Playwright を呼ぶ
```

### Step 3: orchestrator パイプラインへの接続

- verifier_gate_helper から computer_use_helper を呼べるようにする
- 具体的には: verifier-cmd として computer_use_helper を指定し、UI の状態を検証に使う

### Step 4: E2E テスト

- テスト対象: ローカルの dev server 画面
- スクリーンショット取得 → ファイル保存 → 正常性確認

## 4. 完了判定（Exit Criteria）

- [ ] MCP Playwright server が Codex から接続可能
- [ ] computer_use_helper が URL → screenshot を取得できる
- [ ] orchestrator から verifier-cmd 経由で computer_use_helper が呼べる
- [ ] ローカルの dev server でスクリーンショットベースの検証が成功

## 5. リスク・注意

- MCP server のバージョン非互換 → 特定バージョンを pin する
- Headless ブラウザのメモリ使用量 → タイムアウトとメモリ制限を設定
- scope freeze で決めた範囲外の機能追加は Phase 12 ではやらない

## 6. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
