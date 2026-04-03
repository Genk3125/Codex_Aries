# Subplan: 日常運用パイプラインの定着

## メタ情報

- **Phase ID**: `settle-1_daily-driver-pipeline`
- **Master Flow 位置**: Settle（Phase 8）
- **依存先**: Phase 1-7（全 done）
- **主対象ファイル**: `poc/one_shot_orchestrator.py`, 新規 `scripts/run-task.sh`
- **推定ワークロード**: 2 セッション
- **ステータス**: `done`

---

## 1. 目的

Phase 1-7 で作った個別 helper を「1 コマンドで日常タスクを起動→検証→状態保存→再開」できるパイプラインにまとめ、**毎日の開発で実際に使う**状態にする。

## 2. 背景・前提

- 現在 orchestrator + compact_state + handoff + notify + verifier_gate の全 helper が動作する
- しかし起動コマンドが長い（10+ 引数）
- --from-compact での再開も「compact → recovery_next → handoff」の 3 段チェーンが手動
- **目標**: `./scripts/run-task.sh "タスク名"` 一発で起動、失敗時は `./scripts/resume-task.sh` で再開

## 3. 具体的な作業ステップ

### Step 1: ワンコマンドラッパー `scripts/run-task.sh` 作成

- **やること**:
  1. orchestrator の全引数をデフォルト値付きで wrap する
  2. 出力先を `runs/<timestamp>/` に固定
  3. 完了後に自動で `compact_state --output-markdown` を実行
  4. 失敗時に自動で `notify_helper` を呼ぶ
- **インターフェース**:
  ```bash
  ./scripts/run-task.sh \
    --title "fix the login bug" \
    --flow gate \           # default: gate
    --strict                # optional
  ```

### Step 2: 再開ラッパー `scripts/resume-task.sh` 作成

- **やること**:
  1. `runs/<latest>/compact.json` を自動検出
  2. `--from-compact` 経由で recovery_next_helper を実行
  3. 必要に応じて handoff を生成
  4. 新しい orchestrator run を起動

### Step 3: runs/ ディレクトリ構造の固定

```
runs/
  2026-04-03T12-00-00/
    orch.json          # orchestrator 出力
    compact.json       # compact_state 出力
    compact.md         # human-readable resume context
    notify.txt         # notification output (if any)
    handoff.md         # handoff draft (if escalation)
```

### Step 4: 実タスクで 5 回使用して検証

- **やること**: 日常の開発タスクで 5 回以上 `run-task.sh` を使用
- **記録**: `logs/daily-driver-journal.md` に結果を記録
- **成功基準**: 5 回中 3 回以上、手動引数指定なしで起動から結果保存まで完走

## 4. 完了判定（Exit Criteria）

- [x] `scripts/run-task.sh` が 1 コマンドで orchestrator パイプライン全体を起動する
- [x] `scripts/resume-task.sh` が compact.json から自動再開する
- [x] runs/ ディレクトリに全出力が構造化保存される
- [x] 5 回の実タスク使用で 3 回以上手動介入なしで完走

## 5. リスク・注意

- codex-runtime が未接続の場合、session/post_step_check が常に fail-open → ラッパーはこれを許容する
- strict モードは初回使用では推奨しない（fail-open をデフォルトとする）

## 6. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| 2026-04-03 | `scripts/run-task.sh` / `scripts/resume-task.sh` を実装し、`runs/` へ成果物保存フローを固定化 | 実行可能化 + fail-open/strict 透過を維持 | 5回の run-task 実行で日常運用性を確認 |
| 2026-04-03 | `run-task.sh` を 5 回連続実行して成果物保存を検証（`logs/daily-driver-journal.md` 記録） | 5/5 で手動追加引数なし完走 | Step 4 完了、status を `done` へ更新 |
| 2026-04-03 | `resume-task.sh` で latest compact から recovery→handoff→再実行を確認 | `exit=0`、再開フローが成立 | Phase 9 `settle-2_context-reduction` へ移行 |
