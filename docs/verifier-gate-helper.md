# Verifier Gate Helper

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/verifier_gate_helper.py`

## 1. 目的

`post_step_check_helper` の結果を受け、問題兆候がある時だけ verifier 起動を促進する。
最終判定 `PASS / PARTIAL / FAIL` は verifier 本体に委ねる。

## 2. スコープ

- 実施:
  - `post_step_check_helper` 出力 JSON を読み込む
  - gate 判定（最小観点）
    - reconcile 失敗
    - task_get 失敗
    - message_list 失敗
    - message の pending/failed 残存
    - task state の期待不一致
    - 必要 ID 解決失敗
  - gate で要検証なら verifier を半自動起動（`--verifier-cmd` 指定時）
  - `gate_result` と `verifier_result` または `verifier_next` を JSON 出力
  - fail-open / strict 透過
- 非実施:
  - verifier ロジックの再実装
  - 自動修正
  - approval / trigger / worktree
  - runtime 本体変更

## 3. 設計（薄いラッパー）

1. helper は `post_step_check` の JSON を評価して **verifier要否だけ** 判定する。
2. verifier 実行は任意:
   - `--verifier-cmd` あり: gate trigger 時に command 実行（payload JSON を stdin で渡す）
   - `--verifier-cmd` なし: `verifier_next` に次アクションを出す
3. strict の時だけ終了コードを厳格化:
   - gate trigger で verifier 未実行、または verifier 実行失敗なら exit `2`
4. helper は verdict を代替しない。verifier 出力にある verdict は受け渡しのみ。

## 4. 実行手順

### A. gate 判定のみ（fail-open）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/verifier_gate_helper.py \
  --input-json /tmp/runtime-post-step-check/post-step-check-fail-open.json \
  --expected-task-state in_progress \
  --output-json /tmp/runtime-post-step-check/verifier-gate-fail-open.json
```

### B. gate trigger 時に verifier command を実行
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/verifier_gate_helper.py \
  --input-json /tmp/runtime-post-step-check/post-step-check-fail-open.json \
  --expected-task-state blocked \
  --verifier-cmd "python3 /tmp/mock_verifier.py" \
  --output-json /tmp/runtime-post-step-check/verifier-gate-with-verifier.json
```

### C. strict
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/verifier_gate_helper.py \
  --strict \
  --input-json /tmp/runtime-post-step-check/post-step-check-fail-open.json \
  --expected-task-state blocked \
  --output-json /tmp/runtime-post-step-check/verifier-gate-strict.json
```
