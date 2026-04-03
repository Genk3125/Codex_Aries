#!/usr/bin/env bash
set -u -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_CMD="${PYTHON_CMD:-python3}"

RUNS_ROOT="${ROOT_DIR}/runs"
SOURCE_COMPACT=""
STRICT_MODE=0
TITLE_OVERRIDE=""
FLOW_OVERRIDE=""
MEMBER_OVERRIDE=""
TEAM_OVERRIDE=""
NOTIFY_MEMBER_OVERRIDE=""
STORE_ROOT_OVERRIDE=""
CARRY_GATE_EXPECTED=0

print_help() {
  cat <<'EOF'
Usage:
  ./scripts/resume-task.sh [options]

Options:
  --compact-json <path>           Source compact/context-compacted json (default: latest auto-detected)
  --runs-root <path>              Runs root (default: <repo>/runs)
  --title <text>                  Override resumed task title
  --flow <gate|chain>             Override flow mode
  --member-id <id>                Override member id
  --team-name <name>              Override team name
  --notify-member-id <id>         Override notify member id
  --store-root <path>             Override store root for new run
  --carry-gate-expected           Carry previous --gate-expected-task-state into resumed run
  --strict                        Strict mode
  -h, --help                      Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --compact-json)
      SOURCE_COMPACT="$2"
      shift 2
      ;;
    --runs-root)
      RUNS_ROOT="$2"
      shift 2
      ;;
    --title)
      TITLE_OVERRIDE="$2"
      shift 2
      ;;
    --flow)
      FLOW_OVERRIDE="$2"
      shift 2
      ;;
    --member-id)
      MEMBER_OVERRIDE="$2"
      shift 2
      ;;
    --team-name)
      TEAM_OVERRIDE="$2"
      shift 2
      ;;
    --notify-member-id)
      NOTIFY_MEMBER_OVERRIDE="$2"
      shift 2
      ;;
    --store-root)
      STORE_ROOT_OVERRIDE="$2"
      shift 2
      ;;
    --carry-gate-expected)
      CARRY_GATE_EXPECTED=1
      shift
      ;;
    --strict)
      STRICT_MODE=1
      shift
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    *)
      echo "[resume-task] unknown option: $1" >&2
      print_help >&2
      exit 2
      ;;
  esac
done

if [[ -z "${SOURCE_COMPACT}" ]]; then
  SOURCE_COMPACT="$("${PYTHON_CMD}" - "${RUNS_ROOT}" <<'PY'
import glob, os, sys
runs_root = sys.argv[1]
context_candidates = sorted(glob.glob(os.path.join(runs_root, "*", "context-compacted.json")), key=os.path.getmtime, reverse=True)
if context_candidates:
    print(context_candidates[0])
    raise SystemExit(0)
compact_candidates = sorted(glob.glob(os.path.join(runs_root, "*", "compact.json")), key=os.path.getmtime, reverse=True)
print(compact_candidates[0] if compact_candidates else "")
PY
)"
fi

if [[ -z "${SOURCE_COMPACT}" || ! -f "${SOURCE_COMPACT}" ]]; then
  echo "[resume-task] compact.json not found. Provide --compact-json or run run-task.sh first." >&2
  exit 2
fi

SOURCE_RUN_DIR="$(dirname "${SOURCE_COMPACT}")"
SOURCE_CONTEXT_COMPACT="${SOURCE_RUN_DIR}/context-compacted.json"
SOURCE_PLAIN_COMPACT="${SOURCE_RUN_DIR}/compact.json"
if [[ -f "${SOURCE_CONTEXT_COMPACT}" && -f "${SOURCE_PLAIN_COMPACT}" && "${SOURCE_COMPACT}" == "${SOURCE_CONTEXT_COMPACT}" ]]; then
  echo "[resume-task] info: using context-compacted.json (preferred). compact.json also exists in the same run."
fi

RESUME_FIELDS_STR="$("${PYTHON_CMD}" - "${SOURCE_COMPACT}" <<'PY'
import json, os, sys
compact_path = sys.argv[1]
compact = json.load(open(compact_path, encoding="utf-8"))
input_obj = compact.get("input", {}) if isinstance(compact, dict) else {}
if not isinstance(input_obj, dict):
    input_obj = {}
orch_path = (
    input_obj.get("orchestrator_json")
    or input_obj.get("latest_orchestrator_json")
    or ""
)
orch = {}
if orch_path and os.path.exists(orch_path):
    orch = json.load(open(orch_path, encoding="utf-8"))
inp = orch.get("input", {}) if isinstance(orch, dict) else {}
flow_mode = orch.get("flow_mode") if isinstance(orch, dict) else ""
task_title = inp.get("task_title") if isinstance(inp, dict) else ""
team_name = inp.get("team_name") if isinstance(inp, dict) else ""
member_id = inp.get("member_id") if isinstance(inp, dict) else ""
notify_member_id = inp.get("notify_member_id") if isinstance(inp, dict) else ""
gate_expected = inp.get("gate_expected_task_state") if isinstance(inp, dict) else ""
task_update_state = inp.get("task_update_state") if isinstance(inp, dict) else ""
print(orch_path or "")
print(task_title or "")
print(team_name or "")
print(member_id or "")
print(notify_member_id or "")
print(flow_mode or "")
print(gate_expected or "")
print(task_update_state or "")
PY
)"

RESUME_FIELDS=()
while IFS= read -r line; do
  RESUME_FIELDS+=("${line}")
done <<EOF
${RESUME_FIELDS_STR}
EOF

SOURCE_ORCH="${RESUME_FIELDS[0]:-}"
PREV_TITLE="${RESUME_FIELDS[1]:-}"
PREV_TEAM_NAME="${RESUME_FIELDS[2]:-}"
PREV_MEMBER_ID="${RESUME_FIELDS[3]:-}"
PREV_NOTIFY_MEMBER_ID="${RESUME_FIELDS[4]:-}"
PREV_FLOW_MODE="${RESUME_FIELDS[5]:-}"
PREV_GATE_EXPECTED="${RESUME_FIELDS[6]:-}"
PREV_TASK_UPDATE_STATE="${RESUME_FIELDS[7]:-}"

NEW_RUN_ID="$(date '+%Y-%m-%dT%H-%M-%S')-resume"
NEW_RUN_DIR="${RUNS_ROOT}/${NEW_RUN_ID}"
mkdir -p "${NEW_RUN_DIR}"

RECOVERY_JSON="${NEW_RUN_DIR}/recovery-next.json"
ESCALATION_JSON="${NEW_RUN_DIR}/escalation-draft.json"
HANDOFF_JSON="${NEW_RUN_DIR}/handoff.json"
HANDOFF_MD="${NEW_RUN_DIR}/handoff.md"

echo "[resume-task] source_compact=${SOURCE_COMPACT}"
echo "[resume-task] source_orchestrator=${SOURCE_ORCH:-"(unresolved)"}"
echo "[resume-task] run_dir=${NEW_RUN_DIR}"

"${PYTHON_CMD}" "${ROOT_DIR}/poc/recovery_next_helper.py" \
  --from-compact "${SOURCE_COMPACT}" \
  --output-json "${RECOVERY_JSON}" >/dev/null || true

if [[ -f "${RECOVERY_JSON}" && -n "${SOURCE_ORCH}" && -f "${SOURCE_ORCH}" ]]; then
  "${PYTHON_CMD}" "${ROOT_DIR}/poc/escalation_draft_helper.py" \
    --orchestrator-json "${SOURCE_ORCH}" \
    --recovery-json "${RECOVERY_JSON}" \
    --output-json "${ESCALATION_JSON}" >/dev/null || true
fi

if [[ -f "${ESCALATION_JSON}" ]]; then
  "${PYTHON_CMD}" "${ROOT_DIR}/poc/handoff_helper.py" \
    --escalation-draft-json "${ESCALATION_JSON}" \
    --output-json "${HANDOFF_JSON}" \
    --output-markdown "${HANDOFF_MD}" >/dev/null || true
fi

TITLE="${TITLE_OVERRIDE:-${PREV_TITLE:-resumed-task}}"
TEAM_NAME="${TEAM_OVERRIDE:-${PREV_TEAM_NAME:-team-resume}}"
MEMBER_ID="${MEMBER_OVERRIDE:-${PREV_MEMBER_ID:-worker_daily_driver}}"
NOTIFY_MEMBER_ID="${NOTIFY_MEMBER_OVERRIDE:-${PREV_NOTIFY_MEMBER_ID:-${MEMBER_ID}}}"
FLOW_MODE="${FLOW_OVERRIDE:-${PREV_FLOW_MODE:-gate}}"
BOOTSTRAP_MESSAGE="resume from $(basename "$(dirname "${SOURCE_COMPACT}")")"
TASK_UPDATE_STATE="${PREV_TASK_UPDATE_STATE:-in_progress}"

if [[ ${CARRY_GATE_EXPECTED} -eq 1 && -n "${PREV_GATE_EXPECTED}" ]]; then
  GATE_EXPECTED_OPT=(--gate-expected-task-state "${PREV_GATE_EXPECTED}")
else
  GATE_EXPECTED_OPT=()
fi

RUN_TASK_CMD=(
  "${ROOT_DIR}/scripts/run-task.sh"
  --title "${TITLE}"
  --flow "${FLOW_MODE}"
  --team-name "${TEAM_NAME}"
  --member-id "${MEMBER_ID}"
  --notify-member-id "${NOTIFY_MEMBER_ID}"
  --bootstrap-message "${BOOTSTRAP_MESSAGE}"
  --task-update-state "${TASK_UPDATE_STATE}"
  --runs-root "${RUNS_ROOT}"
  --run-id "${NEW_RUN_ID}"
)

if [[ ${STRICT_MODE} -eq 1 ]]; then
  RUN_TASK_CMD+=(--strict)
fi
if [[ -n "${STORE_ROOT_OVERRIDE}" ]]; then
  RUN_TASK_CMD+=(--store-root "${STORE_ROOT_OVERRIDE}")
fi
if [[ ${#GATE_EXPECTED_OPT[@]} -gt 0 ]]; then
  RUN_TASK_CMD+=("${GATE_EXPECTED_OPT[@]}")
fi

"${RUN_TASK_CMD[@]}"
RUN_EXIT=$?

if [[ ${STRICT_MODE} -eq 1 && ${RUN_EXIT} -ne 0 ]]; then
  exit "${RUN_EXIT}"
fi
exit 0
