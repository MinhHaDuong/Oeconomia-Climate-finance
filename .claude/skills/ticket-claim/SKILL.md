---
name: ticket-claim
description: Claim a local ticket for work (cross-worktree safe).
disable-model-invocation: false
user-invocable: true
argument-hint: <ticket-id>
---

# Claim ticket $ARGUMENTS

## Steps

1. Verify the ticket exists: `tickets/$ARGUMENTS-*.ticket`
2. Check for existing claim:
   ```bash
   wip_dir="$(git rev-parse --git-common-dir)/ticket-wip"
   cat "$wip_dir/$ARGUMENTS.wip" 2>/dev/null
   ```
   If claimed by another worktree, stop and report.

3. Write the claim:
   ```bash
   wip_dir="$(git rev-parse --git-common-dir)/ticket-wip"
   mkdir -p "$wip_dir"
   echo "$(date -u +%Y-%m-%dT%H:%MZ) $(whoami) $(pwd)" > "$wip_dir/$ARGUMENTS.wip"
   ```

4. Update the ticket file:
   - Change `Status: open` → `Status: doing`
   - Append log line: `{timestamp} {agent} claimed`
   - Append log line: `{timestamp} {agent} status doing`

5. Commit the ticket status change.

## On release

When abandoning or completing, delete the `.wip` file:
```bash
rm "$(git rev-parse --git-common-dir)/ticket-wip/$ARGUMENTS.wip"
```
