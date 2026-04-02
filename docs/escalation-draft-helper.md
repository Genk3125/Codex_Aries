# Escalation Draft Helper

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/escalation_draft_helper.py`

## 1. 目的

`recovery_next_helper` の結果を受けて、escalation が必要な時だけ  
verifier / coordinator に渡す添付下書きを即時生成する。

## 2. スコープ

- 実施:
  - `one_shot_orchestrator` 出力 JSON と `recovery_next_helper` 出力 JSON を入力に受ける
  - escalation 不要なら skip を返す
  - escalation 必要なら `escalation_draft` を返す
  - 下書きには最低限以下を含める
    - `executed_commands`
    - `actual_outputs`（要約）
    - `failed_step`
    - `stop_reasons`
    - `suggested_next_action`
  - strict / fail-open を透過する
- 非実施:
  - guard 判定の再実装
  - verifier 判定の再実装
  - retry 実行
  - task update / send_message / reconcile の再実装
  - 自動送信

## 3. 責務分離

- `recovery_next_helper`:
  - stop reason を playbook 分岐に引く
- `escalation_draft_helper`:
  - 分岐が escalation 系なら添付材料を整形する
- playbook/coordinator/verifier:
  - 最終判断と実行を担当する

## 4. 実行手順

### A. escalation 必要時の下書き生成
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/escalation_draft_helper.py \
  --orchestrator-json /tmp/runtime-preflight-max-retries/out.json \
  --recovery-json /tmp/runtime-preflight-max-retries/recovery-next.json \
  --output-json /tmp/runtime-preflight-max-retries/escalation-draft.json
```

### B. escalation 不要時（skip）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/escalation_draft_helper.py \
  --orchestrator-json /tmp/runtime-preflight-manual-stop/out.json \
  --recovery-json /tmp/runtime-preflight-manual-stop/recovery-next.json \
  --output-json /tmp/runtime-preflight-manual-stop/escalation-draft.json
```

### C. strict（入力異常時に非0）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/escalation_draft_helper.py \
  --strict \
  --orchestrator-json /tmp/not-found-orch.json \
  --recovery-json /tmp/not-found-recovery.json \
  --output-json /tmp/escalation-draft-strict.json
```
