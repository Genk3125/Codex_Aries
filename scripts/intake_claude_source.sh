#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /absolute/path/to/claude-code-main [output_markdown_path]" >&2
  exit 1
fi

SOURCE_DIR="$1"
OUTPUT_PATH="${2:-}"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Source directory not found: $SOURCE_DIR" >&2
  exit 1
fi

SRC_DIR="$SOURCE_DIR/src"
if [[ ! -d "$SRC_DIR" ]]; then
  echo "Expected src directory not found: $SRC_DIR" >&2
  exit 1
fi

DATE_UTC="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
DATE_TAG="$(date -u '+%Y%m%d-%H%M%S')"

if [[ -z "$OUTPUT_PATH" ]]; then
  OUTPUT_PATH="data/raw/claude-source-intake-${DATE_TAG}.md"
fi

mkdir -p "$(dirname "$OUTPUT_PATH")"

TOTAL_FILES="$(find "$SRC_DIR" -type f | wc -l | tr -d ' ')"
TS_FILES="$(find "$SRC_DIR" -type f -name '*.ts' | wc -l | tr -d ' ')"
TSX_FILES="$(find "$SRC_DIR" -type f -name '*.tsx' | wc -l | tr -d ' ')"
JS_FILES="$(find "$SRC_DIR" -type f -name '*.js' | wc -l | tr -d ' ')"

{
  echo "# Claude Source Intake"
  echo
  echo "- Generated at (UTC): $DATE_UTC"
  echo "- Source path: $SOURCE_DIR"
  echo "- Total source files: $TOTAL_FILES"
  echo "- TypeScript files (.ts): $TS_FILES"
  echo "- TypeScript React files (.tsx): $TSX_FILES"
  echo "- JavaScript files (.js): $JS_FILES"
  echo
  echo "## Top-level Directory Density (src/*)"
  for d in "$SRC_DIR"/*; do
    [[ -d "$d" ]] || continue
    c="$(find "$d" -type f | wc -l | tr -d ' ')"
    printf "%s\t%s\n" "$c" "$(basename "$d")"
  done | sort -nr | awk -F'\t' '{printf("- %s files: `%s`\n", $1, $2)}'
  echo
  echo "## Tool Modules (src/tools/*)"
  for d in "$SRC_DIR"/tools/*; do
    [[ -d "$d" ]] || continue
    c="$(find "$d" -type f | wc -l | tr -d ' ')"
    printf "%s\t%s\n" "$c" "$(basename "$d")"
  done | sort -nr | awk -F'\t' '{printf("- %s files: `%s`\n", $1, $2)}'
  echo
  echo "## Command Modules (src/commands/*)"
  for d in "$SRC_DIR"/commands/*; do
    [[ -d "$d" ]] || continue
    c="$(find "$d" -type f | wc -l | tr -d ' ')"
    printf "%s\t%s\n" "$c" "$(basename "$d")"
  done | sort -nr | awk -F'\t' '{printf("- %s files: `%s`\n", $1, $2)}'
  echo
  echo "## Candidate Transfer Targets for Codex CLI"
  echo "- Permission orchestration: \`src/hooks/toolPermission\`"
  echo "- Dynamic skills loader: \`src/skills/loadSkillsDir.ts\`"
  echo "- Plugin command loader: \`src/utils/plugins/loadPluginCommands.ts\`"
  echo "- Tool registry composition: \`src/tools.ts\`"
  echo "- Command registry composition: \`src/commands.ts\`"
} >"$OUTPUT_PATH"

echo "Wrote intake report: $OUTPUT_PATH"
