# Baseline Results (Phase 16)

- Generated at: 2026-04-03T12:37:12.692774+00:00
- Source: `eval/tasks/manifest.json`

## Task Results

| Task | Size | Kind | Success | Attempts | Elapsed(sec) | Note |
|---|---|---|---|---:|---:|---|
| E01 | easy | orchestrator | yes | 1 | 0.534 | single pass |
| E02 | easy | orchestrator | yes | 1 | 0.522 | single pass |
| E03 | easy | orchestrator | yes | 1 | 0.526 | single pass |
| M01 | medium | orchestrator | yes | 1 | 0.595 | single pass |
| M02 | medium | orchestrator | yes | 1 | 0.597 | single pass |
| M03 | medium | orchestrator | yes | 1 | 0.596 | single pass |
| M04 | medium | team_runtime | yes | 1 | 0.038 | team runtime mvp scenario |
| H01 | hard | orchestrator | yes | 2 | 1.179 | strict failure + resume |
| H02 | hard | orchestrator | yes | 1 | 0.621 | single pass |
| H03 | hard | team_runtime | yes | 1 | 0.038 | team runtime mvp scenario |

## Metrics

| Metric | Value | Target |
|---|---:|---:|
| task_success_rate | 100.0% | >= 80% |
| first_valid_output_time | 0.564 sec | <= 300 sec |
| self_recovery_rate | 100.0% | >= 50% |
| rework_cycles_per_task | 0.1 | <= 2 |
| verification_pass_rate | 100.0% | >= 70% |
| team_completion_rate | 100.0% | >= 60% |

## Target Check

| Metric | Pass | Target |
|---|---|---|
| task_success_rate | yes | >= 80% |
| first_valid_output_time | yes | <= 300 sec |
| self_recovery_rate | yes | >= 50% |
| rework_cycles_per_task | yes | <= 2 |
| verification_pass_rate | yes | >= 70% |
| team_completion_rate | yes | >= 60% |

## Weak Points / Next Actions

- 目標未達の指標はなし。

## Notes

- 本ベースラインは single-pass kernel の現行実装を対象。
- strict 失敗から resume する recovery ケースを 1 本含む。
