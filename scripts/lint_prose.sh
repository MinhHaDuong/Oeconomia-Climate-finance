#!/usr/bin/env bash
# lint_prose.sh — Detect AI-tell patterns in manuscript prose.
#
# Checks for blacklisted words (LLM vocabulary tells), em-dash overuse,
# and contrast farming ("not X, but Y") patterns. Exits non-zero on failure.
set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANUSCRIPT="${PROJ_ROOT}/content/manuscript.qmd"

echo "=== Blacklisted words (expect 0) ==="
count=$(grep -ciE 'delve|nuanced|multifaceted|pivotal|tapestry|intricate|meticulous|vibrant|showcasing|underscores' "$MANUSCRIPT" || true)
echo "  Found: $count"
[ "$count" -eq 0 ] || exit 1

echo "=== Em-dash heavy paragraphs (target 0, currently 7 — fix during proofread) ==="
count=$(grep -cP -- '---.*---.*---' "$MANUSCRIPT" || true)
echo "  Found: $count"
[ "$count" -le 7 ] || exit 1

echo "=== Contrast farming (expect ≤3) ==="
count=$(grep -cP 'not .{3,60}, but ' "$MANUSCRIPT" || true)
echo "  Found: $count"
[ "$count" -le 3 ] || exit 1

echo "LINT-PROSE: PASS"
