# Team Runtime MVP (Phase 13)

## 実装方針
- `poc/` の Team Runtime 実装を `src/team_runtime/` へ昇格。
- `poc/codex_runtime_adapter.py` は `src.team_runtime` を優先 import（失敗時は旧 PoC import fallback）。
- runtime の責務は維持し、追加機能は入れない（MVP 境界固定）。

## 追加構成
- `src/team_runtime/control_plane.py`
- `src/team_runtime/message_bus.py`
- `src/team_runtime/task_bus.py`
- `src/team_runtime/runtime.py`
- `src/team_runtime/__init__.py`

## 3-member シナリオ確認

```bash
python3 /Users/kondogenki/AI\ Agent\ Maximizer/tests/e2e/team_runtime_mvp.py
```

このテストで確認すること:
- team create + 3 member add
- member owner 付き task create/update(done まで)
- leader -> member direct message delivery
- delete crash point (`deleting`) から startup reconcile で `deleted` へ回復

## 備考
- broadcast / approval / trigger / worktree は MVP 外。
- task 自動再割当と leader handoff も deferred のまま。

