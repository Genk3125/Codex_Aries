# Subplan: handoff Markdown を verifier-contract に整合させる

## メタ情報

- **Phase ID**: `now-2_handoff-verifier-alignment`
- **Master Flow 位置**: Now
- **依存先**: `now-1`（compact_state の出力フォーマットが handoff の入力情報を規定）
- **主対象ファイル**: `poc/handoff_helper.py`
- **副対象**: `verifier-contract.md`, `docs/handoff-helper.md`
- **推定ワークロード**: 1 セッション
- **ステータス**: `not_started`

---

## 1. 目的

handoff_helper の Markdown 出力を verifier-contract.md の 6 セクション構成に揃え、「handoff を貼ればそのまま verifier に渡せる」状態にする。

## 2. 背景・前提

- `verifier-contract.md` は 6 セクション構成が固定されている:
  1. Verification Result
  2. Executed Commands
  3. Actual Output (Evidence)
  4. Unverified Items
  5. Residual Risks
  6. Next Actions
- `handoff_helper.py` の `--output-markdown` は独自フォーマットで出力している
- 現状は handoff の Markdown を手動で verifier-contract テンプレートに転記している
- **課題**: 転記作業が手動介入点になっている

### 現在の handoff Markdown フォーマット（コード確認済み）
```
# Handoff Draft
## Verifier
- title: Verifier Read-Only Check Request
- summary: <1文要約>
## Coordinator
- title: Coordinator Escalation Packet
- summary: <1文要約>
```

### 必要な変換（verifier-contract 準拠）
```
現 handoff                → verifier-contract
──────────────────────────────────────────────
summary                   → ### Verification Result (1文要約)
failed_step (JSON にはある) → ### Verification Result (判定根拠)
executed_commands (JSON)   → ### Executed Commands
actual_outputs_summary (JSON) → ### Actual Output (Evidence)
(未実装)                  → ### Unverified Items
(未実装)                  → ### Residual Risks
suggested_next_action (JSON) → ### Next Actions
```
Note: JSON 出力には必要なフィールドが揃っているが、Markdown 出力はtitle+summary のみで大幅に不足している。

## 3. 具体的な作業ステップ

### Step 1: 現在の handoff Markdown 出力を取得し差分を確認

- **対象**: `poc/handoff_helper.py` の Markdown 生成部分
- **やること**:
  1. escalation ありケースで `--output-markdown` を実行
  2. 出力 Markdown のセクション見出しを列挙
  3. verifier-contract の 6 セクションとの差分表を作成
- **検証コマンド**:
  ```bash
  python3 poc/handoff_helper.py \
    --escalation-draft-json /tmp/runtime-preflight-max-retries/escalation-draft.json \
    --output-json /tmp/handoff-align/handoff.json \
    --output-markdown /tmp/handoff-align/handoff.md
  grep "^###" /tmp/handoff-align/handoff.md
  grep "^###" verifier-contract.md
  ```

### Step 2: handoff_helper に verifier-contract 準拠セクションを追加

- **対象**: `poc/handoff_helper.py`
- **やること**:
  - Markdown 生成部分を verifier-contract の 6 セクション順に出力するよう変更
  - 既存フィールドのマッピング:
    - `summary` + `failed_step` → `### Verification Result` (PARTIAL or FAIL + 1文要約)
    - `executed_commands` → `### Executed Commands` (command / cwd / exit_code / purpose)
    - `actual_outputs_summary` → `### Actual Output (Evidence)`
    - 新規追加: `### Unverified Items` — handoff 時点で未検証のものを列挙
    - 新規追加: `### Residual Risks` — escalation_draft から抽出
    - `suggested_next_action` → `### Next Actions`
  - `stop_reasons` は Verification Result の判定根拠として組み込む
- **検証**: 出力 Markdown が verifier-contract テンプレートと `diff` で構造一致

### Step 3: JSON → Markdown の双方向整合確認

- **対象**: `poc/handoff_helper.py`
- **やること**: `--output-json` と `--output-markdown` で同等の情報が出力されていることを確認
- **検証**:
  ```bash
  # JSON のキーと Markdown のセクション見出しが 1:1 対応
  jq 'keys' /tmp/handoff-align/handoff.json
  grep "^###" /tmp/handoff-align/handoff.md
  ```

### Step 4: verifier-contract テンプレートへの貼り付けテスト

- **対象**: handoff Markdown 出力
- **やること**: 出力をそのまま verifier-contract テンプレートに貼り、人が読んで判断可能か確認
- **検証**: 転記・整形なしで verifier に渡せること

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| `handoff_helper.py`: Markdown 生成関数 | 6 セクション全てが出力されているか | セクションヘッダの存在チェック → `stderr` |
| `handoff_helper.py`: Markdown 出力直前 | 行数が極端に少なくないか（< 10 行は異常） | `print(f"[DEBUG][handoff] lines={md.count(newline)}", file=sys.stderr)` |
| `handoff_helper.py`: escalation_draft 読み込み直後 | Unverified Items / Residual Risks の元データが存在するか | キー存在チェック → `stderr` |

## 5. 完了判定（Exit Criteria）

- [ ] handoff Markdown が verifier-contract の 6 セクション構成を持つ
- [ ] 各セクションのフィールド仕様が verifier-contract と一致
- [ ] escalation あり/なし 両ケースで正常出力される
- [ ] 出力をそのまま verifier に渡して、手動転記が不要になること

## 6. リスク・注意

- escalation_draft に Unverified Items / Residual Risks に相当する情報がない場合 → `None` を明示出力する（verifier-contract のルール通り）
- skip ケース（handoff 不要）では Markdown を生成しない → この判定ロジックは変更しない
- now-1 の compact_state テンプレートと「Next Actions」の書き方が矛盾しないこと

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
