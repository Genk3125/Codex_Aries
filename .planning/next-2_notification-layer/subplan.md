# Subplan: 通知層追加（guard → notification）

## メタ情報

- **Phase ID**: `next-2_notification-layer`
- **Master Flow 位置**: Next
- **依存先**: なし（単独着手可能。`next-1` とは独立）
- **主対象ファイル**: 新規 `poc/notify_helper.py`（仮称）
- **副対象**: `poc/loop_guard.py`, `poc/post_step_check_helper.py`, `docs/preflight-guard-check.md`
- **推定ワークロード**: 1 セッション
- **ステータス**: `not_started`

---

## 1. 目的

preflight guard / post-run guard の stop reason を運用通知に繋ぐ薄いレイヤーを追加し、「guard が止めた/通した」をオペレータが確認できるようにする。

## 2. 背景・前提

- guard が stop reason を返す仕組みは既にある（loop_guard.py / post_step_check_helper.py）
- しかし、stop reason の通知先が `stderr` 出力のみで、構造化された通知には繋がっていない
- **最小目標**: guard → フォーマットされた stderr 通知（Phase 1）
- **将来目標**: guard → ファイル書き出し / webhook（Phase 2 以降）

## 3. 具体的な作業ステップ

### Step 1: guard の stop reason 全種類を列挙

- **対象**: `poc/loop_guard.py`, `poc/post_step_check_helper.py`
- **やること**:
  1. 各 guard が返す stop reason の種類を grep で抽出
  2. 各 reason に対する通知テンプレートを設計
- **検証コマンド**:
  ```bash
  grep -nE "(stop_reason|StopReason|STOP_|reason.*=)" poc/loop_guard.py poc/post_step_check_helper.py
  ```
- **出力**: stop reason 一覧表

### Step 2: 通知テンプレートを設計

- **やること**: 各 stop reason に対して以下の通知フォーマットを定義
  ```
  [NOTIFY][<guard_name>] <verdict>
  reason: <stop_reason>
  timestamp: <ISO8601>
  action_required: <yes|no>
  suggested_next: <next_action>
  ```
- **出力**: `.planning/next-2_notification-layer/notification-templates.md`

### Step 3: notify_helper の最小実装

- **対象**: 新規 `poc/notify_helper.py`
- **やること**:
  - 入力: guard 出力 JSON（stop_reason を含む）
  - 出力: フォーマット済み通知文を stderr に書く
  - オプション: `--output-file` でファイルにも書き出す
  - **fail-open**: 通知自体が失敗しても本体処理を止めない
- **非実施**: webhook 送信、メール通知、Slack 連携

### Step 4: orchestrator → guard → notify の接続テスト

- **やること**: orchestrator が guard を呼び、guard が notify を呼ぶフローをテスト
  1. preflight guard PASS → 通知なし（or verbose 時のみ通知）
  2. preflight guard FAIL → 通知発火
  3. post-run guard STOP → 通知発火
- **検証**: stderr に通知が出力されること、本体のフローが通知の成否に依存しないこと

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| `notify_helper.py`: 通知発火判定 | guard が通知をトリガーした/しなかった | `[DEBUG][notify] triggered=true/false` を stderr |
| `notify_helper.py`: 通知出力 | フォーマットが正しいか | 出力を regex で構造チェック |
| orchestrator → notify 接続 | 通知失敗が本体を止めていないか | try/except で wrap し、`[DEBUG][notify] error ignored` を出力 |

## 5. 完了判定（Exit Criteria）

- [ ] guard の stop reason 全種類が列挙されている
- [ ] 各 stop reason に対する通知テンプレートが定義されている
- [ ] notify_helper が stderr に構造化通知を出力する
- [ ] 通知失敗が本体処理を止めないことが確認されている
- [ ] orchestrator → guard → notify の E2E が動作する

## 6. リスク・注意

- 通知層を厚くしすぎると helper 数が増えてメンテナンスコストが上がる → 最小限に抑える
- fail-open 原則を徹底: 通知はベストエフォート
- 将来の webhook 化を見据えて、出力フォーマットは JSON 互換にしておく

## 7. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
