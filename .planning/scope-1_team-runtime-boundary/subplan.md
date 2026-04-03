# Subplan: Team Runtime 本実装化境界の整理

## メタ情報

- **Phase ID**: `scope-1_team-runtime-boundary`
- **Master Flow 位置**: Scope（Phase 10）
- **依存先**: なし（独立着手可能、Phase 8-9 と並走可）
- **主対象ファイル**: `docs/rfc-agent-team-control-plane.md`, `docs/team-runtime-state-model.md`
- **アウトプット**: `.planning/scope-1_team-runtime-boundary/boundary-decision.md`
- **推定ワークロード**: 1 セッション
- **ステータス**: `not_started`

---

## 1. 目的

現在 `poc/` にある Team Runtime 関連コード（control_plane, message_bus, task_bus）の「どこまでが PoC で、どこからが本実装に持っていくか」の境界を決定する。

## 2. 背景・前提

- `poc/team_control_plane.py` (19,902 bytes), `poc/team_message_bus.py` (16,772 bytes), `poc/team_task_bus.py` (21,147 bytes) が既に存在
- これらは RFC に基づく PoC だが、orchestrator パイプラインとは未接続
- Codex の runtime-adapter (`~/.codex/runtime-adapter/codex-runtime`) との接続もまだ
- **決定すべきこと**: 本実装の scope, どの PoC を流用し何を捨てるか, runtime-adapter との接続方式

## 3. 具体的な作業ステップ

### Step 1: 既存 PoC の棚卸し

- 各 PoC ファイルの公開インターフェース（関数/クラス）を列挙
- Codex runtime-adapter が提供する operation 一覧と突き合わせ
- PoC と runtime-adapter の重複 / ギャップを特定

### Step 2: 本実装 scope の決定

判断基準:
- **In-scope**: orchestrator パイプラインから呼ばれ、日常運用に必須なもの
- **Out-of-scope**: RFC にはあるが日常運用に不要なもの（例: cron, remote trigger）
- **Defer**: 将来有用だが今は不要なもの

### Step 3: boundary-decision.md を作成

出力フォーマット:
```markdown
## In-Scope (Phase 13 で実装)
- team_create / team_delete
- task_create / task_get / task_update
- message_send / message_list
- 理由: ...

## Out-of-Scope (やらない)
- cron_create / cron_delete
- remote_trigger / sleep
- 理由: ...

## Deferred (将来)
- worktree enter/exit
- plan mode transitions
- 理由: ...
```

### Step 4: Phase 13 (team-runtime-mvp) の具体的 scope を確定

## 4. 完了判定（Exit Criteria）

- [ ] 既存 PoC の公開インターフェースが列挙されている
- [ ] runtime-adapter との重複/ギャップが特定されている
- [ ] In-Scope / Out-of-Scope / Deferred が明文化されている
- [ ] Phase 13 の入力として使える粒度で scope が確定している

## 5. リスク・注意

- scope を広げすぎると Phase 13 が巨大になる → MVPに絞る
- runtime-adapter の API が unstable な場合がある → adapter 側のバージョンを固定する

## 6. 実行ログ（着手後に記入）

| 日時 | 何をしたか | 結果 | 次アクション |
|------|-----------|------|-------------|
| | | | |
