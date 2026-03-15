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

## When investigation spawns sub-issues (tracking issue convention)

If investigation of a ticket reveals multiple independent action items:

1. The original issue becomes the **tracking issue** — leave it open.
2. Create each sub-issue as a native GitHub child (`--parent` requires gh ≥ 2.49):
   ```bash
   gh issue create --title "..." --body "..." --parent <TRACKING_ISSUE_NUMBER>
   ```
3. After creating all sub-issues, edit the tracking issue body to add a `## Sub-issues` heading listing each child issue number.
4. The tracking issue closes only after integration review (see `runbooks/celebrate.md` step 10).
