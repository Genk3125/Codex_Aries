# Context Compactor

`poc/context_compactor.py` は `runs/` に溜まった複数 run の `orch.json` を圧縮し、次ターン向けの固定フィールド compact state を生成する。

## 目的
- transcript 全文ではなく、`state / evidence index / next action` だけを残す。
- token 上限を超えやすい長時間 run で、再開判断に必要な情報を優先保存する。

## 入力 / 出力

```bash
python3 poc/context_compactor.py \
  --runs-dir runs \
  --max-context-tokens 4000 \
  --output-json runs/<run_id>/context-compacted.json \
  --output-markdown runs/<run_id>/context-compacted.md
```

- 入力: `runs/*/orch.json`
- 出力 JSON:
  - `compact_state.current_status`
  - `compact_state.last_successful_step`
  - `compact_state.failed_step`
  - `compact_state.stop_reasons`
  - `compact_state.executed_commands_summary`
  - `compact_state.actual_outputs_summary`
  - `compact_state.next_action`
  - `compact_state.ids`
  - `evidence_index.runs[]`

## サイズ方針
- `--max-context-tokens` は警告/短縮閾値。
- 超過時は optional 項目（command items / evidence runs / history）から削る。
- `failed_step`, `stop_reasons`, `next_action`, `ids` は保護する。

## daily-driver 統合
- `scripts/run-task.sh` は `orch.json` サイズが `--context-threshold-bytes` 以上なら自動実行。
- `scripts/resume-task.sh` は `context-compacted.json` を `compact.json` より優先して再開入力に使う。

