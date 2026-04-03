# Auto Context Pipeline (Phase 14)

## 目的
`run-task.sh` / `resume-task.sh` に context compaction を直結し、膨張時の圧縮を自動化する。

## 実装点

### `scripts/run-task.sh`
- `--context-threshold-bytes` を追加（default: `51200`）
- `--context-max-tokens` を追加（default: `4000`）
- `--disable-context-compactor` を追加
- `orch.json` が閾値超過のときのみ `poc/context_compactor.py` を自動実行
- 出力:
  - `context-compacted.json`
  - `context-compacted.md`

### `scripts/resume-task.sh`
- 最新入力の自動選択順:
  1. `runs/*/context-compacted.json`
  2. `runs/*/compact.json`
- 同一 run 内で両方存在する場合は、`context-compacted.json` 優先を明示ログで通知

## 最小動作確認

```bash
./scripts/run-task.sh \
  --title "phase14-auto-context-check" \
  --context-threshold-bytes 1

./scripts/resume-task.sh
```

