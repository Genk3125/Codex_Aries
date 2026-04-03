#!/usr/bin/env bash
set -u -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_CMD="${PYTHON_CMD:-python3}"

FLOW_MODE="gate"
STRICT_MODE=0
TITLE=""
TEAM_NAME=""
MEMBER_ID="${DAILY_DRIVER_MEMBER_ID:-worker_daily_driver}"
NOTIFY_MEMBER_ID=""
BOOTSTRAP_MESSAGE=""
TASK_UPDATE_STATE="in_progress"
TASK_UPDATE_MESSAGE="task moved to in_progress"
TASK_UPDATE_BLOCKED_REASON=""
TASK_UPDATE_RESULT_REFERENCE=""
GATE_EXPECTED_TASK_STATE=""
BRIDGE_MESSAGE="verifier gate triggered; task moved to blocked"
VERIFIER_CMD=""
COMPUTER_USE_URL=""
COMPUTER_USE_OPERATION="both"
COMPUTER_USE_TIMEOUT_SEC=20
COMPUTER_USE_TIMEOUT_MS=15000
COMPUTER_USE_OUTPUT_DIR=""
COMPUTER_USE_SCREENSHOT_PATH=""
RUNS_ROOT="${ROOT_DIR}/runs"
STORE_ROOT=""
RUN_ID=""
CONTEXT_THRESHOLD_BYTES=51200
CONTEXT_MAX_TOKENS=4000
ENABLE_CONTEXT_COMPACTOR=1

print_help() {
  cat <<'EOF'
Usage:
  ./scripts/run-task.sh --title "task title" [options]

Options:
  --title <text>                  Required task title
  --flow <gate|chain>             Flow mode (default: gate)
  --strict                        Strict mode (default: fail-open)
  --team-name <name>              Team name override
  --member-id <id>                Member id (default: worker_daily_driver)
  --notify-member-id <id>         Notify target (default: member-id)
  --bootstrap-message <text>      Bootstrap message override
  --task-update-state <state>     task_update state (default: in_progress)
  --task-update-message <text>    task_update message
  --task-update-blocked-reason <text>
  --task-update-result-reference <ref>
  --gate-expected-task-state <state>
  --bridge-message <text>
  --verifier-cmd <cmd>
  --computer-use-url <url>        Optional evidence URL for computer_use_helper
  --computer-use-operation <mode> screenshot|extract_text|both (default: both)
  --computer-use-timeout-sec <n>  URL fetch timeout (default: 20)
  --computer-use-timeout-ms <n>   Browser timeout for screenshot (default: 15000)
  --computer-use-output-dir <path>
  --computer-use-screenshot-path <path>
  --runs-root <path>              Runs root (default: <repo>/runs)
  --store-root <path>             Runtime store root (default: <run_dir>/store)
  --run-id <id>                   Fixed run id (default: timestamp)
  --context-threshold-bytes <n>   Auto compact trigger threshold for orch.json (default: 51200)
  --context-max-tokens <n>        Context compactor token budget (default: 4000)
  --disable-context-compactor     Disable auto context compaction
  -h, --help                      Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)
      TITLE="$2"
      shift 2
      ;;
    --flow)
      FLOW_MODE="$2"
      shift 2
      ;;
    --strict)
      STRICT_MODE=1
      shift
      ;;
    --team-name)
      TEAM_NAME="$2"
      shift 2
      ;;
    --member-id)
      MEMBER_ID="$2"
      shift 2
      ;;
    --notify-member-id)
      NOTIFY_MEMBER_ID="$2"
      shift 2
      ;;
    --bootstrap-message)
      BOOTSTRAP_MESSAGE="$2"
      shift 2
      ;;
    --task-update-state)
      TASK_UPDATE_STATE="$2"
      shift 2
      ;;
    --task-update-message)
      TASK_UPDATE_MESSAGE="$2"
      shift 2
      ;;
    --task-update-blocked-reason)
      TASK_UPDATE_BLOCKED_REASON="$2"
      shift 2
      ;;
    --task-update-result-reference)
      TASK_UPDATE_RESULT_REFERENCE="$2"
      shift 2
      ;;
    --gate-expected-task-state)
      GATE_EXPECTED_TASK_STATE="$2"
      shift 2
      ;;
    --bridge-message)
      BRIDGE_MESSAGE="$2"
      shift 2
      ;;
    --verifier-cmd)
      VERIFIER_CMD="$2"
      shift 2
      ;;
    --computer-use-url)
      COMPUTER_USE_URL="$2"
      shift 2
      ;;
    --computer-use-operation)
      COMPUTER_USE_OPERATION="$2"
      shift 2
      ;;
    --computer-use-timeout-sec)
      COMPUTER_USE_TIMEOUT_SEC="$2"
      shift 2
      ;;
    --computer-use-timeout-ms)
      COMPUTER_USE_TIMEOUT_MS="$2"
      shift 2
      ;;
    --computer-use-output-dir)
      COMPUTER_USE_OUTPUT_DIR="$2"
      shift 2
      ;;
    --computer-use-screenshot-path)
      COMPUTER_USE_SCREENSHOT_PATH="$2"
      shift 2
      ;;
    --runs-root)
      RUNS_ROOT="$2"
      shift 2
      ;;
    --store-root)
      STORE_ROOT="$2"
      shift 2
      ;;
    --run-id)
      RUN_ID="$2"
      shift 2
      ;;
    --context-threshold-bytes)
      CONTEXT_THRESHOLD_BYTES="$2"
      shift 2
      ;;
    --context-max-tokens)
      CONTEXT_MAX_TOKENS="$2"
      shift 2
      ;;
    --disable-context-compactor)
      ENABLE_CONTEXT_COMPACTOR=0
      shift
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    *)
      echo "[run-task] unknown option: $1" >&2
      print_help >&2
      exit 2
      ;;
  esac
done

if [[ -z "${TITLE}" ]]; then
  echo "[run-task] --title is required" >&2
  exit 2
fi

if [[ "${FLOW_MODE}" != "gate" && "${FLOW_MODE}" != "chain" ]]; then
  echo "[run-task] --flow must be gate or chain" >&2
  exit 2
fi
if [[ "${COMPUTER_USE_OPERATION}" != "screenshot" && "${COMPUTER_USE_OPERATION}" != "extract_text" && "${COMPUTER_USE_OPERATION}" != "both" ]]; then
  echo "[run-task] --computer-use-operation must be screenshot|extract_text|both" >&2
  exit 2
fi

if [[ -z "${RUN_ID}" ]]; then
  RUN_ID="$(date '+%Y-%m-%dT%H-%M-%S')"
fi
BASE_RUN_ID="${RUN_ID}"
SEQ=1
while [[ -e "${RUNS_ROOT}/${RUN_ID}" ]]; do
  RUN_ID="${BASE_RUN_ID}-$(printf '%02d' "${SEQ}")"
  SEQ=$((SEQ + 1))
done
RUN_DIR="${RUNS_ROOT}/${RUN_ID}"
WORK_DIR="${RUN_DIR}/work"
mkdir -p "${RUN_DIR}" "${WORK_DIR}"

if [[ -z "${NOTIFY_MEMBER_ID}" ]]; then
  NOTIFY_MEMBER_ID="${MEMBER_ID}"
fi
if [[ -z "${BOOTSTRAP_MESSAGE}" ]]; then
  BOOTSTRAP_MESSAGE="daily-driver start: ${TITLE}"
fi

if [[ -z "${TEAM_NAME}" ]]; then
  TEAM_SLUG="$(echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-*//;s/-*$//' | cut -c1-24)"
  if [[ -z "${TEAM_SLUG}" ]]; then
    TEAM_SLUG="daily-driver"
  fi
  TEAM_NAME="team-${TEAM_SLUG}"
fi

if [[ -z "${STORE_ROOT}" ]]; then
  STORE_ROOT="${RUN_DIR}/store"
fi

ORCH_JSON="${RUN_DIR}/orch.json"
COMPACT_JSON="${RUN_DIR}/compact.json"
COMPACT_MD="${RUN_DIR}/compact.md"
CONTEXT_COMPACT_JSON="${RUN_DIR}/context-compacted.json"
CONTEXT_COMPACT_MD="${RUN_DIR}/context-compacted.md"
RECOVERY_JSON="${RUN_DIR}/recovery-next.json"
ESCALATION_JSON="${RUN_DIR}/escalation-draft.json"
HANDOFF_JSON="${RUN_DIR}/handoff.json"
HANDOFF_MD="${RUN_DIR}/handoff.md"
NOTIFY_JSON="${RUN_DIR}/notify.json"
NOTIFY_TXT="${RUN_DIR}/notify.txt"
CONTEXT_COMPACT_EXIT=0
CONTEXT_COMPACT_TRIGGERED=0

ORCH_CMD=(
  "${PYTHON_CMD}" "${ROOT_DIR}/poc/one_shot_orchestrator.py"
  --flow-mode "${FLOW_MODE}"
  --team-name "${TEAM_NAME}"
  --member-id "${MEMBER_ID}"
  --notify-member-id "${NOTIFY_MEMBER_ID}"
  --task-title "${TITLE}"
  --bootstrap-message "${BOOTSTRAP_MESSAGE}"
  --task-update-state "${TASK_UPDATE_STATE}"
  --task-update-message "${TASK_UPDATE_MESSAGE}"
  --bridge-message "${BRIDGE_MESSAGE}"
  --store-root "${STORE_ROOT}"
  --work-dir "${WORK_DIR}"
  --guard-state-json "${RUN_DIR}/guard-state.json"
  --output-json "${ORCH_JSON}"
)

if [[ ${STRICT_MODE} -eq 1 ]]; then
  ORCH_CMD+=(--strict)
fi
if [[ -n "${TASK_UPDATE_BLOCKED_REASON}" ]]; then
  ORCH_CMD+=(--task-update-blocked-reason "${TASK_UPDATE_BLOCKED_REASON}")
fi
if [[ -n "${TASK_UPDATE_RESULT_REFERENCE}" ]]; then
  ORCH_CMD+=(--task-update-result-reference "${TASK_UPDATE_RESULT_REFERENCE}")
fi
if [[ -n "${GATE_EXPECTED_TASK_STATE}" ]]; then
  ORCH_CMD+=(--gate-expected-task-state "${GATE_EXPECTED_TASK_STATE}")
fi
if [[ -n "${VERIFIER_CMD}" ]]; then
  ORCH_CMD+=(--verifier-cmd "${VERIFIER_CMD}")
fi
if [[ -n "${COMPUTER_USE_URL}" ]]; then
  ORCH_CMD+=(--computer-use-url "${COMPUTER_USE_URL}")
  ORCH_CMD+=(--computer-use-operation "${COMPUTER_USE_OPERATION}")
  ORCH_CMD+=(--computer-use-timeout-sec "${COMPUTER_USE_TIMEOUT_SEC}")
  ORCH_CMD+=(--computer-use-timeout-ms "${COMPUTER_USE_TIMEOUT_MS}")
fi
if [[ -n "${COMPUTER_USE_OUTPUT_DIR}" ]]; then
  ORCH_CMD+=(--computer-use-output-dir "${COMPUTER_USE_OUTPUT_DIR}")
fi
if [[ -n "${COMPUTER_USE_SCREENSHOT_PATH}" ]]; then
  ORCH_CMD+=(--computer-use-screenshot-path "${COMPUTER_USE_SCREENSHOT_PATH}")
fi

echo "[run-task] run_dir=${RUN_DIR}"
echo "[run-task] executing orchestrator..."
"${ORCH_CMD[@]}"
ORCH_EXIT=$?

echo "[run-task] compacting state..."
"${PYTHON_CMD}" "${ROOT_DIR}/poc/compact_state_helper.py" \
  --orchestrator-json "${ORCH_JSON}" \
  --output-json "${COMPACT_JSON}" \
  --output-markdown "${COMPACT_MD}" >/dev/null
COMPACT_EXIT=$?

if [[ ${ENABLE_CONTEXT_COMPACTOR} -eq 1 && -f "${ORCH_JSON}" ]]; then
  ORCH_SIZE_BYTES="$("${PYTHON_CMD}" - "${ORCH_JSON}" <<'PY'
import sys
from pathlib import Path
print(Path(sys.argv[1]).stat().st_size)
PY
)"
  if [[ "${ORCH_SIZE_BYTES}" =~ ^[0-9]+$ ]] && [[ "${ORCH_SIZE_BYTES}" -ge "${CONTEXT_THRESHOLD_BYTES}" ]]; then
    CONTEXT_COMPACT_TRIGGERED=1
    echo "[run-task] context threshold exceeded (${ORCH_SIZE_BYTES} >= ${CONTEXT_THRESHOLD_BYTES}), running context_compactor..."
    "${PYTHON_CMD}" "${ROOT_DIR}/poc/context_compactor.py" \
      --runs-dir "${RUNS_ROOT}" \
      --max-context-tokens "${CONTEXT_MAX_TOKENS}" \
      --output-json "${CONTEXT_COMPACT_JSON}" \
      --output-markdown "${CONTEXT_COMPACT_MD}" >/dev/null
    CONTEXT_COMPACT_EXIT=$?
  fi
fi

ORCH_OK="false"
if [[ -f "${ORCH_JSON}" ]]; then
  ORCH_OK="$("${PYTHON_CMD}" - "${ORCH_JSON}" <<'PY'
import json, sys
path = sys.argv[1]
obj = json.load(open(path, encoding="utf-8"))
print("true" if bool(obj.get("ok")) else "false")
PY
)"
fi

if [[ "${ORCH_OK}" != "true" ]]; then
  echo "[run-task] run not ok; notifying..."
  "${PYTHON_CMD}" "${ROOT_DIR}/poc/notify_helper.py" \
    --input-json "${ORCH_JSON}" \
    --output-file "${NOTIFY_TXT}" \
    --output-json "${NOTIFY_JSON}" >/dev/null
else
  echo "(no notifications)" > "${NOTIFY_TXT}"
fi

if [[ -f "${COMPACT_JSON}" ]]; then
  "${PYTHON_CMD}" "${ROOT_DIR}/poc/recovery_next_helper.py" \
    --from-compact "${COMPACT_JSON}" \
    --output-json "${RECOVERY_JSON}" >/dev/null || true
fi

if [[ -f "${RECOVERY_JSON}" ]]; then
  "${PYTHON_CMD}" "${ROOT_DIR}/poc/escalation_draft_helper.py" \
    --orchestrator-json "${ORCH_JSON}" \
    --recovery-json "${RECOVERY_JSON}" \
    --output-json "${ESCALATION_JSON}" >/dev/null || true
fi

if [[ -f "${ESCALATION_JSON}" ]]; then
  "${PYTHON_CMD}" "${ROOT_DIR}/poc/handoff_helper.py" \
    --escalation-draft-json "${ESCALATION_JSON}" \
    --output-json "${HANDOFF_JSON}" \
    --output-markdown "${HANDOFF_MD}" >/dev/null || true
fi

echo "[run-task] artifacts:"
echo "  - ${ORCH_JSON}"
echo "  - ${COMPACT_JSON}"
echo "  - ${COMPACT_MD}"
if [[ ${CONTEXT_COMPACT_TRIGGERED} -eq 1 ]]; then
  echo "  - ${CONTEXT_COMPACT_JSON}"
  echo "  - ${CONTEXT_COMPACT_MD}"
fi
echo "  - ${NOTIFY_TXT}"
if [[ -f "${HANDOFF_MD}" ]]; then
  echo "  - ${HANDOFF_MD}"
fi

if [[ ${STRICT_MODE} -eq 1 ]]; then
  if [[ ${ORCH_EXIT} -ne 0 ]]; then
    exit "${ORCH_EXIT}"
  fi
  if [[ ${COMPACT_EXIT} -ne 0 ]]; then
    exit "${COMPACT_EXIT}"
  fi
  if [[ ${CONTEXT_COMPACT_TRIGGERED} -eq 1 && ${CONTEXT_COMPACT_EXIT} -ne 0 ]]; then
    exit "${CONTEXT_COMPACT_EXIT}"
  fi
fi
exit 0
