# Memory — persistent memory hook

Run when writing, updating, or sweeping persistent memory.

Persistent memory lives at `$CLAUDE_MEMORY_DIR/MEMORY.md`.

## When this hook fires

- During `runbooks/celebrate.md` (step 5)
- During `runbooks/on-start.md` (step 3d)
- After a user correction (save feedback immediately)
- After discovering a project quirk

## Procedure

1. Check the entry against `docs/memory-policy.md`:
   - Is it something to remember? (not derivable from code/git/docs)
   - Does it fit within list caps?
   - Does it have a TTL?
2. For sweeps: scan every entry against staleness criteria in `docs/memory-policy.md`.
3. For `project_*.md` files: delete if the state described is complete or superseded; remove MEMORY.md pointer.
