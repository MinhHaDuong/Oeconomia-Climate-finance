#!/bin/bash
# Usage: scripts/time_target.sh <label> <output_jsonl> <command...>
#
# Runs <command> and appends a JSON line to <output_jsonl> with:
#   label, wall_s, peak_rss_kb, timestamp, git_sha
#
# Uses /usr/bin/time -v (GNU time) for peak RSS measurement.
# On macOS, install `gtime` via Homebrew and symlink or use gtime.

set -euo pipefail

# Force C locale for consistent decimal separator in awk/printf
export LC_ALL=C

LABEL="$1"
OUTPUT="$2"
shift 2

# Create output directory if needed
mkdir -p "$(dirname "$OUTPUT")"

# GNU time writes to stderr in a specific format
TIMEFILE=$(mktemp)
trap 'rm -f "$TIMEFILE"' EXIT

if command -v /usr/bin/time &>/dev/null; then
    TIME_CMD="/usr/bin/time"
elif command -v gtime &>/dev/null; then
    TIME_CMD="gtime"
else
    echo "ERROR: GNU time not found (/usr/bin/time or gtime)" >&2
    exit 1
fi

# Run the command with GNU time
"$TIME_CMD" -v "$@" 2>"$TIMEFILE"
EXIT_CODE=$?

# Parse wall time (format: h:mm:ss or m:ss.ss)
WALL_RAW=$(grep "Elapsed (wall clock) time" "$TIMEFILE" | sed 's/.*: //')
# Convert to seconds
if echo "$WALL_RAW" | grep -q "^[0-9]*:[0-9]*:[0-9]"; then
    # h:mm:ss format
    WALL_S=$(echo "$WALL_RAW" | awk -F: '{print $1*3600 + $2*60 + $3}')
else
    # m:ss.ss format
    WALL_S=$(echo "$WALL_RAW" | awk -F: '{print $1*60 + $2}')
fi

# Parse peak RSS (in KB)
PEAK_RSS=$(grep "Maximum resident set size" "$TIMEFILE" | awk '{print $NF}')

# Git SHA (short)
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Timestamp
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Append JSON line
printf '{"label":"%s","wall_s":%s,"peak_rss_kb":%s,"exit_code":%d,"timestamp":"%s","git_sha":"%s"}\n' \
    "$LABEL" "$WALL_S" "${PEAK_RSS:-0}" "$EXIT_CODE" "$TIMESTAMP" "$GIT_SHA" >> "$OUTPUT"
