# Verifier Output Contract (v1.0)

## 目的
- `verifier` の検証結果を、毎回同じ形式・同じ判断基準で報告する。
- 「検証した/していない」を曖昧にせず、次アクションを即決できる状態にする。

## 判定定義（必須）
- **PASS**
  - 主要受け入れ条件を満たし、必要な検証コマンドが実行済みで、実出力に失敗がない。
- **PARTIAL**
  - 重大な失敗は確認していないが、未検証項目が残る（環境不足・権限不足・時間制約など）。
- **FAIL**
  - 受け入れ条件未達、テスト失敗、型エラー、明確な回帰、または高リスク不具合を確認。

## 出力フォーマット（必須）
以下の見出しを **この順序で** 出すこと。

### 1) Verification Result
- `PASS` / `PARTIAL` / `FAIL` のいずれか1つ
- 1文要約（なぜその判定か）

### 2) Executed Commands
- 実行した検証コマンドを列挙（未実行なら `None` と理由）
- 各コマンドは次を含む:
  - `command`
  - `cwd`
  - `exit_code`
  - `purpose`

### 3) Actual Output (Evidence)
- 実出力の要点を貼る（成功/失敗を判断した根拠）
- 失敗時はエラー行を優先して示す
- 「成功したはず」等の推測は禁止

### 4) Unverified Items
- 未検証項目を列挙（なければ `None`）
- 各項目は次を含む:
  - `item`
  - `reason`
  - `what_is_needed_to_verify`

### 5) Residual Risks
- 残留リスクを列挙（なければ `None`）
- 可能なら `severity`（High/Medium/Low）を付与

### 6) Next Actions
- 次の対応を優先順で列挙
- FAIL の場合は「修正→再検証」の具体手順を必ず含める

## 最低限ルール
- 検証していないことを「問題なし」と書かない。
- `PARTIAL` は「未検証ゼロ」の代替に使わない。
- `PASS` は実行コマンドと実出力の根拠がある場合のみ使う。

## テンプレート
````markdown
### Verification Result
PASS | PARTIAL | FAIL
<1文要約>

### Executed Commands
- command: `<...>`
  cwd: `<...>`
  exit_code: `<...>`
  purpose: `<...>`

### Actual Output (Evidence)
```text
<実出力の抜粋>
```

### Unverified Items
- item: `<...>`
  reason: `<...>`
  what_is_needed_to_verify: `<...>`

### Residual Risks
- `<risk>` (severity: High|Medium|Low)

### Next Actions
1. `<next action>`
2. `<next action>`
````

---

## verifier-cmd インターフェース規約

_Added: 2026-04-03_

### Exit Code 規約

| Exit Code | Verdict | 意味 |
|-----------|---------|------|
| `0` | PASS | 全チェック通過 |
| `1` | FAIL | 致命的な不一致を検出 |
| `2` | PARTIAL | 一部通過・一部未検証。未検証項目を Unverified Items に記録 |
| `3+` | UNKNOWN | verifier 自体の実行異常（クラッシュ、設定ミス等） |

### stdout 規約

- **1 行目**: `PASS` / `PARTIAL` / `FAIL`（verdict 判定に使用）
- **2 行目以降**: 自由形式（人間向け詳細。パースされない）

### stderr 規約

- デバッグ専用。verdict 判定には使用しない

### Verdict 分岐ルール

| Verdict | fail-open モード | strict モード |
|---------|-----------------|--------------|
| PASS | 続行 | 続行 |
| PARTIAL | **続行**（未検証項目を記録） | **停止**（全項目検証完了まで） |
| FAIL | **停止** | **停止** |
| UNKNOWN | **続行**（verifier 異常として記録） | **停止** |

### Decision Record

- PARTIAL を fail-open で「続行」とした理由: dogfood 実験で PARTIAL の多くがランタイム未接続による RECONCILE_FAILED であり、開発中は続行が実用的
- UNKNOWN を fail-open で「続行」とした理由: verifier 自体の不具合で本体を止めるべきではない

