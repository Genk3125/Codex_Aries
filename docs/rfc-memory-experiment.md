# RFC: Memory Experiment (P2)

- Status: Draft (Experimental)
- Version: 0.1
- Date: 2026-04-02
- Owner: Codex CLI Maximizer

## 1. 目的
中核 runtime を汚染せずに、会話横断で有用な記憶を近似実装し効果を検証する。

## 2. なぜ P2 か
- Team Control Plane / Message / Task の基盤未確立段階で memory を中核化すると障害面積が増える。
- memory は品質向上要素だが、基盤が壊れると価値を出せない。
- 先に実行基盤を固め、memory は fail-open な追加層として検証するのが安全。

## 3. 設計方針
- **fail-open**: memory 読み書き失敗でも本処理は継続。
- **limited scope**: 保存対象を「再利用価値が高い構造化要点」に限定。
- **trigger point 明示**: 保存/参照タイミングを限定し副作用を抑える。
- **rollback 可能**: feature flag で即時無効化できる。

## 4. スコープ

### In Scope
- セッション終端での memory 抽出（要点のみ）
- 次回開始時の補助コンテキスト注入
- coordinator/verifier 実行メタ（成功/失敗パターン）

### Out of Scope（Non-Goals）
- 個人情報の広範保存
- 完全な長期会話再現
- memory への依存前提設計
- memory による意思決定自動化

## 5. データモデル（最小）

```json
{
  "memory_id": "mem_...",
  "scope": "project|team|agent",
  "kind": "decision|constraint|failure_pattern|verification_note",
  "summary": "short text",
  "evidence_ref": "log/artifact/path",
  "created_at": "ISO-8601",
  "expires_at": "optional"
}
```

## 6. Trigger Point
- write trigger: セッション終了時、または verifier 完了時。
- read trigger: 新規タスク開始時の plan フェーズ入口。
- update trigger: 同一 `kind+scope` の新証拠が出た場合のみ。

## 7. Rollback 戦略
- `memory_experiment_enabled=false` で全停止。
- 停止後は read/write を no-op 化。
- 既存 memory は削除せず inert 化（再有効化に備える）。

## 8. 失敗時の影響
- fail-open のため実行停止は起こさない。
- 想定影響は「文脈補助の劣化」「推奨精度の低下」に限定。
- 誤った memory 参照で方針が偏るリスクがあるため、evidence_ref を必須にする。

## 9. 運用評価
- memory あり/なしで plan 時間、retry 回数、verification PASS 率を比較。
- 誤参照率（不正確 memory が使われた回数）を追跡。

## 10. 非中核化の理由（再掲）
- runtime の可用性を最優先するため。
- memory が壊れても本体が動く設計を守るため。
- P2 で有効性が確認できた後に昇格判断するため。
