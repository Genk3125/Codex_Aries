# Coordinator Plan (Experiment 2026-04-03)

## Plan Steps (ordered)
1. Investigate baseline (read-only): confirm runtime components and IDs, define experiment run id.
2. `team-create`: create ephemeral team and record `team_id`.
3. `task-create`: create bounded orchestration task with explicit expected artifacts.
4. `send-message`: send kickoff message tied to task id and require ack payload.
5. Minimal implementation change (single file): one reversible tiny change only.
6. Verifier handoff: provide `team_id`, `task_id`, changed file, required checks.
7. `reconcile-all`: run startup-style reconcile to confirm no state drift.

## Assumptions
- Runtime adapter operations are available and configured.
- Coordinator and verifier roles already exist.
- Minimal change is single-file and reversible.
- This plan is synthesis-only; no implementation or verification in this step.

## Exit Criteria
- Valid `team_id` from `team-create`.
- Valid `task_id` linked to the team.
- At least one `send-message` recorded.
- Exactly one minimal implementation change scoped.
- Verifier handoff payload prepared.
- `reconcile-all` executed with no unresolved drift.
