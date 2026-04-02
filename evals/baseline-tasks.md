# Baseline Tasks

- Version: 0.2
- Date: 2026-04-02
- Owner: Codex CLI Maximizer
- Purpose: 改善前後比較のための共通評価タスク定義

## 1. 評価観点（比較可能指標）
- `success`: 要件達成可否（PASS/PARTIAL/FAIL）
- `speed`: `time_to_first_valid_plan` / `time_to_completion`
- `recovery`: `retry_count` / `recovery_success_rate` / `manual_intervention_count`

## 2. Pre-Improvement Baseline の実行条件
- 現行 Codex で実行可能な機能のみを使う（標準ツール + 既存 sub-agent 機能）。
- `team_create` / `team_delete` / Task Bus / Trigger Layer などの未実装機能は使わない。
- 同一タスクを同一環境で最低2回実行し、中央値で比較する。
- verifier 出力は `verifier-contract.md` 形式に揃える。
- 未検証は必ず未検証として記録し、成功扱いしない。

## 3. Pre-Improvement Baseline Tasks（現行で実行可能）

| ID | Size | カテゴリ | タスク内容 | Team Runtime 依存 | 主評価 |
|---|---|---|---|---|---|
| B01 | Small | Doc | 既存RFCに1項目追記し整合確認 | なし | success/speed |
| B02 | Small | Code Edit | 単一ファイルの軽微バグ修正 | なし | success/speed |
| B03 | Small | Verify | 実行コマンドと実出力を契約形式で提出 | なし | success/recovery |
| B04 | Medium | Multi-file | 3-5ファイルの仕様同期修正 | なし | success/speed/recovery |
| B05 | Medium | Refactor | 関数分割を行い動作回帰を確認 | なし | success/recovery |
| B06 | Medium | Recovery | 意図的失敗1件を first retry で復旧 | なし | recovery |
| B07 | Medium | Sub-agent | 1 sub-agent の調査結果を統合要約 | なし | speed/success |
| B08 | Large | Sub-agent | 2 sub-agent の独立調査結果を比較統合 | なし | speed/recovery |
| B09 | Large | Verify | 実装者と独立した verifier 判定を取得 | なし | success/recovery |
| B10 | Large | Resume | セッション跨ぎで作業再開し差分継続 | なし | success/speed |

## 4. Post-Implementation Acceptance Tasks（将来機能）
> 以下は Team Runtime 実装後に実施する acceptance セット。Pre-baseline には混在させない。

| ID | Size | カテゴリ | タスク内容 | 前提機能 | 主評価 |
|---|---|---|---|---|---|
| A01 | Medium | Control Plane | `team_create -> team_delete` の最小往復 | Control Plane | success |
| A02 | Medium | Task Bus | task CRUD + owner/state 遷移 | Task Bus | success/recovery |
| A03 | Large | Message Bus | direct/broadcast + approval/shutdown | Message Bus | success/recovery |
| A04 | Large | Runtime | interrupted 復旧を含む startup reconcile | Runtime State | recovery |
| A05 | Large | Worktree | member別 worktree enter/exit/cleanup | Worktree Tools | success/speed |
| A06 | Large | Trigger | one-shot/recurring/remote/sleep の安全実行 | Trigger Layer | recovery/speed |

## 5. 判定基準（初期）
- success: PASS 率 80%以上
- speed: 改善後が baseline 中央値より短縮
- recovery: stop condition 違反 0件、復帰成功率 70%以上

## 6. まだ baseline に入れられない項目
- Team Runtime を前提にした全ケース（A01-A06）
- unattended 実行の安全性評価（Trigger guard 実装前）
- memory 実験の長期効果（P2導入後に別評価）

## 7. 追加すべき評価
- split-brain 回避の耐久テスト
- orphan worktree 回収テスト
- approval timeout 多発時の運用品質テスト
