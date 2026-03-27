---
name: new-ticket
description: Create a GitHub issue as a handoff document with required sections for TDD workflow.
disable-model-invocation: false
user-invocable: true
argument-hint: [title]
---

# New ticket — create a GitHub issue

`[Dreaming → Planning]`

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

## Test
- What test to write first (red step of TDD)

## Verification
- [ ] How to confirm each action worked

## Invariants
- What must not break (tests, build, existing behavior)

## Exit criteria
- Definition of done — when is this ticket complete?
```

## Command

```bash
gh issue create --title "$ARGUMENTS" --body "$(cat <<'EOF'
<paste template above, filled in>
EOF
)"
```

## Tracking issue convention

When investigation spawns sub-issues:

1. Original issue becomes the **tracking issue** — leave it open.
2. Create each sub-issue as a GitHub child: `gh issue create --title "..." --body "..." --parent <TRACKING_ISSUE_NUMBER>`
3. Edit tracking issue body to add `## Sub-issues` heading listing each child.
4. Tracking issue closes only after integration review (see `/celebrate` step 10).
