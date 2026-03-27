# Ticket format spec — %erg v1

## Overview

Local ticket system for agent coordination across worktrees on one machine.
Not a replacement for GitHub Issues — those handle inter-agent and human coordination.
Tickets are committed to git and travel with the repo.

## File format

Extension: `.erg`
Location: `tickets/` (active), `tickets/archive/` (closed, old)
Encoding: UTF-8, LF line endings.

### Magic first line

```
%erg v1
```

Every `.erg` file starts with this line. It declares the format version
and enables file-type detection without relying on the extension. A future
`%ticket v2` adds headers without breaking v1 validators (they reject
unknown versions rather than silently misparsing).

### Structure

```
%erg v1
Title: Short imperative description
Status: open
Created: 2026-03-27
Author: claude

--- log ---
2026-03-27T10:00Z claude created

--- body ---
Free-form markdown body.
```

Three sections, in order:
1. **Headers** — RFC 822 style, one per line, immediately after magic line.
2. **Log** — append-only ledger, after `--- log ---` separator.
3. **Body** — free-form markdown, after `--- body ---` separator.

A blank line ends the header block. Both separators are required (the
validator rejects files missing either one).

### Headers (closed set, v1)

| Header | Required | Type | Values |
|--------|----------|------|--------|
| `Title` | yes | string | Short imperative sentence |
| `Status` | yes | enum | `open`, `doing`, `closed`, `pending` |
| `Created` | yes | date | `YYYY-MM-DD` |
| `Author` | yes | string | Agent or human identifier |
| `Blocked-by` | no | ref | Ticket ID or `gh#N` (repeatable) |

No other headers are valid in v1. No `X-` extensions. If v2 needs new
headers, it declares `%ticket v2` and extends the set.

**Status values:**
- `open` — available for work.
- `doing` — claimed, in progress.
- `closed` — completed or cancelled.
- `pending` — awaiting external input (e.g., review). Excluded from ready query.

**`Blocked-by` references:**
- A 4-digit ID (e.g., `0041`) refers to a local ticket.
- `gh#N` refers to a GitHub issue. Resolved via API when online, treated as
  satisfied (non-blocking) when offline.
- Repeatable: one `Blocked-by:` line per dependency.
- A blocker must be `closed` to unblock. `doing` and `pending` still block.

### ID assignment

The ticket ID is derived from the filename, not a header.

Filename pattern: `{ID}-{slug}.erg`
- ID: zero-padded sequential number, 4 digits. `0001`, `0002`, ...
- Slug: lowercase kebab-case, ASCII only (`[a-z0-9-]`).

To assign the next ID: read filenames in `tickets/` and `tickets/archive/`,
extract the numeric prefix from each, take the maximum, increment by 1,
zero-pad to 4 digits. If no tickets exist, start at `0001`.

**Collision handling:** optimistic. Two worktrees may pick the same number.
The pre-commit validator catches duplicate IDs. The agent that loses renames
its ticket (increment again). This matches git's own optimistic concurrency.

### Log section

Append-only. Each line records one event:

```
{ISO-8601-timestamp} {actor} {verb} [{detail}]
```

**Timestamp:** `YYYY-MM-DDThh:mmZ` (UTC, minute precision).
**Actor:** agent or human identifier (e.g., `claude`, `user`).
**Verbs (closed set, v1):**

| Verb | Meaning |
|------|---------|
| `created` | Ticket created |
| `status` | Status changed. Detail: new status + reason |
| `claimed` | Agent is starting work (also writes `.wip` file) |
| `released` | Agent released claim without completing |
| `note` | Free-form annotation |

Lines are never edited or deleted. To correct an error, append a new line.

### Body section

Free-form markdown. Convention for actionable tickets:

```
## Context
Why this work exists.

## Actions
1. Concrete steps.

## Test
First test to write (TDD red step).

## Exit criteria
Definition of done.
```

Not enforced by the validator. Agents are encouraged to follow the convention
but the body is structurally unconstrained.

## Cross-worktree coordination

### Claim protocol

Claims prevent two worktrees on the same machine from working on the same ticket.

Claims use `.git/ticket-wip/` (shared across worktrees via `git-common-dir`):

1. **Check:** read `.git/ticket-wip/{ID}.wip`. If it exists, ticket is claimed.
2. **Claim:** write the file with content `{timestamp} {actor} {worktree-path}`.
3. **Release:** delete the file (on close, abandon, or session end).

`.wip` files are local-only (inside `.git/`, never committed). They survive
across sessions but not across clones.

### Ready query

A ticket is **ready** when:
- `Status: open` (not `doing`, not `closed`, not `pending`)
- Every `Blocked-by` local ref points to a `Status: closed` ticket
- Every `Blocked-by: gh#N` is either resolved via API or treated as satisfied (offline)
- No `.wip` file exists for its ID

### Archive criteria

A ticket is **archivable** when:
- `Status: closed`
- Last log entry older than 90 days
- Not referenced by any live ticket's `Blocked-by` header (DAG safety)

Archive moves the file to `tickets/archive/` via `git mv`.

## Validator rules (pre-commit)

The Go validator enforces:
1. Magic first line is `%erg v1` (reject unknown versions)
2. All required headers present
3. No unknown headers
4. `Status` value is in the enum (`open`, `doing`, `closed`, `pending`)
5. `Created` is a valid ISO date (`YYYY-MM-DD`)
6. Filename matches `NNNN-{slug}.erg` pattern (4-digit ID, ASCII slug)
7. No duplicate IDs across `tickets/` and `tickets/archive/`
8. `Blocked-by` local refs point to existing ticket IDs
9. No dependency cycles
10. Log lines match `{timestamp} {actor} {verb}` format
11. Both `--- log ---` and `--- body ---` separators present

## Relationship to GitHub Issues

| Concern | Tool |
|---------|------|
| Local work organization | `.erg` files |
| Cross-worktree deconfliction | `.git/ticket-wip/` |
| Multi-agent coordination | GitHub Issues |
| Public visibility, review | GitHub Issues + PRs |

A ticket may reference a GitHub issue (`Blocked-by: gh#435`) but never
caches it. The two systems are independent.

## Postel's Law

**Strict on write, tolerant on read.** The validator enforces `%erg v1`
on commit. But you — the agent — are the parser for arbitrary input. If you
receive ticket-like information in any form (raw JSON from `gh`, a sentence,
a markdown sketch), understand the intent and write clean `%erg v1`. The
pre-commit hook catches mistakes. The tolerance is in you, not the tooling.
