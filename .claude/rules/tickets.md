# Ticket format spec — %ticket v1

## Overview

Local ticket system for agent coordination across worktrees on one machine.
Not a replacement for GitHub Issues — those handle inter-agent and human coordination.
Tickets are committed to git and travel with the repo.

## File format

Extension: `.ticket`
Location: `tickets/` (active), `tickets/archive/` (closed, old)
Encoding: UTF-8, LF line endings.

### Magic first line

```
%ticket v1
```

Every `.ticket` file starts with this line. It declares the format version
and enables file-type detection without relying on the extension.

### Structure

```
%ticket v1
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

A blank line ends the header block. Both separators are required.

### Headers (closed set, v1)

| Header | Required | Type | Values |
|--------|----------|------|--------|
| `Title` | yes | string | Short imperative sentence |
| `Status` | yes | enum | `open`, `doing`, `closed` |
| `Created` | yes | date | `YYYY-MM-DD` |
| `Author` | yes | string | Agent or human identifier |
| `Blocked-by` | no | ref | Ticket ID or `gh#N` (repeatable) |
| `Labels` | no | string | Comma-separated tags |

No other headers are valid in v1. No `X-` extensions.

**`Blocked-by` references:**
- A bare ID (e.g., `0041`) refers to a local ticket.
- `gh#N` refers to a GitHub issue. Resolved via API when online, treated as
  satisfied (non-blocking) when offline.
- Repeatable: one `Blocked-by:` line per dependency.

### ID assignment

The ticket ID is derived from the filename, not a header.

Filename pattern: `{ID}-{slug}.ticket`
- ID: zero-padded sequential number, 4 digits. `0001`, `0002`, ...
- Slug: lowercase kebab-case summary. `add-validation`, `fix-cycle-bug`.

To assign the next ID:
```
ls tickets/*.ticket tickets/archive/*.ticket 2>/dev/null \
  | sed 's|.*/||; s|-.*/||' | sort -n | tail -1
```
Increment by 1, zero-pad to 4 digits. If the directory is empty, start at `0001`.

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
- `Status: open`
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
1. Magic first line is `%ticket v1`
2. All required headers present
3. No unknown headers
4. `Status` value is in the enum
5. `Created` is a valid ISO date
6. Filename ID matches `NNNN-slug` pattern
7. No duplicate IDs across `tickets/` and `tickets/archive/`
8. `Blocked-by` local refs point to existing ticket IDs
9. No dependency cycles
10. Log lines match `{timestamp} {actor} {verb}` format

## Relationship to GitHub Issues

| Concern | Tool |
|---------|------|
| Local work organization | `.ticket` files |
| Cross-worktree deconfliction | `.git/ticket-wip/` |
| Multi-agent coordination | GitHub Issues |
| Public visibility, review | GitHub Issues + PRs |

A ticket may reference a GitHub issue (`Blocked-by: gh#435`) but never
caches it. The two systems are independent.
