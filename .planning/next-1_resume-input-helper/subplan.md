# Subplan: resume-input 変換 helper

## メタ情報

- **Phase ID**: `next-1_resume-input-helper`
- **Master Flow 位置**: Next（Now 完了後）
- **依存先**: `now-1`（compact_state 出力フォーマットが確定していること）, `now-3`（dogfooding で判明した実 resume パターン）
- **主対象ファイル**: 新規 `poc/resume_input_helper.py` or `poc/compact_state_helper.py` 拡張
- **副対象**: `poc/recovery_next_helper.py`, `poc/handoff_helper.py`
- **推定ワークロード**: 1 セッション
- **ステータス**: `done`

---

## 1. 目的

compact_state の出力 JSON を recovery_next_helper / handoff_helper の入力フォーマットに変換し、セッション再開時の手動フォーマット変換を不要にする。

## 2. 背景・前提

- compact_state は「次ターン向け最小 state」を出力する（now-1 で確立）
- recovery_next_helper は「次に何をすべきか」を計算する
- handoff_helper は「verifier/coordinator 向けの引き継ぎ」を整形する
- **現状の課題**: compact_state → 各 helper の入力フォーマットが異なり、手動変換が必要
- **now-3 の dogfooding で判明するはず**: 実際にどの変換パスが頻出するか

### 想定される変換パス
```
compact_state JSON
    ├─→ recovery_next_helper 入力（resume 時）
    └─→ handoff_helper 入力（escalation 時）
```

## 3. 具体的な作業ステップ

### Step 1: 入出力フィールドマッピング表を作成

- **やること**:
  1. compact_state 出力 JSON のスキーマを整理（now-1 成果物から）
  2. recovery_next_helper の入力スキーマを `poc/recovery_next_helper.py` の argparse から抽出
  3. handoff_helper の入力スキーマを `poc/handoff_helper.py` の argparse から抽出
  4. マッピング表を作成: compact_state キー → 各 helper の引数
- **出力**: `.planning/next-1_resume-input-helper/field-mapping.md`

### Step 2: 変換方式の決定

- **選択肢**:
  - A) 新規スクリプト `poc/resume_input_helper.py` を作る
  - B) compact_state_helper に `--format-for recovery_next|handoff` オプションを追加
  - C) 各 helper に `--from-compact <compact.json>` オプションを追加
- **判断基準**: now-3 の dogfooding で判明した頻出パスに合わせる
- **推奨**: 選択肢 C（各 helper 側で吸収）— helper の独立性が保たれる

### Step 3: 実装

- **やること**: Step 2 で選んだ方式で変換ロジックを実装
- **最低限の変換**:
  - 必須キーの存在チェック
  - キー名のリネーム（compact → helper 固有名）
  - 欠損キーへのデフォルト値付与
- **非実施**: 型変換、バリデーション強化（それは後のフェーズ）

### Step 4: E2E テスト

- **やること**: now-1 の 3 パターン compact_state 出力を入力に使い、各 helper が正常動作することを確認
- **検証コマンド例**:
  ```bash
  # compact → recovery_next_helper
  python3 poc/recovery_next_helper.py --from-compact /tmp/e2e/small/compact.json --output-json /tmp/e2e/small/recovery-next.json
  
  # compact → handoff_helper (escalation ケース)
  python3 poc/handoff_helper.py --from-compact /tmp/e2e/recovery/compact.json --output-json /tmp/e2e/recovery/handoff.json
  ```

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| 変換関数: 入力パース | compact JSON にあるが使われないキー | `[DEBUG][resume] unused_keys=` を stderr |
| 変換関数: 出力構築 | 出力に必要だが入力にないキー | `[DEBUG][resume] missing_for_output=` を stderr |
| 各 helper: `--from-compact` 分岐 | 従来入力と compact 入力で同じ出力になるか | 両方実行して diff |

## 5. 完了判定（Exit Criteria）

- [ ] compact_state → recovery_next_helper の変換が動作する
- [ ] compact_state → handoff_helper の変換が動作する
- [ ] 3 パターンの compact_state 出力で E2E が通る
- [ ] フィールドマッピング表がドキュメント化されている

## 6. リスク・注意

- now-1 の compact_state 出力スキーマが変更されると、この変換も壊れる → now-1 のスキーマ固定が前提
- now-3 の dogfooding 結果次第で「実はこの変換パスは不要」となる可能性がある → その場合はこの subplan をスキップ

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
