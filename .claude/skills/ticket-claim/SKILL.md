---
name: ticket-claim
description: Claim a local ticket for work (cross-worktree safe).
disable-model-invocation: false
user-invocable: true
argument-hint: <ticket-id>
---

# Claim ticket $ARGUMENTS

## Steps

1. **Validate the ticket ID** — must be exactly 4 digits:
   ```bash
   echo "$ARGUMENTS" | grep -qE '^[0-9]{4}$' || { echo "Invalid ticket ID: must be 4 digits"; exit 1; }
   ```

2. Verify the ticket exists: `tickets/$ARGUMENTS-*.erg`
3. Check for existing claim:
   ```bash
   wip_dir="$(git rev-parse --git-common-dir)/ticket-wip"
   cat "$wip_dir/$ARGUMENTS.wip" 2>/dev/null
   ```
   If claimed by another worktree, stop and report.

4. Write the claim:
   ```bash
   wip_dir="$(git rev-parse --git-common-dir)/ticket-wip"
   mkdir -p "$wip_dir"
   echo "$(date -u +%Y-%m-%dT%H:%MZ) $(whoami) $(pwd)" > "$wip_dir/$ARGUMENTS.wip"
   ```

5. Update the ticket file:
   - Change `Status: open` → `Status: doing`
   - Append log line: `{timestamp} {agent} claimed`
   - Append log line: `{timestamp} {agent} status doing`

6. Commit the ticket status change.

## On release

When abandoning or completing, delete the `.wip` file:
```bash
rm "$(git rev-parse --git-common-dir)/ticket-wip/$ARGUMENTS.wip"
```
