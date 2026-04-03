# Agent Install and Runbook

- Version: 0.1
- Date: 2026-04-02
- Owner: Codex CLI Maximizer

## 1. 目的
`AGENTS.md` / `coordinator.toml` / `verifier.toml` / `verifier-contract.md` を実運用に載せる手順を標準化する。

## 2. 配置先
- `AGENTS.md`: `<repo-root>/AGENTS.md`（repo ルート）
- **repo-local custom agents（推奨）**:
  - `<repo-root>/.codex/agents/coordinator.toml`
  - `<repo-root>/.codex/agents/verifier.toml`
- **user-global custom agents（個人共通）**:
  - `/Users/kondogenki/.codex/agents/coordinator.toml`
  - `/Users/kondogenki/.codex/agents/verifier.toml`
- verifier 契約:
  - `<repo-root>/verifier-contract.md`
- runtime shared contract（Phase 20-22）:
  - `<repo-root>/docs/runtime-shared-contract.md`
  - `<repo-root>/docs/schemas/runtime-shared-contract.v1.json`

## 3. repo-local と user-global の使い分け
- repo-local: プロジェクト固有の役割定義をチームで共有したい場合に使う（Git 管理対象）。
- user-global: 個人の全プロジェクト共通設定として使う。
- 同名 agent を両方に置くと運用が混乱しやすい。初期運用ではどちらか片方に寄せる。

## 4. 読み込み確認
1. Codex セッションを再起動する（配置前セッションのキャッシュを避ける）。
2. `AGENTS.md` が適用されていることを確認する。
3. `coordinator` を起動し、短い合成タスクを実行できることを確認する。
4. `verifier` を起動し、read-only 検証タスクを実行できることを確認する。

## 5. 最小の起動確認手順
1. coordinator へ「2件の調査結果を統合して3行で要約」を依頼する。
2. verifier へ「変更なしで検証観点だけ列挙」を依頼する。
3. verifier 出力に `PASS/PARTIAL/FAIL`、`実行コマンド`、`実出力`、`未検証項目` が含まれることを確認する。

## 6. verifier contract の参照方法
- verifier system prompt に `<repo-root>/verifier-contract.md` を必読として明示する。
- 判定時は契約の章立て順（Verdict → Commands → Outputs → Unverified → Risk → Next）を強制する。
- 契約不一致の出力は無効とし再提出する。

## 6.1 shared contract の参照方法（Phase 20-22）
- Trigger / Worktree / Verifier Queue 実装前に `docs/runtime-shared-contract.md` を参照する。
- operation 名、store layout、schema version、idempotency 形式、strict/fail-open は shared contract を正本とする。

## 7. 初回運用手順（推奨）
1. Plan モードで coordinator が実施計画を作成。
2. Execute モードへ遷移し実装担当が変更を実施。
3. verifier が read-only 検証し verdict を提出。
4. coordinator が verdict を統合し、未解決を次タスク化。

## 8. トラブル時の切り分け
- **読み込みされない**: `/.codex/agents/` 配置誤り、ファイル名誤り、セッション再起動不足を確認。
- **役割が混ざる**: coordinator/verifier prompt の責務境界を再確認。
- **verifierが書き込みする**: read-only 制約設定漏れを確認。
- **契約逸脱**: `verifier-contract.md` の参照漏れまたはテンプレート未適用を確認。
- **判定不安定**: 実行コマンド不足、実出力不足、未検証項目未記載を点検。

## 9. まだ手動な部分
- custom agent TOML の配置とセッション再起動。
- coordinator/verifier 起動時の role 選択。
- verifier 契約準拠チェック（自動 lint 未整備）。
- 失敗分類の最終判断（人のレビュー依存）。

## 10. 最初に確認すべきこと
- custom agents が `/.codex/agents/` 配下にあるか。
- `AGENTS.md` の適用スコープが対象ディレクトリか。
- verifier が read-only で動作しているか。
- 検証結果に「未検証項目」が明示されているか。
