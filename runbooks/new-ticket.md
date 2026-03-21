# New ticket — create a ticket

Tickets are handoff documents. A new agent will only have the context provided. Creating a ticket is a `[Dreaming → Planning]` transition.

## Local tickets (default)

1. **Choose a semantic slug** — a freely chosen name related to the ticket's purpose. ID = initials of the slug words. Check `ls tickets/{id}-*.ticket` for collisions; if collision, append numeric suffix.
2. **Write the ticket file** as `tickets/{id}-{slug}.ticket` using RFC 822 format (see spec).
3. **Commit immediately** — uncommitted tickets are invisible across worktrees. `git add tickets/{id}-{slug}.ticket && git commit -m "Open ticket {id}: {title}"`.

The body should contain enough context for another agent to work autonomously:

```markdown
--- body ---
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

## Forge tickets (big/coordinated work)

For tickets that need coordination (`Coordination: forge#N`):

```bash
gh issue create --title "short title" --body "$(cat <<'EOF'
<paste template above, filled in>
EOF
)"
```

Then create a local `.ticket` file with `Coordination: gh#N` pointing to the forge issue.

## When investigation spawns sub-issues

If investigation of a ticket reveals multiple independent action items:

1. The original ticket becomes the **tracking ticket** — leave it open.
2. Create each sub-ticket with `X-Parent: {parent-id}`.
3. For forge tickets, also use native GitHub children (`--parent` requires gh ≥ 2.49):
   ```bash
   gh issue create --title "..." --body "..." --parent <TRACKING_ISSUE_NUMBER>
   ```
4. The tracking ticket closes only after integration review (see `runbooks/celebrate.md` step 10).
