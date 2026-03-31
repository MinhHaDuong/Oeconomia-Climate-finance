---
paths:
  - "STATE.md"
  - "ROADMAP.md"
---

# STATE.md and ROADMAP.md

Both files are loaded at every session start. Keep them short and current — history lives in `git log`.

## STATE.md — snapshot of now (~30 lines max)

| Section | Content |
|---------|---------|
| `Last updated:` | Date |
| `## Status` | One-liner summary |
| `## Submissions` | Active submissions only (journal, date, key links) |
| `## Corpus` | Current version + key stats. No changelog. |
| `## Blockers` | Current blockers or "None" |
| `## Next actions` | 5–10 items, most urgent first |

**Pruning:** each update *replaces* sections, not appends. Completed next-actions are deleted. Infrastructure improvements are not listed — they're in git history.

## ROADMAP.md — forward-looking milestones (~40 lines max)

| Section | Content |
|---------|---------|
| `## North star` | One paragraph — the core argument |
| `## Current milestone` | What we're working toward, with `- [ ]` checkboxes |
| `## Next milestone` | What comes after |
| `## Backlog` | Parked ideas, no checkboxes |

**Pruning:** when an item is checked off, it stays for one session (so the author sees it acknowledged), then is deleted on the next update. No "Completed" section — git has the history.
