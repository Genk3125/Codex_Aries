# Recovery Next Helper

- Version: 0.1
- Date: 2026-04-03
- Target: `poc/recovery_next_helper.py`

## 1. 目的

`one_shot_orchestrator` の guard 結果を、`recovery-playbook.md` の分岐テンプレートへ即時マッピングし、  
停止後の人手判断を速くする。

## 2. スコープ

- 実施:
  - orchestrator 出力 JSON を入力に受ける
  - `preflight_guard` / `guard`（post-run）を読む
  - `stop_reasons` ごとに playbook 分岐へマッピングする
  - `guard_summary` と `recovery_next` を JSON 出力する
  - strict / fail-open を透過する
- 非実施:
  - gate 判定の再実装
  - verifier 判定の再実装
  - retry 実行
  - task update / send_message / reconcile の再実装

## 3. 責務分離

- guard:
  - 停止/継続/エスカレーションの判断主体
- recovery_next_helper:
  - stop reason を playbook 分岐に引くだけ
- recovery-playbook:
  - 実際の復旧行動（First Retry / Independent Verify / Escalate）の規律を定義

## 4. 実行手順

### A. preflight/post-run stop の次アクション抽出
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/recovery_next_helper.py \
  --input-json /tmp/runtime-preflight-manual-stop/out.json \
  --output-json /tmp/runtime-preflight-manual-stop/recovery-next.json
```

### B. strict（入力異常時に非0）
```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/poc/recovery_next_helper.py \
  --strict \
  --input-json /tmp/not-found.json \
  --output-json /tmp/recovery-next-strict.json
```
