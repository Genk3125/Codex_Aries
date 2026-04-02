# 次ターン入力テンプレート仕様

_Created: 2026-04-03_

compact_state JSON → Markdown 変換の固定フォーマット。

## テンプレート構造

```markdown
# Resume Context

## Status
- **現在の状態**: <current_status>
- **最終成功ステップ**: <last_successful_step>
- **失敗ステップ**: <failed_step.step> (exit_code: <failed_step.exit_code>)
- **停止理由**: <stop_reasons をカンマ区切り>

## Evidence Summary
- **実行コマンド数**: <executed_commands_summary.count>
- **ステップ数**: <actual_outputs_summary.total_steps> (成功: <succeeded_steps>, 失敗: <failed_steps の数>, スキップ: <skipped_steps の数>)

## Next Action
- **種別**: <next_action.type>
- **ヒント**: <next_action.hint>
- **アクション**:
  - <action_items の各項目>

## IDs
- team: <team_id>
- task: <task_id>
- member: <member_id>

## Meta
- run_id: <run_id>
- flow_mode: <flow_mode>
- mode: <strict|fail-open>
```

## 省略ルール

- `failed_step` が None の場合 → 行自体を省略
- `stop_reasons` が空の場合 → 「なし」と表示
- `action_items` が空の場合 → 「（なし — 次タスクへ進行）」と表示
- IDs の各フィールドが None の場合 → 「(未取得)」と表示

## 判断基準

人が読んで「次に何をすべきか」が 10 秒以内に判断できること。
