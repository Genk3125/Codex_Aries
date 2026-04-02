# Dogfood Journal

_Created: 2026-04-03_

## 実行記録

### Task 1: Gate — docs 整合確認 (fail-open)
- **flow**: gate
- **結果**: `failed` — session_helper が最初に失敗（codex-runtime 未設定）
- **compact.md**: 正常生成、next_action=`inspect_failure`
- **手動介入**: なし（パイプライン自体は自動完了）
- **観察**: runtime-adapter (exit_code 126) が全ケースの根本失敗原因。runtime 未接続時は全 helper が fail-open で進み、verifier_gate が RECONCILE_FAILED 等を6件検出する

### Task 2: Chain — compact→handoff 連結 (fail-open)
- **flow**: chain
- **結果**: `failed` — 5/7 ステップ失敗、chain_helper と loopback_helper のみ成功
- **compact.md**: 正常生成、last_successful_step=`chain_helper`
- **手動介入**: なし
- **観察**: chain モードでは bridge→loopback→chain まで全実行されるが、bridge が missing_task_or_team_id でスキップされ、実質 no-op

### Task 3: Recovery — strict fail → recover (strict)
- **flow**: gate (strict)
- **結果**: 1回目 exit=2（strict fail）、2回目 exit=2（gate_expected_task_state 変更でもリカバリ不可）
- **compact-fail.md / compact-recover.md**: 両方正常生成
- **手動介入**: gate_expected_task_state を `blocked` → `in_progress` に変更（手動判断ポイント）
- **観察**: strict モードでは runtime 未接続だと post_step_check が即 exit=2 で停止する。expected_task_state の変更だけではリカバリ不十分（runtime 接続が必要）

## 横断的な発見

### 手動介入パターン（3 タスク共通）
1. **runtime-adapter 未設定時の判断**: 全 helper が runtime (exit_code 126) で失敗する → runtime なしで gate-only テストしたい場合の `--skip-runtime` フラグがない
2. **gate_expected_task_state の事前判断**: どの状態を期待すべきか実行前に分からない → compact.md の Status セクションに期待値のヒントを出すべき
3. **strict recovery の限界**: runtime 未接続では strict リカバリが機能しない → これは正しい挙動（strict = 妥協しない）

### compact.md の品質評価
- ✅ 次アクションが 10 秒以内に判断可能
- ✅ 失敗ステップが明確
- ⚠️ exit_code=0 なのに `failed` 判定になるケースがある（`ok: false` で判定しているため正しいが、表示上は混乱しうる）
