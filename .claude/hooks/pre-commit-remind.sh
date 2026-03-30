#!/bin/bash
# PreToolUse(Bash) hook: remind agent to verify before committing.
# Fires when a git commit command is detected.

COMMAND="$TOOL_INPUT_COMMAND"

# Only trigger on git commit commands
case "$COMMAND" in
    *"git commit"*) ;;
    *) exit 0 ;;
esac

echo "Pre-commit checklist:"
echo "- DVC lock: if dvc.lock is staged, verify hashes exist in local cache"
echo "- Stale check: re-read modified files for outdated numbers/dead references"
echo "- Technical report: update if pipeline contracts, scripts, or schema changed"
exit 0
