# Recovery Playbook

- Version: 0.1
- Date: 2026-04-02
- Owner: Codex CLI Maximizer

## 1. 目的
失敗時の対応順序を固定し、リトライ品質と検証独立性を標準化する。

## 2. 適用範囲
- Team 実行（coordinator + member）
- 単体 agent 実行
- verifier 付き検証フロー

## 3. 標準フロー

## 3.1 First Retry（第1再試行）
1. 失敗イベントを分類（taxonomy）
2. 最小修正だけ実施
3. 同一コマンドで再実行
4. 結果をログ化

## 3.2 Independent Verify（独立検証）
- 実装担当とは別 agent（verifier）で read-only 検証。
- 検証結果は `PASS|PARTIAL|FAIL` で返す。
- `PARTIAL` の場合、未検証項目を明示して再実装判断へ戻す。

## 3.3 Escalate（第2失敗以降）
- 同系統失敗が2回続いたら escalation。
- escalation には以下を必須添付:
  - 試した修正
  - 実行コマンド
  - 実出力
  - 仮説と次の打ち手

## 4. Failure Taxonomy
- `ENVIRONMENT`（依存欠落、権限、ネットワーク）
- `INPUT_SPEC`（要件誤解、パラメータ不備）
- `LOGIC_BUG`（実装不整合）
- `STATE_DRIFT`（runtime/state 不整合）
- `TOOLING`（ツール自体の異常）
- `UNKNOWN`（分類不能）

## 5. Stop Conditions（打ち切り条件）
- データ破壊リスクが顕在化。
- 同一仮説で2回失敗し新情報がない。
- read-only で再現不能（環境依存）で追加証拠が取れない。
- 依存サービス停止で前提が崩壊。

## 6. Coordinator / Verifier 接続
- coordinator は復旧方針と再実装を担当。
- verifier は実装に介入せず read-only 検証のみ担当。
- coordinator は verifier の `PARTIAL` を PASS 扱いしない。

## 7. 運用ルール
- 検証未実施は必ず `未実施` と記録。
- retry ごとに `attempt_index` を増やし比較可能にする。
- 成功時も residual risk を残す（ゼロ宣言しない）。

## 8. 自動化しにくい判断
- 失敗分類の境界（INPUT_SPEC vs LOGIC_BUG）。
- `PARTIAL` を許容して先に進む可否。
- stop condition 到達時の最終判断（人のレビューが必要）。
