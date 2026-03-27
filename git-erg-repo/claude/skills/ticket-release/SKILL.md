---
name: ticket-release
description: Release a claimed ticket (abandon work, restore to open).
disable-model-invocation: false
user-invocable: true
argument-hint: <ticket-id>
---

# Release ticket $ARGUMENTS

Use when abandoning work on a claimed ticket, or when a session ends without completing it.

## Steps

1. **Validate the ticket ID** — must be exactly 4 digits:
   ```bash
   echo "$ARGUMENTS" | grep -qE '^[0-9]{4}$' || { echo "Invalid ticket ID: must be 4 digits"; exit 1; }
   ```

2. Find the ticket file: `tickets/$ARGUMENTS-*.erg`

3. Update the ticket:
   - Change `Status: doing` → `Status: open`
   - Append log line: `{timestamp} {agent} released — {reason}`
   - Append log line: `{timestamp} {agent} status open`

4. Delete the `.wip` claim:
   ```bash
   rm -f "$(git rev-parse --git-common-dir)/ticket-wip/$ARGUMENTS.wip"
   ```

5. Commit the ticket status change.
