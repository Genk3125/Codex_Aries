# RFC: Plan Mode Runtime Tools

- Status: Draft
- Version: 0.1
- Date: 2026-04-02
- Owner: Codex CLI Maximizer

## 1. 目的
model-callable な Plan Mode の開始/終了を明確化し、調査フェーズと実装フェーズを runtime で強制分離する。

## 2. スコープ

### In Scope
- `enter_plan_mode`
- `exit_plan_mode`
- approval
- existing collaboration mode（Default/Plan）との整合
- Team Runtime 連携

### Out of Scope
- UIデザイン詳細（文言・配色）
- Task自動生成ロジック
- Memory 抽出（Memory RFCへ委譲）

## 3. API 仕様

## 3.1 `enter_plan_mode`

### 入力
- `team_id?`
- `reason`
- `scope_hint?`（調査対象）
- `requires_approval: boolean`（既定 `true`）

### 効果
- write系 tool を runtime でブロック。
- plan artifact（仮: plan item list）作成を有効化。
- Team Runtime lifecycle に `planning` を付与。

## 3.2 `exit_plan_mode`

### 入力
- `team_id?`
- `approval_token?`
- `exit_to: "execute" | "idle"`

### 効果
- `execute` の場合のみ write unblock。
- `approval_token` 不一致時は exit 拒否。

## 4. Approval モデル
- 既定は `enter -> plan作成 -> approval -> exit(execute)` の順。
- approval は Message Bus の `approval_request/response` を利用。
- timeout 時は `needs_clarification` 扱いで execute へ進ませない。

## 5. 既存 collaboration mode との整合
- 現在の `Default`/`Plan` モードは UI/操作モード。
- 本RFCは runtime gate（write許可）を追加する層。
- 片方だけ Plan になっても不整合が起きないよう、優先順位は `runtime gate > UI mode` とする。

## 6. Team Runtime との関係
- team lifecycle 拡張: `active(planning)` / `active(executing)` を metadata で表現。
- member ごとに `can_write` フラグを持たず、team 単位で統一（初期設計）。
- verifier は常時 read-only なので plan mode の影響を受けない。

## 7. UI/runtime の衝突点
- UI が execute 表示でも runtime が plan gate なら write は拒否される。
- subagent が古い mode 情報を持つ場合、最初の write 時に runtime error を返す必要がある。
- approval 済みなのに token 伝播が遅延すると exit 失敗する。

## 8. 非対応にしたこと
- member 単位の部分的 write 解放。
- 自動 approval（policy engine）による無人昇格。
- 過去 plan からの自動差分実装。
