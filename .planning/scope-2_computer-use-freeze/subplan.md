# Subplan: computer-use scope freeze

## メタ情報

- **Phase ID**: `scope-2_computer-use-freeze`
- **Master Flow 位置**: Scope（Phase 11）
- **依存先**: なし（独立着手可能、Phase 8-9 と並走可）
- **主対象ファイル**: なし（調査 + 文書作成のみ）
- **アウトプット**: `.planning/scope-2_computer-use-freeze/cu-scope-decision.md`
- **推定ワークロード**: 1 セッション
- **ステータス**: `done`

---

## 1. 目的

computer-use（ブラウザ操作、UI 操作、スクリーンショット取得）の scope を凍結する。何を Phase 12 で実装し、何を後回しにするかを先に決定して、実装フェーズでのスコープクリープを防ぐ。

## 2. 背景・前提

- Codex には computer-use 相当の組み込み機能がない
- Claude Code / Tengu は Anthropic の computer-use API を使っている
- MCP 経由で Playwright / Puppeteer を接続する選択肢がある
- **懸念**: computer-use は巨大なスコープになりうる → 先に freeze してから実装に入る

## 3. 具体的な作業ステップ

### Step 1: computer-use のユースケース列挙

日常運用で実際に必要な操作:
1. **ブラウザで URL を開いてスクリーンショット取得** → UI 回帰テスト
2. **フォームに入力して送信** → E2E テスト
3. **ページ内テキストを読み取って判定** → verifier 連携
4. **ファイルマネージャ操作** → 不要（CLI で十分）
5. **デスクトップ UI 操作** → 不要

### Step 2: MCP vs API vs 外部ツール の選定

| 方式 | Pros | Cons |
|------|------|------|
| MCP (Playwright) | Codex native 連携、JSON-RPC | セットアップが重い |
| Puppeteer direct | 軽量、npm 一発 | Codex からの呼び出しが間接的 |
| Anthropic computer-use API | 最も高機能 | Codex からは使えない（Claude 専用） |
| Selenium | 安定 | 古い、重い |

### Step 3: cu-scope-decision.md を作成

```markdown
## Phase 12 で実装するもの
- URL を開いてスクリーンショット取得
- ページ内テキスト抽出
- MCP 経由の Playwright 接続

## Phase 12 で実装しないもの
- フォーム入力・送信
- マウスクリック操作
- デスクトップ UI 操作

## 技術選定
- Playwright MCP server を採用
- 理由: ...
```

## 4. 完了判定（Exit Criteria）

- [x] ユースケースが列挙され、それぞれに In/Out 判定がついている
- [x] 技術選定（MCP / direct / API）が決定し、理由が文書化されている
- [x] Phase 12 の実装 scope が cu-scope-decision.md に凍結されている
- [x] scope freeze 後の変更は「明示的な unfreeze 判断」を必要とする

## 5. リスク・注意

- scope を広げると Phase 12 が爆発する → 最小 useful set に絞る
- MCP server の安定性はまだ実験レベル → PoC で先に安定性を確認してから凍結

## 6. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| 2026-04-03 | computer-use ユースケースを洗い出し、日常運用に必要な最小セットを判定 | URL screenshot / text extraction を In、複雑操作を Out と確定 | 技術選定を固定 |
| 2026-04-03 | `.planning/scope-2_computer-use-freeze/cu-scope-decision.md` を作成 | MCP + helper fallback の方針、Phase 12 実装範囲を freeze | Phase 12 実装へ |
