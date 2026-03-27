---
name: memory
description: Write, update, or sweep persistent memory. Enforces list caps, TTLs, and staleness criteria.
disable-model-invocation: false
user-invocable: true
---

# Memory — persistent memory management

Persistent memory lives at `$CLAUDE_MEMORY_DIR/MEMORY.md`.

## When to run

- During `/celebrate` (save only, no sweep)
- During `/end-session` (full sweep: stale check + rule cross-reference)
- After a user correction (save feedback immediately)
- After discovering a project quirk

## Procedure

1. Check the entry against policy:
   - Is it something to remember? (not derivable from code/git/docs)
   - Does it fit within list caps?
   - Does it have a TTL?
2. For sweeps: scan every entry against staleness criteria.
3. **Cross-reference against rules and skills**: if covered, delete the memory. If the rule is worth codifying but missing, add it to the appropriate rule file and delete the memory.
4. For `project_*.md` files: delete if complete or superseded.

## What to remember

- User preferences and workflow corrections
- Machine-specific configuration (paths, API keys, remote machines)
- Naming conventions and project quirks not obvious from code

## What NOT to remember

- Anything derivable from code, git history, or other docs
- Ephemeral task state (use STATE.md or git commits)
- Content already in README, ROADMAP, STATE, rules, or skills

## List size limits

| Section type | Cap |
|---|---|
| Corpus statistics | 3 — replace, don't append |
| Feedback entries | 5 — older feedback should be distilled into rule changes |
| Project-state entries | 3 — stale project state belongs in git history |
| Named scripts or output files | 10 |

## Time limits (TTL)

| Memory type | TTL | Action on expiry |
|---|---|---|
| Corpus statistics | 30 days | Re-derive or delete |
| "X needed" / "X blocked" | 14 days | File ticket or delete |
| Performance benchmarks | 60 days | Re-run or delete |
| Remote machine config | 90 days | Confirm or delete |

No TTL (stable until contradicted): workflow preferences, feedback, naming conventions, architectural decisions.

## Staleness criteria

An entry is stale if:
- It references a file that no longer exists
- It describes a state marked resolved elsewhere
- Its TTL has elapsed without confirmation
- A newer entry in the same section contradicts it
