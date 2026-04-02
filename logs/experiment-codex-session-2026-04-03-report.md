# Codex セッション最小オーケストレーション実験レポート（2026-04-03）

## 結果
- 最終判定: **PARTIAL**
- 判定根拠: runtime の主要操作は成立したが、README の変更を「1行追加のみ」と厳密比較できる事前差分基準（VCS/スナップショット）が不足。

## 何を実験したか
- 既存 `runtime adapter` / `coordinator` / `verifier` のみで、Codex セッション最小フローを 1 回実施。
- 対象フロー:
  1. coordinator で計画合成
  2. `team-create`
  3. `task-create`（実装/検証）
  4. `send-message`
  5. 最小変更 1 件（`README.md` に bullet 追加）
  6. verifier 実行
  7. `runtime_reconcile_all`
  8. fail-open / strict の挙動確認

## 何が本当に動いたか
- `team-create`: `team_6a3e8ab07b48` を作成、leader 付与成功。
- `task-create`: 実装タスク / 検証タスクを作成し、最終的に両方 `done` へ更新成功。
- `send-message`: direct message 2 件を送信し、recipient 配信状態 `delivered` を確認。
- `runtime_reconcile_all`: control/message/task の 3 系統を再整合し、今回 `orphaned=0` / `pending_after=0`。
- fail-open/strict:
  - fail-open: `TEAM_NOT_FOUND` でも exit code `0`。
  - strict: 同条件で exit code `2`。
- verifier: contract 形式で `PARTIAL` を返却。

## 観測された問題点
1. **ログ解析の脆弱性**  
   正規表現で JSON を抜き出す実装が `Extra data` で破綻。実験中に ID を固定値管理へ切替。
2. **store root の取り違えリスク**  
   `CODEX_RUNTIME_STORE_ROOT` を毎回明示しないと別ストアを参照する可能性が高い。
3. **変更厳密検証の基盤不足**  
   `.git` 不在で事前後差分の機械的比較ができず、verifier が `PARTIAL` へ寄る。
4. **手動受け渡しが多い**  
   `team_id` / `task_id` / `leader_id` の引き回しと task state 更新が手動。

## どこで手動介入が必要だったか
- coordinator への指示文作成と計画の採択。
- runtime 応答から ID を抽出し次コマンドへ受け渡し。
- verifier 起動指示と検証結果の task 反映。
- エラー時（JSON解析失敗）の回復手順選択。

## 一番痛いボトルネック
- **ID と状態遷移の手動オペレーション**。  
  フローの再現性よりも、運用者の手作業精度に依存する点が最も重い。

## 次に自動化すべき 1 箇所
- `team-create -> task-create -> send-message -> task_update` を一括で扱う薄いセッションヘルパー（wrapper）を追加し、ID 受け渡しと state 更新を自動化する。

## 追記: team_member 修正のトリガー整理（2026-04-03）
- 一次トリガー（違和感検知）: `/Users/kondogenki/Downloads/team-member-impl-summary.md`
- 二次トリガー（実装修正確定）: `/Users/kondogenki/AI Agent Maximizer/poc/team_control_plane.py` の確認
  - `team_member_remove` 本体（`/Users/kondogenki/AI Agent Maximizer/poc/team_control_plane.py:406` 以降）
  - warning-only の leader removal 方針（旧 `:434` 付近）
  - `_read_idempotency` default schema（`/Users/kondogenki/AI Agent Maximizer/poc/team_control_plane.py:132`）
- 反映した方針: leader removal 拒否 + idempotency schema 正規化

## 実行した確認手順
- 詳細実行ログ: `logs/experiment-codex-session-2026-04-03.log`
- コマンド一覧: `logs/experiment-codex-session-2026-04-03-commands.md`
- coordinator 計画記録: `logs/experiment-coordinator-plan-2026-04-03.md`
- verifier レポート: `logs/experiment-verifier-report-2026-04-03.md`
