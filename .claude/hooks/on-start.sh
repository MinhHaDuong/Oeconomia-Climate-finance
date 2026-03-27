#!/bin/bash
# SessionStart hook: set agent identity and activate git hooks.
# Runs at the beginning of every Claude Code session.

cd "$CLAUDE_PROJECT_DIR" || exit 0

# Load .env if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Set agent identity (non-blocking: don't fail if vars are missing)
if [ -n "$AGENT_GIT_NAME" ]; then
    git config user.name "$AGENT_GIT_NAME"
fi
if [ -n "$AGENT_GIT_EMAIL" ]; then
    git config user.email "$AGENT_GIT_EMAIL"
fi

# Activate project hooks
git config core.hooksPath hooks 2>/dev/null

# Export GitHub token for gh CLI
if [ -n "$AGENT_GH_TOKEN" ]; then
    # Write to CLAUDE_ENV_FILE so it persists for the session
    if [ -n "$CLAUDE_ENV_FILE" ]; then
        echo "GH_TOKEN=$AGENT_GH_TOKEN" >> "$CLAUDE_ENV_FILE"
    fi
fi

echo "Agent identity configured. Read STATE.md and ROADMAP.md to orient."
