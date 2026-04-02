# Subplan: compact_state を実運用フローへ組み込む

## メタ情報

- **Phase ID**: `now-1_compact-state-integration`
- **Master Flow 位置**: Now（最優先・最初に着手）
- **依存先**: なし（単独着手可能）
- **主対象ファイル**: `poc/compact_state_helper.py`
- **副対象**: `poc/one_shot_orchestrator.py`, `docs/compact-state-helper.md`
- **推定ワークロード**: 1-2 セッション
- **ステータス**: `not_started`

---

## 1. 目的

orchestrator 実行後に compact_state を呼び出して「次ターンで何をすべきか」を固定フォーマットで出力する E2E パイプラインを確立する。

## 2. 背景・前提

- `compact_state_helper.py`（14,766 bytes）は既に動作する PoC がある
- `one_shot_orchestrator.py` が `--output-json` で結果 JSON を書き出す
- 現状は orchestrator 出力を手動で読み、次アクションを判断している
- **課題**: orchestrator → compact_state の接続が手動であり、出力フォーマットが不定

### 既存の接続パス
```
orchestrator --output-json /tmp/out.json
    ↓ (手動)
compact_state_helper --orchestrator-json /tmp/out.json --output-json /tmp/compact.json
    ↓ (未実装)
次ターン入力テンプレート（Markdown）
```

## 3. 具体的な作業ステップ

### Step 1: orchestrator 出力 JSON のキー棚卸し

- **対象**: `poc/one_shot_orchestrator.py` の出力 JSON
- **やること**: orchestrator が書き出す JSON の全キーを列挙し、compact_state が期待する入力キーとの差分を洗い出す
- **具体的な方法**:
  1. 実験レポートの 3 パターン出力（small/medium/recovery）を再実行して JSON を取得
  2. `jq 'keys'` で各パターンのトップレベルキーを比較
  3. compact_state_helper の `json.load` 部分で参照しているキーを grep で列挙
- **検証**: 差分がゼロであること、または差分への対処方針が決まること

### Step 2: compact_state 出力の次ターンテンプレート仕様を固定

- **対象**: 新規 — `.planning/now-1_compact-state-integration/next-turn-template.md`
- **やること**: compact_state JSON から生成する Markdown テンプレートのフォーマットを決める
- **含めるべきフィールド**:
  ```markdown
  ## Resume Context
  - **Status**: <current_status>
  - **Last OK Step**: <last_successful_step>
  - **Failed Step**: <failed_step> (あれば)
  - **Stop Reasons**: <stop_reasons> (あれば)
  
  ## Evidence Summary
  - **Executed**: <executed_commands_summary>
  - **Output**: <actual_outputs_summary>
  
  ## Next Action
  <next_action>
  
  ## IDs
  - task: <task_id>
  - team: <team_id>
  - member: <member_id>
  ```
- **検証**: 人が読んで「次に何をすべきか」が 10 秒以内に判断できること

### Step 3: compact_state_helper に Markdown テンプレート出力を追加

- **対象**: `poc/compact_state_helper.py`
- **やること**: `--output-markdown` オプションを追加し、Step 2 のテンプレートを出力する
- **変更箇所の見込み**:
  - argparse に `--output-markdown` を追加
  - compact_state JSON → Markdown 変換関数を追加
  - 既存の `--output-json` は変更しない
- **検証**: `--output-json` と `--output-markdown` 両方指定で、両方書き出されること

### Step 4: E2E テスト — 3 パターンで通す

- **対象**: orchestrator → compact_state → テンプレートの全パイプライン
- **やること**:
  1. small パターン: `orchestrator --output-json → compact_state --output-markdown`
  2. medium パターン: 同上
  3. recovery パターン: 1 回目失敗 → 2 回目成功で、それぞれの compact_state を確認
- **検証コマンド例**:
  ```bash
  # small
  python3 poc/one_shot_orchestrator.py --flow-mode gate ... --output-json /tmp/e2e/small/orch.json
  python3 poc/compact_state_helper.py --orchestrator-json /tmp/e2e/small/orch.json \
    --output-json /tmp/e2e/small/compact.json --output-markdown /tmp/e2e/small/compact.md
  cat /tmp/e2e/small/compact.md  # 人が読んで判断可能か確認
  ```

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| `compact_state_helper.py`: `json.load()` 直後 | 受け取ったキー一覧と欠損キー | `print(f"[DEBUG][compact] keys={sorted(data.keys())}", file=sys.stderr)` |
| `compact_state_helper.py`: JSON 書き込み直前 | `next_action` が空でないか | `assert compact["next_action"], "next_action is empty"` |
| orchestrator → compact_state 接続部 | 出力 JSON ファイルが存在するか | `os.path.exists()` + stderr 警告 |
| Markdown 生成関数 | セクション数が期待通りか | `stderr` にセクション数を出力 |

## 5. 完了判定（Exit Criteria）

- [ ] orchestrator 出力 JSON の全キーが compact_state で消費可能
- [ ] compact_state が `--output-markdown` でテンプレートを出力する
- [ ] small / medium / recovery の 3 パターンで E2E が通る
- [ ] 生成された Markdown を読んで次アクションが 10 秒以内に判断可能

## 6. リスク・注意

- orchestrator の出力 JSON スキーマが flow-mode（gate/chain）で異なる可能性 → Step 1 で洗い出す
- recovery パターンでは 2 回分の JSON があるため、「どちらの JSON を compact に渡すか」の判断が必要
- strict 失敗時は orchestrator の JSON が不完全な可能性がある → fail-safe デフォルト値を用意

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
