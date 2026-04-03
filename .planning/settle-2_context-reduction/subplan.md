# Subplan: context reduction 強化

## メタ情報

- **Phase ID**: `settle-2_context-reduction`
- **Master Flow 位置**: Settle（Phase 9）
- **依存先**: Phase 8（daily-driver で日常使用データが溜まっていること）
- **主対象ファイル**: `poc/compact_state_helper.py`, 新規 `poc/context_compactor.py`
- **推定ワークロード**: 2 セッション
- **ステータス**: `not_started`

---

## 1. 目的

transcript（会話全文）ではなく **state / evidence / next-actions** だけを残す context reduction を実装し、長時間タスクでもコンテキストが膨張しない仕組みを作る。

## 2. 背景・前提

- compact_state は orchestrator 出力 JSON を圧縮するが、会話全体のコンテキストは圧縮しない
- Codex の `/compact` は組み込みだが、何を残すかの制御ができない
- **目標**: orchestrator の N ターン分の蓄積を「最新 state + evidence index + next-actions」に不可逆圧縮し、次ターンに渡す

## 3. 具体的な作業ステップ

### Step 1: Phase 8 の daily-driver 使用ログから context 膨張パターンを分析

- `runs/` の orchestrator 出力をサイズ順にソートし、膨張が起きるパターンを特定
- 特に「何が不要か」を列挙する

### Step 2: context_compactor のインターフェース設計

```bash
python3 poc/context_compactor.py \
  --runs-dir runs/ \
  --max-context-tokens 4000 \
  --output-json /tmp/compacted-context.json \
  --output-markdown /tmp/compacted-context.md
```

### Step 3: 圧縮戦略の実装

- **残すもの**: current_status, failed_step, stop_reasons, next_action, ids, 直近のエビデンス要約
- **捨てるもの**: 中間 helper の stdout/stderr 全文、成功したステップの詳細、重複する JSON キー
- **トークン予算**: 出力を最大 4,000 トークン（約 3,000 文字）に制限

### Step 4: 既存 compact_state の出力と context_compactor を連結テスト

## 4. 完了判定（Exit Criteria）

- [ ] context_compactor が N ターン分の runs/ を入力として受け取り、4,000 トークン以内の要約を出力する
- [ ] 圧縮後の要約を読んで、次アクションが 10 秒以内に判断可能（now-1 と同じ基準）
- [ ] daily-driver ジャーナルに「context 膨張で困った」が出なくなる

## 5. リスク・注意

- 不可逆圧縮は情報ロスのリスクがある → evidence index（参照パス）を必ず残すことで softlink を提供
- 圧縮対象の判断を誤ると重要な失敗情報を捨てる → failed_step 関連は常に保護

## 6. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
