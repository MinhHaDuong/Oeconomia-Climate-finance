# New ticket — create a GitHub issue

Issues are handoff documents. A new agent will only have the context provided.

## Required sections

```markdown
## Context
What problem or need this addresses. Why now.

## Relevant files
- `path/to/file.py` — role in this task

## Actions
1. Concrete step
2. Concrete step

## Verification
- [ ] How to confirm each action worked

## Invariants
- What must not break (tests, build, existing behavior)

## Exit criteria
- Definition of done — when is this ticket complete?
```

## Before starting work on a ticket

Read the exit criteria. If unclear, clarify with the author before writing code.

## Command

```bash
gh issue create --title "short title" --body "$(cat <<'EOF'
<paste template above, filled in>
EOF
)"
```
