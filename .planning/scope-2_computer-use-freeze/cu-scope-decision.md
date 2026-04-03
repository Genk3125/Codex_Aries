# Computer-use Scope Decision (Phase 11)

_Date: 2026-04-03_

## 1. Daily 運用ユースケース判定

| Use Case | 判定 | 理由 |
|---|---|---|
| URL を開いてスクリーンショット取得 | In | verifier 前段の evidence 収集に直結 |
| ページ内テキスト抽出 | In | 画面要素の存在確認を自動化できる |
| フォーム入力・送信 | Out (Phase 12) | スコープが急拡大しやすい。MVP外 |
| 任意クリック・ドラッグなど複雑操作 | Out (Phase 12) | 再現性/安定性のコストが高い |
| デスクトップUI操作 | Out | 本プロジェクトの runtime 核心ではない |
| ファイルマネージャ操作 | Out | CLI で代替可能 |

## 2. 技術選定

### 採用: Playwright ベース（MCP + CLI fallback）
- 第一選択: Codex の Playwright MCP（セッション内から直接ブラウザ証跡収集）
- 補助: `poc/computer_use_helper.py` で URL 入力→証跡 JSON を標準化
- fallback: MCP が使えない場面では helper の local extraction/screenshot fallback を許容

### 不採用
- Anthropic computer-use API: Codex 運用に直接接続できない
- Selenium: 今回の最小ユースケースには過剰

## 3. Phase 12 実装スコープ（freeze）

## In-Scope
- `computer_use_helper.py`（evidence collector）
  - `screenshot`
  - `extract_text`
  - `both`
- orchestrator から任意で computer-use step を 1 回呼ぶ接続点
- verifier に渡せる証跡 JSON（画像パス/抽出テキスト/メタデータ）

## Out-of-Scope
- multi-step browser workflow（複数ページ遷移やフォーム送信）
- 自動 verdict 判定（verifier ロジックの内包）
- UI 層
- trigger/worktree 連携

## 4. 運用ルール

- computer-use は verifier 本体ではなく **evidence collector** として扱う。
- 判定主体（PASS/PARTIAL/FAIL）は verifier 契約に残す。
- scope 変更は明示的 unfreeze でのみ許可する。

