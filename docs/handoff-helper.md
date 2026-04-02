# Handoff Helper

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/handoff_helper.py`

## 1. 目的

`escalation_draft_helper` の出力を受け、  
verifier / coordinator へ渡す handoff 材料を JSON（任意で Markdown）に整形する。

## 2. スコープ

- 実施:
  - `escalation_draft_helper` 出力 JSON を入力に受ける
  - handoff 不要なら skip を返す
  - handoff 必要時は verifier/coordinator 向け下書きを返す
  - 最低限以下を出力する
    - `summary`
    - `failed_step`
    - `stop_reasons`
    - `executed_commands`
    - `actual_outputs_summary`
    - `suggested_next_action`
  - strict / fail-open を透過する
  - `--strict` 指定時は入力 mode に関わらず strict で扱う
- 非実施:
  - guard 判定の再実装
  - verifier 判定の再実装
  - retry 実行
  - task update / send_message / reconcile の再実装
  - 自動送信

## 3. 責務分離

- `escalation_draft_helper`:
  - escalation 添付材料を抽出する
- `handoff_helper`:
  - その材料を handoff フォーマットに整形する
- verifier/coordinator:
  - 最終判断・実行を行う

## 4. 実行手順

### A. stop/escalation ケース（handoff 生成）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/handoff_helper.py \
  --escalation-draft-json /tmp/runtime-preflight-max-retries/escalation-draft.json \
  --output-json /tmp/runtime-preflight-max-retries/handoff.json \
  --output-markdown /tmp/runtime-preflight-max-retries/handoff.md
```

### B. no-op ケース（skip）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/handoff_helper.py \
  --escalation-draft-json /tmp/runtime-preflight-manual-stop/escalation-draft.json \
  --output-json /tmp/runtime-preflight-manual-stop/handoff.json
```

### C. strict（入力異常時に非0）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/handoff_helper.py \
  --strict \
  --escalation-draft-json /tmp/not-found-escalation.json \
  --output-json /tmp/handoff-strict.json
```
