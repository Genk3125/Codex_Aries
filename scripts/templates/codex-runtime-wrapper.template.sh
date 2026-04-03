#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_SUFFIX="__PROFILE_NAME__"
PROFILE_ENV_FILE="${SCRIPT_DIR}/runtime-adapter-${PROFILE_SUFFIX}.env"

if [[ -f "${PROFILE_ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${PROFILE_ENV_FILE}"
fi

AMAX_PYTHON_CMD="${AMAX_PYTHON_CMD:-python3}"
AMAX_RUNTIME_ADAPTER_PATH="${AMAX_RUNTIME_ADAPTER_PATH:-__REPO_ROOT__/poc/codex_runtime_adapter.py}"
AMAX_RUNTIME_STORE_ROOT="${AMAX_RUNTIME_STORE_ROOT:-__STORE_ROOT__}"

if [[ ! -f "${AMAX_RUNTIME_ADAPTER_PATH}" ]]; then
  echo "Adapter not found: ${AMAX_RUNTIME_ADAPTER_PATH}" >&2
  exit 2
fi

STRICT_FLAG=""
if [[ "${1:-}" == "--strict" ]]; then
  STRICT_FLAG="--strict"
  shift
fi

run_adapter_op() {
  local op_name="$1"
  local args_json="$2"
  "${AMAX_PYTHON_CMD}" "${AMAX_RUNTIME_ADAPTER_PATH}" \
    --store-root "${AMAX_RUNTIME_STORE_ROOT}" \
    ${STRICT_FLAG:+$STRICT_FLAG} \
    op --name "${op_name}" --args-json "${args_json}"
}

if [[ $# -lt 1 ]]; then
  cat <<'USAGE'
Usage:
  codex-runtime-__PROFILE_NAME__ [--strict] team-create <team_name> [idempotency_key]
  codex-runtime-__PROFILE_NAME__ [--strict] send-message <team_id> <from_member_id> <to_member_id> <text> [idempotency_key]
  codex-runtime-__PROFILE_NAME__ [--strict] task-create <team_id> <title> <owner_member_id> [state] [idempotency_key]
  codex-runtime-__PROFILE_NAME__ [--strict] reconcile-all
  codex-runtime-__PROFILE_NAME__ [--strict] op --name <operation> [--args-json <json> | --args-file <path>]
  codex-runtime-__PROFILE_NAME__ [--strict] ops
USAGE
  exit 1
fi

cmd="$1"
shift

case "${cmd}" in
  team-create)
    if [[ $# -lt 1 ]]; then
      echo "team-create requires: <team_name> [idempotency_key]" >&2
      exit 1
    fi
    TEAM_NAME="$1"
    IDEMPOTENCY_KEY="${2:-}"
    ARGS_JSON="$("${AMAX_PYTHON_CMD}" - "${TEAM_NAME}" "${IDEMPOTENCY_KEY}" <<'PY'
import json
import sys
team_name = sys.argv[1]
idempotency_key = sys.argv[2]
data = {"team_name": team_name}
if idempotency_key:
    data["idempotency_key"] = idempotency_key
print(json.dumps(data, ensure_ascii=False))
PY
)"
    run_adapter_op "team_create" "${ARGS_JSON}"
    ;;

  send-message)
    if [[ $# -lt 4 ]]; then
      echo "send-message requires: <team_id> <from_member_id> <to_member_id> <text> [idempotency_key]" >&2
      exit 1
    fi
    TEAM_ID="$1"
    FROM_MEMBER_ID="$2"
    TO_MEMBER_ID="$3"
    TEXT="$4"
    IDEMPOTENCY_KEY="${5:-}"
    ARGS_JSON="$("${AMAX_PYTHON_CMD}" - "${TEAM_ID}" "${FROM_MEMBER_ID}" "${TO_MEMBER_ID}" "${TEXT}" "${IDEMPOTENCY_KEY}" <<'PY'
import json
import sys
team_id = sys.argv[1]
from_member_id = sys.argv[2]
to_member_id = sys.argv[3]
text = sys.argv[4]
idempotency_key = sys.argv[5]
data = {
    "team_id": team_id,
    "from_member_id": from_member_id,
    "to_member_id": to_member_id,
    "message_type": "direct",
    "payload": {"text": text},
}
if idempotency_key:
    data["idempotency_key"] = idempotency_key
print(json.dumps(data, ensure_ascii=False))
PY
)"
    run_adapter_op "send_message" "${ARGS_JSON}"
    ;;

  task-create)
    if [[ $# -lt 3 ]]; then
      echo "task-create requires: <team_id> <title> <owner_member_id> [state] [idempotency_key]" >&2
      exit 1
    fi
    TEAM_ID="$1"
    TITLE="$2"
    OWNER_MEMBER_ID="$3"
    STATE="${4:-todo}"
    IDEMPOTENCY_KEY="${5:-}"
    ARGS_JSON="$("${AMAX_PYTHON_CMD}" - "${TEAM_ID}" "${TITLE}" "${OWNER_MEMBER_ID}" "${STATE}" "${IDEMPOTENCY_KEY}" <<'PY'
import json
import sys
team_id = sys.argv[1]
title = sys.argv[2]
owner_member_id = sys.argv[3]
state = sys.argv[4]
idempotency_key = sys.argv[5]
data = {
    "team_id": team_id,
    "title": title,
    "owner_member_id": owner_member_id,
    "state": state,
}
if idempotency_key:
    data["idempotency_key"] = idempotency_key
print(json.dumps(data, ensure_ascii=False))
PY
)"
    run_adapter_op "task_create" "${ARGS_JSON}"
    ;;

  reconcile-all)
    run_adapter_op "runtime_reconcile_all" "{}"
    ;;

  op)
    "${AMAX_PYTHON_CMD}" "${AMAX_RUNTIME_ADAPTER_PATH}" \
      --store-root "${AMAX_RUNTIME_STORE_ROOT}" \
      ${STRICT_FLAG:+$STRICT_FLAG} \
      op "$@"
    ;;

  ops)
    "${AMAX_PYTHON_CMD}" "${AMAX_RUNTIME_ADAPTER_PATH}" \
      --store-root "${AMAX_RUNTIME_STORE_ROOT}" \
      ${STRICT_FLAG:+$STRICT_FLAG} \
      ops
    ;;

  *)
    echo "Unknown command: ${cmd}" >&2
    exit 1
    ;;
esac
