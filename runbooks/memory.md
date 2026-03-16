# Memory — persistent memory trigger

Run when writing, updating, or sweeping persistent memory.

Persistent memory lives at `$CLAUDE_MEMORY_DIR/MEMORY.md`.

## When this trigger runs

- During `runbooks/celebrate.md` (step 5)
- During `runbooks/on-start.md` (step 3d)
- After a user correction (save feedback immediately)
- After discovering a project quirk

## Procedure

1. Check the entry against the policy below:
   - Is it something to remember? (not derivable from code/git/docs)
   - Does it fit within list caps?
   - Does it have a TTL?
2. For sweeps: scan every entry against staleness criteria below.
3. For `project_*.md` files: delete if the state described is complete or superseded; remove MEMORY.md pointer.

## What to remember

- User preferences and workflow corrections
- Machine-specific configuration (paths, API keys, remote machines)
- Naming conventions and project quirks not obvious from code

## What NOT to remember

- Anything derivable from code, git history, or other docs
- Ephemeral task state (use STATE.md or git commits instead)
- Content already in README, ROADMAP, STATE, or guidelines docs

## List size limits

Any list-type section in MEMORY.md has a hard cap. When appending, if the cap is reached, evict the least-recently-confirmed entry first.

| Section type | Cap |
|---|---|
| Corpus statistics (work counts, source counts) | 3 — replace, don't append |
| Feedback entries | 5 — older feedback should be distilled into runbook changes |
| Project-state entries (blockers, regen needed) | 3 — stale project state belongs in git history |
| Named scripts or output files | 10 — if a list exceeds this, the section needs redesign |

## Time limits (TTL)

Entries describing **transient state** expire. After the TTL, either confirm and reset the clock, or archive.

| Memory type | TTL | Action on expiry |
|---|---|---|
| Corpus statistics (counts, dates) | 30 days | Re-derive from data or delete |
| "X needed" / "X blocked" entries | 14 days | File a ticket or delete — don't let blockers rot in memory |
| Performance benchmarks (timing, size) | 60 days | Re-run or delete |
| Remote machine config | 90 days | Confirm or delete |

Entries with **no TTL** (stable until explicitly contradicted): workflow preferences, feedback, naming conventions, architectural decisions.

## Staleness criteria

An entry is stale if any of the following are true:
- It references a file that no longer exists
- It describes a state marked as resolved elsewhere (STATE.md, closed PR, closed issue)
- Its TTL has elapsed without confirmation
- A newer entry in the same section contradicts it
