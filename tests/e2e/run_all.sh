#!/usr/bin/env bash
set -u -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_CMD="${PYTHON_CMD:-python3}"
TS="$(date '+%Y-%m-%dT%H-%M-%S')"
RESULTS_DIR="${ROOT_DIR}/tests/e2e/results/${TS}"
mkdir -p "${RESULTS_DIR}"

SUMMARY_JSON="${RESULTS_DIR}/summary.json"
SUMMARY_MD="${RESULTS_DIR}/summary.md"

PASS_COUNT=0
FAIL_COUNT=0
SCENARIOS=()

record_result() {
  local name="$1"
  local status="$2"
  local note="$3"
  local artifacts="$4"
  if [[ "${status}" == "PASS" ]]; then
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
  SCENARIOS+=("${name}|${status}|${note}|${artifacts}")
}

latest_run_dir() {
  local runs_root="$1"
  "${PYTHON_CMD}" - "${runs_root}" <<'PY'
import glob, os, sys
runs_root = sys.argv[1]
runs = [p for p in glob.glob(os.path.join(runs_root, "*")) if os.path.isdir(p)]
runs.sort(key=os.path.getmtime)
print(runs[-1] if runs else "")
PY
}

scenario_1_single_gate_success() {
  local name="S1_single_agent_gate_success"
  local runs_root="${RESULTS_DIR}/runs-s1"
  mkdir -p "${runs_root}"
  local log="${RESULTS_DIR}/${name}.log"

  if "${ROOT_DIR}/scripts/run-task.sh" --title "${name}" --flow gate --runs-root "${runs_root}" >"${log}" 2>&1; then
    local run_dir
    run_dir="$(latest_run_dir "${runs_root}")"
    local orch="${run_dir}/orch.json"
    local ok
    ok="$("${PYTHON_CMD}" - "${orch}" <<'PY'
import json, sys
obj = json.load(open(sys.argv[1], encoding="utf-8"))
print("true" if bool(obj.get("ok")) else "false")
PY
)"
    if [[ "${ok}" == "true" ]]; then
      record_result "${name}" "PASS" "gate flow completed" "${run_dir}"
      return 0
    fi
  fi
  record_result "${name}" "FAIL" "gate flow did not produce ok=true" "${log}"
  return 1
}

scenario_2_fail_then_resume() {
  local name="S2_fail_then_resume"
  local runs_root="${RESULTS_DIR}/runs-s2"
  mkdir -p "${runs_root}"
  local fail_log="${RESULTS_DIR}/${name}-fail.log"
  local resume_log="${RESULTS_DIR}/${name}-resume.log"

  set +e
  "${ROOT_DIR}/scripts/run-task.sh" \
    --title "${name}" \
    --flow gate \
    --strict \
    --gate-expected-task-state done \
    --runs-root "${runs_root}" >"${fail_log}" 2>&1
  local fail_exit=$?
  set -e

  if [[ ${fail_exit} -eq 0 ]]; then
    record_result "${name}" "FAIL" "expected strict failure did not occur" "${fail_log}"
    return 1
  fi

  if "${ROOT_DIR}/scripts/resume-task.sh" --runs-root "${runs_root}" >"${resume_log}" 2>&1; then
    record_result "${name}" "PASS" "strict failure recovered by resume flow" "${resume_log}"
    return 0
  fi

  record_result "${name}" "FAIL" "resume flow failed after strict stop" "${resume_log}"
  return 1
}

scenario_3_single_with_computer_use() {
  local name="S3_single_agent_computer_use"
  local runs_root="${RESULTS_DIR}/runs-s3"
  mkdir -p "${runs_root}"
  local log="${RESULTS_DIR}/${name}.log"
  local web_root="${RESULTS_DIR}/web-s3"
  mkdir -p "${web_root}"
  cat > "${web_root}/index.html" <<'EOF'
<html>
  <body>
    <h1>Phase15 Computer Use Scenario</h1>
    <p id="marker">computer-use evidence test</p>
  </body>
</html>
EOF

  python3 -m http.server 8771 --directory "${web_root}" >"${RESULTS_DIR}/${name}-http.log" 2>&1 &
  local server_pid=$!
  sleep 1

  local status=0
  if ! "${ROOT_DIR}/scripts/run-task.sh" \
    --title "${name}" \
    --flow gate \
    --runs-root "${runs_root}" \
    --computer-use-url "http://127.0.0.1:8771" >"${log}" 2>&1; then
    status=1
  fi
  kill "${server_pid}" >/dev/null 2>&1 || true
  wait "${server_pid}" 2>/dev/null || true

  if [[ ${status} -ne 0 ]]; then
    record_result "${name}" "FAIL" "run-task with computer-use failed" "${log}"
    return 1
  fi

  local run_dir
  run_dir="$(latest_run_dir "${runs_root}")"
  local orch="${run_dir}/orch.json"
  local cu_ok
  cu_ok="$("${PYTHON_CMD}" - "${orch}" <<'PY'
import json, sys
obj = json.load(open(sys.argv[1], encoding="utf-8"))
step = obj.get("results", {}).get("computer_use_helper", {})
print("true" if bool(step.get("ok")) else "false")
PY
)"
  if [[ "${cu_ok}" == "true" ]]; then
    record_result "${name}" "PASS" "computer_use evidence step succeeded" "${run_dir}"
    return 0
  fi

  record_result "${name}" "FAIL" "computer_use step missing or not ok" "${orch}"
  return 1
}

scenario_4_three_agent_team() {
  local name="S4_three_agent_team_runtime"
  local log="${RESULTS_DIR}/${name}.log"
  if "${PYTHON_CMD}" "${ROOT_DIR}/tests/e2e/team_runtime_mvp.py" >"${log}" 2>&1; then
    record_result "${name}" "PASS" "3-member team runtime scenario passed" "${log}"
    return 0
  fi
  record_result "${name}" "FAIL" "team runtime mvp scenario failed" "${log}"
  return 1
}

scenario_5_long_running_context_compaction() {
  local name="S5_long_running_context_compaction"
  local runs_root="${RESULTS_DIR}/runs-s5"
  mkdir -p "${runs_root}"
  local run_log="${RESULTS_DIR}/${name}-run.log"
  local resume_log="${RESULTS_DIR}/${name}-resume.log"

  if ! "${ROOT_DIR}/scripts/run-task.sh" \
    --title "${name}" \
    --flow chain \
    --runs-root "${runs_root}" \
    --context-threshold-bytes 1 \
    --context-max-tokens 1200 >"${run_log}" 2>&1; then
    record_result "${name}" "FAIL" "run-task failed before compaction check" "${run_log}"
    return 1
  fi

  local run_dir
  run_dir="$(latest_run_dir "${runs_root}")"
  if [[ ! -f "${run_dir}/context-compacted.json" ]]; then
    record_result "${name}" "FAIL" "context-compacted.json not generated" "${run_dir}"
    return 1
  fi

  if ! "${ROOT_DIR}/scripts/resume-task.sh" --runs-root "${runs_root}" >"${resume_log}" 2>&1; then
    record_result "${name}" "FAIL" "resume failed after context compaction" "${resume_log}"
    return 1
  fi

  if ! rg -Fq "context-compacted.json (preferred)" "${resume_log}"; then
    record_result "${name}" "FAIL" "resume did not prefer context-compacted.json" "${resume_log}"
    return 1
  fi

  record_result "${name}" "PASS" "context compaction + resume preference validated" "${run_dir}"
  return 0
}

set -e
scenario_1_single_gate_success || true
scenario_2_fail_then_resume || true
scenario_3_single_with_computer_use || true
scenario_4_three_agent_team || true
scenario_5_long_running_context_compaction || true

{
  echo "# E2E Integration Summary"
  echo ""
  echo "- Timestamp: ${TS}"
  echo "- Pass: ${PASS_COUNT}"
  echo "- Fail: ${FAIL_COUNT}"
  echo ""
  echo "| Scenario | Status | Note | Artifacts |"
  echo "|---|---|---|---|"
  for row in "${SCENARIOS[@]}"; do
    IFS="|" read -r name status note artifacts <<<"${row}"
    echo "| ${name} | ${status} | ${note} | \`${artifacts}\` |"
  done
} > "${SUMMARY_MD}"

{
  echo "{"
  echo "  \"timestamp\": \"${TS}\","
  echo "  \"pass_count\": ${PASS_COUNT},"
  echo "  \"fail_count\": ${FAIL_COUNT},"
  echo "  \"results\": ["
  first=1
  for row in "${SCENARIOS[@]}"; do
    IFS="|" read -r name status note artifacts <<<"${row}"
    if [[ ${first} -eq 0 ]]; then
      echo "    ,"
    fi
    first=0
    "${PYTHON_CMD}" - "$name" "$status" "$note" "$artifacts" <<'PY'
import json, sys
print("    " + json.dumps({
    "scenario": sys.argv[1],
    "status": sys.argv[2],
    "note": sys.argv[3],
    "artifacts": sys.argv[4],
}, ensure_ascii=False))
PY
  done
  echo "  ]"
  echo "}"
} > "${SUMMARY_JSON}"

echo "[e2e] results: ${SUMMARY_MD}"
if [[ ${FAIL_COUNT} -gt 0 ]]; then
  exit 1
fi
exit 0
