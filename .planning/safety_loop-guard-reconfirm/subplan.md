# Subplan: loop guard の実タスク再確認

## メタ情報

- **Phase ID**: `safety_loop-guard-reconfirm`
- **Master Flow 位置**: Safety（Now と並走）
- **依存先**: なし（独立実行可能。now-3 と並走推奨）
- **主対象ファイル**: `poc/loop_guard.py`
- **副対象**: `docs/recovery-playbook.md`, `poc/post_step_check_helper.py`
- **推定ワークロード**: now-3 と並走（追加工数ほぼゼロ）
- **ステータス**: `done`

---

## 1. 目的

loop guard のパラメータが recovery-playbook と整合していることを確認し、single-pass を壊す自動再試行が混入していないことを保証する。

## 2. 背景・前提

- `loop_guard.py`（6,001 bytes）が preflight / post-run guard を提供
- `recovery-playbook.md` が `attempt_count`, `max_retries`, `escalate_after_n`, `stop_condition` のルールを定義
- **懸念**: PoC 開発中にパラメータのデフォルト値が playbook とズレた可能性がある
- **制約**: single-pass を壊す自動再試行は意図的に入れていない → これが崩れていないことの確認

## 3. 具体的な作業ステップ

### Step 1: パラメータ整合性の diff 確認

- **対象**: `poc/loop_guard.py` vs `docs/recovery-playbook.md`
- **やること**:
  1. loop_guard.py 内の以下の変数/デフォルト値を抽出:
     - `attempt_count` / `max_attempts` 相当
     - `max_retries` 相当
     - `escalate_after_n` 相当
     - `stop_condition` 相当
  2. recovery-playbook.md 内の対応ルールを抽出
  3. 差分があれば報告
- **検証コマンド**:
  ```bash
  grep -nE "(attempt|retry|retries|escalat|stop_cond|max_)" poc/loop_guard.py
  grep -nE "(attempt|retry|retries|escalat|stop_cond|max_)" docs/recovery-playbook.md
  ```

### Step 2: 自動再試行の混入チェック

- **対象**: `poc/` 全体
- **やること**: 自動ループ / 自動リトライのパターンが混入していないことを確認
- **検証コマンド**:
  ```bash
  # 自動再試行パターンの検索
  grep -rnE "(while.*retry|for.*retry|auto.*retry|auto.*loop|retry_loop|do_retry)" poc/ --include="*.py"
  
  # sleep + retry の組み合わせ
  grep -rnE "time\.sleep.*retry|retry.*time\.sleep" poc/ --include="*.py"
  ```
- **期待結果**: ヒットゼロ、またはコメントアウトされた実験コードのみ

### Step 3: now-3 dogfooding 中の実地確認

- **対象**: now-3 の dogfood タスク実行時
- **やること**: orchestrator 実行中に以下を観察
  1. preflight guard が呼ばれているか（stderr 出力で確認）
  2. post-run guard が呼ばれているか
  3. 2 回連続失敗時に自動再試行が起きず、エスカレーションが発生するか
- **この Step は now-3 と同時実行**

### Step 4: 差分があった場合の修正判断

- **やること**: Step 1-3 で差分が見つかった場合
  - パラメータのズレ → recovery-playbook.md を正とし、loop_guard.py を合わせる
  - 自動再試行の混入 → 即時削除
  - 差分なし → PASS として記録

## 4. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| `loop_guard.py`: preflight 判定 | guard が通過/拒否した理由 | `stderr` に verdict + reason を出力 |
| `loop_guard.py`: attempt_count 増分 | 増分タイミングが想定通りか | `stderr` に `attempt_count` 値を都度出力 |
| `post_step_check_helper.py`: post-run 判定 | stop_condition の評価結果 | `stderr` に評価対象と結果を出力 |

## 5. 完了判定（Exit Criteria）

- [x] loop_guard.py のパラメータが recovery-playbook.md と整合
- [x] poc/ 内に自動再試行パターンが混入していないことを grep で確認
- [x] now-3 dogfooding 中に guard が期待通りに動作することを実地確認
- [x] 差分なし → PASS 記録

## 6. リスク・注意

- grep だけでは検出漏れの可能性あり（変数名が異なる場合）→ Step 3 の実地確認で補完済み
- recovery-playbook.md 自体の記述が曖昧な場合 → playbook 側を先に明確化（今回は問題なし）
- 「single-pass を壊す」の定義: 「1 回の orchestrator 実行で同一 helper を 2 回以上呼ばない」を基準とした

## 7. 実行ログ

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| 2026-04-03 04:19 | Step 1: パラメータ diff | 整合確認 | Step 2 へ |
| 2026-04-03 04:19 | Step 2: auto-retry grep | ヒットゼロ | Step 3 へ |
| 2026-04-03 04:22 | Step 3: dogfood 実地確認 | guard 正常動作 | PASS → safety 完了 |
