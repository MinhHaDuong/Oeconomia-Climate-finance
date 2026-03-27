---
name: ticket-close
description: Close a local ticket and release its claim.
disable-model-invocation: false
user-invocable: true
argument-hint: <ticket-id>
---

# Close ticket $ARGUMENTS

## Steps

1. Find the ticket file: `tickets/$ARGUMENTS-*.ticket`

2. Update the ticket:
   - Change `Status: doing` → `Status: closed`
   - Append log line: `{timestamp} {agent} status closed — {reason}`

3. Release the claim:
   ```bash
   rm -f "$(git rev-parse --git-common-dir)/ticket-wip/$ARGUMENTS.wip"
   ```

4. Commit the ticket status change.
