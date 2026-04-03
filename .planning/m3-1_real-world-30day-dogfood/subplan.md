# Subplan: real-world 30-day dogfood（Ship finalization）

## メタ情報

- **Phase ID**: `m3-1_real-world-30day-dogfood`
- **Master Flow 位置**: Milestone 3 / Phase 19
- **依存先**:
  - `ship-1_daily-dogfood-30days`（compressed validation 完了）
  - `ship-2_milestone-closeout`（provisional closeout 完了）
- **主対象ファイル**:
  - `logs/real-world-dogfood-30.md`
  - `.planning/MASTER_FLOW.md`
  - `ToDo.md`
  - `docs/milestone-2-closeout.md`
  - `.planning/ship-1_daily-dogfood-30days/subplan.md`
- **推定ワークロード**: 30 calendar days + 週次レビュー 4 回 + final 同期 1 セッション
- **ステータス**: `in_progress`
- **実行準備状態**: `ready_to_run`（2026-04-03 JST 時点）

---

## 1. 目的

Milestone 2 の Ship 判定を `provisional` から `final` に更新するため、real-world 日常運用の証跡を 30 calendar days 分で収集・評価する。

## 2. 背景・前提

- `logs/daily-dogfood-30.md` は **compressed 30 cycles の代替検証**であり、real-world 証跡ではない
- この subplan では `logs/real-world-dogfood-30.md` を唯一の運用証跡として扱う
- 新機能実装はしない。既存 runtime kernel（`run-task.sh` / `resume-task.sh` / adapter）を使う

## 3. 開始前に固定する運用パラメータ（今回確定）

### 3.1 Day 1 開始日
- Day 1: **2026-04-06 (JST)**
- Day 30: **2026-05-05 (JST)**

### 3.2 strict / fail-open 週内配分ルール
- 1 週間あたりの最低ライン:
  - `strict`: **2 日以上**
  - `fail-open`: **4 日以上**
  - `flex`: **1 日**（不足側に寄せる）
- 固定曜日ルール:
  - Mon: fail-open
  - Tue: fail-open
  - Wed: strict
  - Thu: fail-open
  - Fri: strict
  - Sat: fail-open
  - Sun: flex（原則 fail-open、週内 strict 未達時は strict）

| Weekday | Default Mode | Rule |
|---|---|---|
| Mon | fail-open | 固定 |
| Tue | fail-open | 固定 |
| Wed | strict | 固定 |
| Thu | fail-open | 固定 |
| Fri | strict | 固定 |
| Sat | fail-open | 固定 |
| Sun | flex | strict 未達時は strict、達成済みなら fail-open |

### 3.3 scenario 最低割当（30 日）
- `team-runtime`: 最低 3 日（固定割当: Day 8 / 16 / 24）
- `computer-use`: 最低 5 日（固定割当: Day 5 / 11 / 17 / 23 / 29）
- `recovery`: 最低 4 日（固定割当: Day 7 / 14 / 21 / 28）

| Scenario | Min Days | Fixed Days | Fixed Dates (JST) |
|---|---:|---|---|
| team-runtime | 3 | Day 8 / 16 / 24 | 2026-04-13 / 2026-04-21 / 2026-04-29 |
| computer-use | 5 | Day 5 / 11 / 17 / 23 / 29 | 2026-04-10 / 2026-04-16 / 2026-04-22 / 2026-04-28 / 2026-05-04 |
| recovery | 4 | Day 7 / 14 / 21 / 28 | 2026-04-12 / 2026-04-19 / 2026-04-26 / 2026-05-03 |

### 3.4 skipped 上限超過時の延長ルール
- 上限: `skipped <= 6`
- `skipped > 6` の場合:
  - Day 31 以降へ延長（1 skipped 超過につき +1 日）
  - 延長上限: +10 日（Day 40 まで）
  - Day 31-40 の日付窓: **2026-05-06 ～ 2026-05-15 (JST)**
- Day 40 までに条件未達なら `provisional継続 + 延長計画再定義` を記録

### 3.5 週次レビュー固定タイミング
- Day 7 checkpoint: **2026-04-12 20:30 JST**
- Day 14 checkpoint: **2026-04-19 20:30 JST**
- Day 21 checkpoint: **2026-04-26 20:30 JST**
- Day 28 checkpoint: **2026-05-03 20:30 JST**

## 4. 評価設計（定義固定）

### 4.1 日次ステータス
- `executed`: 当日タスク実行あり（成功/失敗は別）
- `skipped`: 当日実行なし（理由必須）
- `incident`: 実行を試みたが環境障害等で評価不能

### 4.2 手動介入レベル
- `L0`: 介入なし
- `L1`: 入力調整のみ（title/引数の軽微修正）
- `L2`: 運用介入（再実行・resume・手順切替）
- `L3`: 実装修正介入（コード/設定変更を伴う）

### 4.3 合否判定母数
- `calendar_days = 30`
- `executed_days = executed + incident`
- `success_rate = success_days / executed_days`
- `manual_free_ratio = L0_days / executed_days`

## 5. 具体的な作業ステップ

### Step 1: Day log テンプレート固定（完了）
- **対象**: `logs/real-world-dogfood-30.md`
- **やること**:
  - Day 1-30 の骨組みを固定
  - 週次レビュー Day 7/14/21/28 を固定
  - 記録項目（status/commands/artifacts/manual level/metrics flags）を固定
- **検証**: テンプレート生成済み、必須項目欠落なし

### Step 2: 30 calendar days 記録（未着手）
- **対象**: `scripts/run-task.sh`, `scripts/resume-task.sh`, `poc/codex_runtime_adapter.py`
- **やること**:
  - 各 calendar day に最低 1 レコード（executed/skipped/incident）
  - strict/fail-open 配分ルールを満たす
  - scenario 最低割当（team-runtime/computer-use/recovery）を満たす
- **検証**: 30 日分すべての Day セクションが埋まる

### Step 3: skipped 管理と延長判定（未着手）
- **対象**: `logs/real-world-dogfood-30.md`
- **やること**:
  - skipped 理由を限定列挙から記録
  - 連続 3 日超 skipped 時は週次レビューに是正計画を記録
  - skipped > 6 で延長窓（Day 31-40）に移行
- **検証**: skipped 理由漏れなし、延長条件の判定が明記される

### Step 4: 週次レビュー実施（未着手）
- **対象**: `logs/real-world-dogfood-30.md`
- **やること**:
  - Day 7/14/21/28 の固定時刻にレビュー
  - 失敗原因を `input_quality / runtime_limit / process_gap / environment` で分類
  - 次週ルールに反映
- **検証**: 4 回分レビューが埋まり、次週アクションが明記される

### Step 5: final 判定と closeout 接続（未着手）
- **対象**: `.planning/MASTER_FLOW.md`, `ToDo.md`, `docs/milestone-2-closeout.md`, `.planning/ship-1_daily-dogfood-30days/subplan.md`
- **やること**:
  - Pass: Milestone 2 Ship を `final` 化
  - Fail/保留: `provisional` 維持 + 延長期間と不足条件明記
- **検証**: 4 ファイルの status/文言が同一判定で同期される

## 6. デバッグ挿入ポイント

| 箇所 | 何を見るか | 挿入方法 |
|------|-----------|---------|
| `scripts/run-task.sh` | strict/fail-open の挙動差 | `orch.json` の `mode` / `ok` を日次記録 |
| `scripts/resume-task.sh` | recovery 成立率 | resume 実行有無と結果を Day log へ明記 |
| `logs/real-world-dogfood-30.md` | 記録漏れ・定義逸脱 | 週次で必須フィールド欠損チェック |
| `poc/codex_runtime_adapter.py` | team-runtime 実行可能性 | `team_create/task_create/send_message` 最低1回を週次確認 |

## 7. 完了判定（Exit Criteria）

### 7.1 Step 1 完了（達成済み）
- [x] Day 1 開始日を固定した
- [x] strict / fail-open 週内配分ルールを固定した
- [x] team-runtime 3 日、computer-use 5 日、recovery 4 日の最低割当を固定した
- [x] skipped 超過時の延長ルール（Day 31-40）を固定した
- [x] Day 7/14/21/28 の週次レビュー実施時刻を固定した
- [x] テンプレートへ記録項目を反映した

### 7.2 Phase 19 完了（未達）
- [ ] `logs/real-world-dogfood-30.md` に 30 calendar days の実績記録がある
- [ ] `executed_days >= 24`（最大 skipped 6）
- [ ] `success_rate >= 80%`（母数: executed_days）
- [ ] `manual_free_ratio >= 50%`（母数: executed_days）
- [ ] `computer-use` 実施日が 5 日以上
- [ ] `team-runtime` 実施日が 3 日以上
- [ ] 週次レビュー 4 回（Day 7/14/21/28）が完了
- [ ] Milestone 2 判定が `final` または `provisional継続+延長計画` のどちらかで明記され、4 ファイル同期が完了

## 8. リスク・注意

- 実運用は外部要因で乱れるため、「未実行日を隠さない」ことを最優先にする
- fail-open に寄りすぎると実運用の難所が見えないため、strict 日を計画的に入れる
- このフェーズは運用証跡の取得が目的。新しい helper 実装は入れない

## 9. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| 2026-04-03 | Step 1 として `logs/real-world-dogfood-30.md` の Day 1-30 テンプレートと週次レビュー枠を作成 | 記録項目を固定し、運用開始前の土台を確立 | 2026-04-06（Day 1）から Step 2 を開始 |
| | | | |
