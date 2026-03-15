# Memory — persistent memory policy

Persistent memory lives at `$CLAUDE_MEMORY_DIR/MEMORY.md` (auto-loaded by some agents; others should read it at conversation start).

## What to remember

- User preferences and workflow corrections
- Machine-specific configuration (paths, API keys, remote machines)
- Naming conventions and project quirks not obvious from code

## What NOT to remember

- Anything derivable from code, git history, or other docs
- Ephemeral task state (use STATE.md or git commits instead)
- Content already in README, ROADMAP, STATE, or guidelines docs

## When to update

- **Celebrating phase**: always review and update memories
- **After user correction**: save feedback immediately
- **After discovering a quirk**: save so future sessions don't rediscover it
