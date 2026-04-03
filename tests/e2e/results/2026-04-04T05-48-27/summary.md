# E2E Integration Summary

- Timestamp: 2026-04-04T05-48-27
- Pass: 3
- Fail: 2

| Scenario | Status | Note | Artifacts |
|---|---|---|---|
| S1_single_agent_gate_success | FAIL | gate flow did not produce ok=true | `/Users/kondogenki/Codex_Aries/tests/e2e/results/2026-04-04T05-48-27/S1_single_agent_gate_success.log` |
| S2_fail_then_resume | PASS | strict failure recovered by resume flow | `/Users/kondogenki/Codex_Aries/tests/e2e/results/2026-04-04T05-48-27/S2_fail_then_resume-resume.log` |
| S3_single_agent_computer_use | PASS | computer_use evidence step succeeded | `/Users/kondogenki/Codex_Aries/tests/e2e/results/2026-04-04T05-48-27/runs-s3/2026-04-04T05-48-29` |
| S4_three_agent_team_runtime | PASS | 3-member team runtime scenario passed | `/Users/kondogenki/Codex_Aries/tests/e2e/results/2026-04-04T05-48-27/S4_three_agent_team_runtime.log` |
| S5_long_running_context_compaction | FAIL | resume did not prefer context-compacted.json | `/Users/kondogenki/Codex_Aries/tests/e2e/results/2026-04-04T05-48-27/S5_long_running_context_compaction-resume.log` |
