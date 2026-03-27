#!/usr/bin/env bash
# run_corpus_pipeline.sh — Run the full DVC corpus pipeline on padme.
#
# Guards: hostname must be padme, dvc must be installed, branch must be main.
# After dvc repro + push, auto-commits dvc.lock if it's the only changed file.
# Otherwise warns the user to commit manually.
#
# Usage: bash scripts/run_corpus_pipeline.sh
#   (or invoked via `make corpus`)

set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ_ROOT"

# --- Guard: hostname ---
if [ "$(hostname)" != "padme" ]; then
    echo "error: make corpus runs on padme only. Use 'make corpus-sync' on $(hostname)."
    exit 1
fi

# --- Guard: dvc installed ---
if ! uv run dvc version >/dev/null 2>&1; then
    echo "error: dvc not found. Install with: uv tool install 'dvc[ssh]'"
    exit 1
fi

# --- Guard: must be on main ---
current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$current_branch" != "main" ]; then
    echo "error: make corpus must run on main (currently on $current_branch)."
    exit 1
fi

# --- Run pipeline ---
ret=0
uv run dvc repro || ret=$?
uv run dvc push

if [ "$ret" -ne 0 ]; then
    exit "$ret"
fi

# --- Auto-commit logic ---
changed=$(git status --porcelain)

if [ -z "$changed" ]; then
    echo "dvc.lock unchanged, nothing to commit."
elif [ "$(echo "$changed" | sed 's/^...//')" = "dvc.lock" ]; then
    echo "Auto-committing dvc.lock..."
    branch="housekeeping-dvclock-$(date +%Y%m%d-%H%M%S)"
    git checkout -b "$branch"
    git add dvc.lock
    git commit -m "data: update dvc.lock after pipeline re-run"
    git checkout main
    git merge "$branch"
    git branch -d "$branch"
    git push origin main
    echo "dvc.lock committed and pushed."
else
    echo ""
    echo "WARNING: files other than dvc.lock changed:"
    echo "$changed"
    echo "Stage and commit manually."
fi
