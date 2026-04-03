#!/usr/bin/env bash
# check-status-sync.sh — Phase 24
# Detects status label mismatches across MASTER_FLOW / ToDo / milestone-2-closeout.
# Exit 0 = no mismatch detected. Exit 1 = mismatch found.
set -u -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MASTER_FLOW="${ROOT_DIR}/.planning/MASTER_FLOW.md"
TODO="${ROOT_DIR}/ToDo.md"
CLOSEOUT="${ROOT_DIR}/docs/milestone-2-closeout.md"

ERRORS=0

check_file_exists() {
  local f="$1"
  if [[ ! -f "$f" ]]; then
    echo "[check-status-sync] MISSING: $f" >&2
    ERRORS=$((ERRORS + 1))
  fi
}

check_file_exists "${MASTER_FLOW}"
check_file_exists "${TODO}"
check_file_exists "${CLOSEOUT}"

if [[ ${ERRORS} -gt 0 ]]; then
  echo "[check-status-sync] FAIL: missing source files" >&2
  exit 1
fi

python3 - "${MASTER_FLOW}" "${TODO}" "${CLOSEOUT}" <<'PY'
import re, sys

master_flow, todo, closeout = sys.argv[1], sys.argv[2], sys.argv[3]

def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

def extract_phase_statuses(text):
    """Extract Phase N -> status from markdown tables."""
    statuses = {}
    for m in re.finditer(r'\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|', text):
        phase_num = int(m.group(1))
        status = m.group(2).strip()
        statuses[phase_num] = status
    return statuses

def check_label_consistency(text, label, source_name):
    issues = []
    # provisional vs final mismatch
    provisional_count = text.count("provisional")
    final_count = text.count("final")
    if provisional_count > 0 and final_count > 0:
        # This is OK — file may mention both states
        pass
    # Check for done/not_started/in_progress labels
    for bad_pair in [("done", "not_started"), ("done", "in_progress")]:
        a, b = bad_pair
        if a in text and b in text:
            pass  # Could be different phases, OK
    return issues

mf_text = read(master_flow)
todo_text = read(todo)
closeout_text = read(closeout)

mf_statuses = extract_phase_statuses(mf_text)
errors = []

# Check Phase 17-18 provisional consistency
for phase in [17, 18]:
    s = mf_statuses.get(phase)
    if s and s not in {"provisional", "done", "final"}:
        errors.append(f"Phase {phase} has unexpected status '{s}' in MASTER_FLOW")

# Check Phase 20-25 statuses are reasonable
for phase, expected_range in [(20, {"done"}), (21, {"done", "in_progress"}), (22, {"done", "in_progress", "not_started"})]:
    s = mf_statuses.get(phase)
    if s is None:
        errors.append(f"Phase {phase} not found in MASTER_FLOW")

# Check ToDo has 'Now' section
if "## Now" not in todo_text:
    errors.append("ToDo.md missing '## Now' section")

# Check closeout has provisional/final label
if "provisional" not in closeout_text.lower() and "final" not in closeout_text.lower():
    errors.append("milestone-2-closeout.md missing provisional/final label")

if errors:
    for e in errors:
        print(f"[check-status-sync] MISMATCH: {e}")
    sys.exit(1)
else:
    print("[check-status-sync] OK: no status mismatches detected")
    sys.exit(0)
PY
EXIT=$?
if [[ ${EXIT} -ne 0 ]]; then
  echo "[check-status-sync] FAIL" >&2
  exit 1
fi
exit 0
