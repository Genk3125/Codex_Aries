# One-Shot Orchestrator 実験レポート（small / medium / recovery）

- Date: 2026-04-03
- Target: `poc/one_shot_orchestrator.py`
- Purpose: 最小運用カーネル（helper連結）が実運用の強さに寄与するかを確認

## 1) 実験で実施したこと

`one_shot_orchestrator` を使い、Codex 作業に近い3シナリオを実行した。

- **small**: 軽量フロー（`flow_mode=gate`、fail-open）
- **medium**: 連結フロー（`flow_mode=chain`、fail-open、`--verifier-cmd` 注入）
- **recovery**: strict 失敗から strict 回復（`flow_mode=gate`、`--verifier-cmd` 注入）

## 2) 実行コマンド一覧

### small（fail-open / gate）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --flow-mode gate \
  --team-name exp-small \
  --member-id worker_small_1 \
  --task-title "small: tiny maintenance" \
  --bootstrap-message "start small run" \
  --task-update-state in_progress \
  --task-update-message "small moved to in_progress" \
  --gate-expected-task-state in_progress \
  --store-root /tmp/orch-experiments/small/store \
  --output-json /tmp/orch-experiments/small/orchestrator.json
```

### medium（fail-open / chain / verifier-cmd 注入）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --flow-mode chain \
  --team-name exp-medium \
  --member-id worker_medium_1 \
  --task-title "medium: multi-step kernel flow" \
  --bootstrap-message "start medium run" \
  --task-update-state in_progress \
  --task-update-message "medium moved to in_progress" \
  --task-update-result-reference "ref://medium-run" \
  --gate-expected-task-state blocked \
  --bridge-message "gate triggered; moved to blocked" \
  --verifier-cmd "python3 /tmp/mock_verifier.py" \
  --store-root /tmp/orch-experiments/medium/store \
  --output-json /tmp/orch-experiments/medium/orchestrator.json
```

### recovery（strict fail）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --strict \
  --flow-mode gate \
  --team-name exp-recovery \
  --member-id worker_recovery_1 \
  --task-title "recovery: forced strict fail" \
  --bootstrap-message "start recovery run" \
  --task-update-state in_progress \
  --task-update-message "recovery moved to in_progress" \
  --gate-expected-task-state blocked \
  --verifier-cmd "python3 /tmp/mock_verifier.py" \
  --store-root /tmp/orch-experiments/recovery/store-fail \
  --output-json /tmp/orch-experiments/recovery/orchestrator-fail.json
```

### recovery（strict recover / 手動介入後）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/one_shot_orchestrator.py \
  --strict \
  --flow-mode gate \
  --team-name exp-recovery \
  --member-id worker_recovery_1 \
  --task-title "recovery: strict recover" \
  --bootstrap-message "retry recovery run" \
  --task-update-state in_progress \
  --task-update-message "recovery moved to in_progress" \
  --gate-expected-task-state in_progress \
  --verifier-cmd "python3 /tmp/mock_verifier.py" \
  --store-root /tmp/orch-experiments/recovery/store-recover \
  --output-json /tmp/orch-experiments/recovery/orchestrator-recover.json
```

## 3) 3タスク結果比較

| Task | Mode | Flow | verifier-cmd | 結果 | 実行ステップ数 | 実行時間(ms) | 手動介入 |
|---|---|---|---|---|---:|---:|---|
| small | fail-open | gate | なし | 成功 (`ok=true`) | 4 | 506 | なし |
| medium | fail-open | chain | あり | 成功 (`ok=true`) | 7 | 749 | なし |
| recovery | strict | gate | あり | 1回目失敗 (`ok=false`, exit=2) → 2回目成功 (`ok=true`) | 4 + 4 | 475 + 465 | あり（expected state 修正） |

補足:
- medium では `verifier_gate` が `TASK_STATE_MISMATCH` を検知し `reported_verdict=PARTIAL`。fail-open のためフロー継続し、bridge/loopback/chain まで到達。
- recovery では strict により `PARTIAL` を失敗として即停止でき、原因が `verifier_gate` に局所化された。

## 4) 観測（強さへの寄与）

### 速くなったか
- 実行コマンド数は **実質1コマンド/タスク** に集約された（従来の手動 4〜7 コマンド連結を置換）。
- small/medium は 1 秒未満で完走（ローカル計測）。

### 迷いが減ったか
- `task_id` / `team_id` / 中間 JSON の受け渡しが orchestrator 内で完結。
- どの helper で落ちたかが `results.<helper>.ok` で明示され、分岐判断が速い。

### 復旧しやすいか
- strict 失敗時に `verifier_gate_helper` で停止点が固定される。
- recovery はパラメータ1点修正（`--gate-expected-task-state`）で再実行できた。

## 5) ボトルネック整理

1. **判定パラメータ依存**
   - `--gate-expected-task-state` の不整合で strict 失敗しやすい。
2. **verifier-cmd の意味論依存**
   - 外部 verifier の verdict 運用に一貫性が必要（PARTIAL をどう扱うか）。
3. **単発実行の限界**
   - 連続失敗時の自動エスカレーションは未実装（意図的に未実装）。

## 6) 結論

### 何が本当に強くなったか
- **接続層**（orchestrator + helper群）で、操作手順の一貫性・再現性・障害局所化が大きく改善。
- fail-open / strict の切替を1箇所から統制できるため、探索とゲートの使い分けが明確になった。

### まだ弱い箇所
- strict 運用時のパラメータ設計（expected state）に運用知識が必要。
- verifier 結果の扱いは外部コマンド品質に依存。

### 一番効いたレイヤー
- **one_shot_orchestrator + chain 連結**（接続レイヤー）が最も効果大。
  - 実処理ロジックを増やさず、既存 helper を束ねるだけで運用負荷を下げられた。

### 次に厚くすべき箇所
- full automation 前提の loop guard:
  - `attempt_count`
  - `max_retries`
  - `escalate_after_n`
  - `stop_condition`
- 上記を `/Users/kondogenki/AI Agent Maximizer/docs/recovery-playbook.md` に接続して、停止/エスカレーション規律を固定する。
