# RFC: Worktree Runtime Tools

- Status: Draft
- Version: 0.1
- Date: 2026-04-02
- Owner: Codex CLI Maximizer

## 1. 目的
model-callable な worktree 操作を標準化し、agent ごとの作業隔離を安全に実行できるようにする。

## 2. スコープ

### In Scope
- `enter_worktree`
- `exit_worktree`
- branch / path の扱い
- cleanup
- safety guard
- Team Runtime 連携

### Out of Scope
- 自動 merge / conflict 解決
- 複数repo横断の一括 worktree 管理
- 永続 scheduler（Trigger Layer RFC へ委譲）

## 3. API 仕様

## 3.1 `enter_worktree`

### 入力
- `team_id`
- `member_id`
- `repo_path`
- `branch_name?`（未指定時: `codex/team-{team_id}/{member_id}`）
- `base_ref?`（既定: 現在 branch HEAD）
- `mode: "create" | "attach"`

### 出力
- `worktree_path`
- `branch_name`
- `attached: boolean`

## 3.2 `exit_worktree`

### 入力
- `team_id`
- `member_id`
- `worktree_path`
- `cleanup_mode: "detach_only" | "delete_if_clean" | "force_delete"`

### 出力
- `detached: boolean`
- `deleted: boolean`
- `cleanup_notes`

## 4. branch / path 規約
- branch prefix: `codex/team-<team_id>/...`
- path prefix: `<repo>/.worktrees/<team_id>/<member_id>`
- Team Runtime の member metadata に `worktree_path` / `branch_name` を保存する。

## 5. Safety
- 既定で `delete_if_clean`。未コミット変更がある場合は削除拒否。
- `force_delete` は明示フラグ + control approval 必須。
- root workspace での直接編集は禁止（worktree へ誘導）。
- `team.status=deleting` 中は `enter_worktree` を拒否。

## 6. Cleanup
- 正常終了: `exit_worktree(delete_if_clean)` を呼び、metadata を消去。
- 異常終了: orphan worktree を startup reconcile で検知し回収候補化。
- 強制停止時: worktree は残しても team 状態は先に終了可能（fail-open cleanup）。

## 7. Team Runtime との関係
- `member.runtime_context.worktree` を単一真実源にする。
- member shutdown 時に `exit_worktree` を cleanup フローへ接続。
- Task owner が未使用 worktree を保持している場合は leader に警告。

## 8. 危険なケース
- 同一 branch を複数 member が attach する運用（履歴競合）。
- cleanup 中断で worktree path が再利用されるケース。
- force delete で未反映成果が消えるケース。
- branch 名衝突で誤 attach するケース。

## 9. 非対応にしたこと
- 自動 stash/unstash。
- 強制 cleanup 時の差分バックアップ生成。
- cross-team worktree 共有。
