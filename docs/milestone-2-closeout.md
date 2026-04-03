# Milestone 2 Closeout (Provisional)

_Date: 2026-04-03_

## 0. 判定レベル

- この closeout は **provisional**。
- 理由: Phase 17 は real-world calendar 30-day ではなく、compressed 30 cycles で代替検証したため。
- final closeout 条件: real-world 30-day dogfood を完了し、Ship 判定を再確定する。

## 1. 成果物棚卸し

## 実装コード（主要）
- `poc/context_compactor.py`（runs 集約コンパクタ）
- `poc/computer_use_helper.py`（evidence collector）
- `src/team_runtime/`（control/message/task/runtime へ昇格）
- `tests/e2e/run_all.sh`（5シナリオ統合試験）
- `tests/e2e/team_runtime_mvp.py`（3-member + resume/reconcile）
- `eval/run_baseline.py` + `eval/tasks/manifest.json`（10タスク基準測定）

## スクリプト運用層
- `scripts/run-task.sh`（auto context compaction, computer-use 引数対応）
- `scripts/resume-task.sh`（context-compacted 優先再開、gate expected 継承 opt-in）

## 計画/運用文書
- `.planning/*` Phase 9-18 subplan 更新
- `logs/daily-dogfood-30.md`（30サイクル運用記録）
- `eval/baseline-results.md`（6指標ベースライン）
- 追加メモ:
  - `docs/context-compactor.md`
  - `docs/computer-use-helper.md`
  - `docs/computer-use-mcp-setup.md`
  - `docs/team-runtime-mvp.md`
  - `docs/auto-context-pipeline.md`

## 規模（現時点）
- Python ファイル数: 29
- Python 総行数: 9808
- docs 配下 markdown 数: 44

## 2. 指標結果（Phase 16 + 17）

## Eval baseline（`eval/baseline-results.json`）
- `task_success_rate`: 100.0%
- `first_valid_output_time_sec`: 0.578 sec
- `self_recovery_rate`: 100.0%
- `rework_cycles_per_task`: 0.1
- `verification_pass_rate`: 100.0%
- `team_completion_rate`: 100.0%

## Daily dogfood（`logs/daily-dogfood-30.md`）
- 30/30 サイクル記録（compressed validation）
- task_success_rate: 100.0%
- manual-free ratio: 83.33%
- computer-use tasks: 5
- team runtime tasks: 3
- 最終判定: PASS（compressed validation）
- Ship 判定: provisional（real-world 30-day pending）

## 3. うまくいったこと
- helper 連鎖を壊さずに Team Runtime / computer-use / context reduction を追加できた。
- strict 失敗→resume の復旧経路が安定した（`resume-task.sh` の carry 制御を導入）。
- E2E 5 シナリオを単発スクリプトで再現可能化できた。

## 4. うまくいかなかったこと
- 30-day dogfood はカレンダー30日ではなく圧縮30サイクルでの検証になった。
- Playwright CLI 依存は環境差があり、fallback snapshot が必要だった。

## 5. 学んだこと
- `gate_expected_task_state` の無条件継承は recovery を破壊する。
- compact 系は token 予算ではなく「保持フィールド固定」が先に効く。
- team runtime は adapter 入口を固定すると実験層との接続が安定する。

## 6. 次にやるべきこと（Milestone 3 入力）
- real-world calendar 30-day dogfood を実施し、Milestone 2 final closeout を確定
- Trigger / worktree の本実装
- verifier 自動起動ではなく verifier queue 化
- full automation へ進む前の loop guard policy 強化（attempt windows / cool-down）
- memory 実験の fail-open 境界を本運用へ接続

## Milestone 3 親子計画（Phase 19-25）
- `m3-1_real-world-30day-dogfood`
- `m3-2_trigger-layer-mvp`
- `m3-3_worktree-runtime-tools-mvp`
- `m3-4_verifier-queue-standardization`
- `m3-5_team-runtime-deferred-priority`
- `m3-6_docs-status-release-sync`
- `m3-7_ts-boundary-decision`

## 7. 手動運用項目
- `git tag milestone-2-complete` は本セッションでは未実行。
- 理由: 実行ポリシー上、明示依頼のない commit/tag 操作は行わないため。
