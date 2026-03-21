Gh-issue: #237
Title: Local ticket system for agent workflows
Author: minh, claude
Status: draft
Type: design
Created: 2026-03-21
Post-History: 2026-03-21 (landscape survey, design discussion, motivation correction)

# Local ticket system for agent workflows

## Abstract

Claude Code App cannot access forge CLIs (`gh`, `gl`). This makes forge-hosted issue trackers unusable as the agent's primary work queue. We propose a lightweight local ticket format — plain text files with RFC 822 headers in `tickets/` — to serve as the agent's native work surface. Forge issues remain the coordination layer for human-facing, cross-repo work. The two systems coexist permanently; neither subsumes the other.

## Motivation

### The forcing function

Claude Code App runs in a sandboxed environment without access to forge CLIs. There is no `gh issue list`, no `gh issue create`, no `gh issue view`. The agent literally cannot read or write GitHub Issues.

This is not a convenience problem — it is a capability gap. An agent that cannot access the issue tracker cannot:

- Pick the next task from a prioritized backlog
- Create sub-tickets discovered during execution
- Update ticket status as work progresses
- Check what blocks a ticket before starting it

Without a local alternative, the agent is blind to its own work queue. Every session starts with the human copy-pasting issue content into the conversation, and every sub-task discovered mid-session either gets lost or pollutes the chat context.

### Secondary benefits

Once the primary constraint forces us to a local ticket system, several bonuses follow:

- **Speed.** Creating a file is instant. No API call, no network round-trip, no rate-limit handling.
- **Worktree portability.** Tickets travel with `git` — every worktree has the full backlog, every branch can carry ticket state changes alongside code.
- **Offline-first.** Agents in worktrees, CI containers, or air-gapped environments work identically.
- **Workflow encoding.** Dragon Dreaming phases, TDD inner loop, dependency graphs — all expressible in headers. No forge supports these natively.
- **Noise reduction.** Small agent-internal tickets ("fix typo in §3.2", "rename variable") never pollute the forge tracker. The forge stays clean for human coordination.

These are real benefits, but they are not why we're doing this. We're doing this because the agent can't reach the forge.

## Design philosophy

1. **Two independent systems.** Local tickets and forge issues are separate. They can link via `Coordination: forge#N` but share no ID space and no sync layer.
2. **Natural attrition.** Existing forge issues close as their work completes. New small tickets are born local. The mix shifts organically.
3. **Promote is rare.** A local ticket can be upgraded to a forge issue if it turns out bigger than expected. This is the exception.
4. **Rollback is trivial.** Stop creating local tickets. The forge never stopped working. Nothing to undo.
5. **Cohabitation is permanent.** Some tickets will always be forge-hosted (cross-repo, external contributors). Both are first-class indefinitely.
6. **Forge-agnostic.** Works with GitHub, GitLab, Gitea, Forgejo, or no forge at all.

## Rationale

### Landscape survey

We surveyed existing distributed issue trackers and evaluated them against our constraints.

#### A. File-in-repo (git-native sync)

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **[Centy](https://centy.io)** | Markdown in `.centy/` | Node.js 20+, daemon | ~new | MIT | Yes (Claude Code integration) |
| **[ticket (tk)](https://github.com/wedow/ticket)** | Markdown + YAML in `.tickets/` | Bash, coreutils | ~new | MIT | Yes (designed for Claude) |
| **[git-issue](https://github.com/dspinellis/git-issue)** | Files in `.issues/` branch | jq, curl, GNU date | 864 | Apache-2.0 | Partial |
| **[Bugs Everywhere](https://bugseverywhere.readthedocs.io)** | Files in `.be/` | Python | ~old | GPLv2 | No |
| **[TrackDown](https://github.com/mgoellnitz/trackdown)** | Markdown in repo | Java/Gradle | small | Apache-2.0 | No |

#### B. Git-object (stored in refs, not files)

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **[git-bug](https://github.com/git-bug/git-bug)** | Git objects in `refs/bugs/` | Go binary | 9.7k | GPLv3 | Partial |
| **[git-appraise](https://github.com/google/git-appraise)** | Git notes in `refs/notes/` | Go binary | 6.2k | Apache-2.0 | No |

#### C. External database

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **[Beads (bd)](https://github.com/steveyegge/beads)** | Dolt DB in `.beads/` | Go + Dolt | 19.4k | MIT | Yes |
| **[Fossil](https://fossil-scm.org)** | SQLite (entire SCM) | C binary | N/A | BSD-2 | No |

#### D. Custom skills

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **Custom Claude Code skills** | RFC 822 files in `tickets/` | Claude Code | N/A | yours | Yes (by definition) |

### Analysis

#### File-in-repo (Centy, tk, git-issue)

**Pros:** git worktree sync for free, readable/greppable/diffable, PRs include ticket changes, zero infrastructure.

**Cons:** merge conflicts on concurrent edits, no structured dependency graph, no `ready` command, schema-free means schema-drift.

**Centy** — very new, Node.js daemon required, minimal docs. Too immature.

**ticket (tk)** — single bash script, dependency graph built-in, `tk ready` command. Most aligned with our needs, but brand new — no track record.

**git-issue** — mature but designed for humans. No JSON output, no dependency graph. Would need wrapping.

#### Git-object (git-bug)

**Pros:** clean working directory, excellent merge semantics (operation-based), forge bridges, JSON output, mature.

**Cons:** worktree problem (`refs/bugs/` behavior with `git worktree` is undertested — risk of corruption), no agent features (`claim`, `ready`, dependency graph), GPLv3.

#### External DB (Beads)

**Pros:** best dependency graph (`blocks`, `relates_to`, `discovered_from`, `supersedes`), `bd ready` transitive closure in ~10ms, atomic `--claim`, memory compaction.

**Cons:** second sync layer (Dolt push/pull on top of git), philosophy clash (push-to-main, no PRs), Dolt dependency in every environment, alpha status.

#### Fossil

Non-starter — replaces git entirely.

### The real cost of extra tooling

Each external tool introduces: installation burden, sync overhead, learning curve, new failure modes, philosophy mismatch. For a research project with one author and intermittent agent sessions, the overhead of Beads (Dolt + dual sync + push-to-main) or Centy (Node.js daemon) is disproportionate.

### The "DB in git" antipattern

1. **Binary blobs don't merge.** SQLite `.db` is opaque — concurrent worktree changes produce unresolvable conflicts.
2. **Dolt is not DB-in-git** — it's git-for-DBs: own merge algorithm, own remotes, own push/pull. Two parallel VCS.
3. **Repository bloat.** Binary blobs resist delta compression.
4. **Worktree isolation breaks.** Shared `.git/objects/` vs worktree-local DB files — syncing pollutes code history.

**Verdict:** either go full file-based (text merges naturally) or full external-DB (Dolt handles its own sync). The hybrid corrupts both.

### Conclusion

**Build custom skills wrapping plain text files with RFC 822 headers.**

Steal the good ideas:
- From Beads: `Blocked-by` header, `ready` command, memory compaction
- From tk: dependency graph, `X-Discovered-from` / `X-Supersedes` headers

Skip what doesn't fit:
- Dolt DB layer, daemon processes, push-to-main workflow, sequential IDs

---

## Specification

### File format

**Why RFC 822?** A ticket is a conversation — someone raises an issue, others respond, status evolves. Email solved this decades ago: structured headers for metadata, free-form body for content, append-only threading for history. Python chose the same format for PEPs (PEP 1), for the same reasons: greppable, human-readable, tool-friendly.

Not YAML — YAML requires a parser, has quoting gotchas, and doesn't compose with Unix pipes. RFC 822 headers work with bare `grep` and `cut`.

**The header set is open**, following RFC 822 conventions: standard headers that core tools understand, and `X-` extension headers for domain-specific metadata. The validator type-checks standard headers and passes `X-` headers through untouched.

**Standard headers:**

| Header | Required | Description |
|--------|----------|-------------|
| `Id` | yes | Initials of the semantic slug (e.g., `afg` from `auth-flow-gates`) |
| `Title` | yes | Short description |
| `Author` | yes | Creator |
| `Status` | yes | Current state (open, doing, closed, ...) |
| `Created` | yes | ISO date |
| `Coordination` | no | `local` (default) or `forge#N` (e.g., `gh#42`, `gl#42`) |
| `Assigned-to` | no | Agent or person owning the work |
| `Blocked-by` | no | ID of blocking ticket (repeatable) |

When `Coordination:` references a forge issue, add a `Forge-issue:` header with the full reference (e.g., `Forge-issue: gh#42`).

**X- extension headers:**

| Header | Domain | Description |
|--------|--------|-------------|
| `X-Phase` | Dragon Dreaming | dreaming, planning, doing, celebrating |
| `X-Parent` | hierarchy | ID of parent ticket (child->parent only) |
| `X-Discovered-from` | provenance | ID of ticket that led to this one |
| `X-Supersedes` | provenance | ID of replaced ticket |
| `X-Review-round` | peer review | R1, R2, R3 |
| `X-Comment-number` | peer review | Reviewer's comment number |
| `X-Section` | peer review | Manuscript section reference |
| `X-Page` | peer review | Page number |

List children via `grep -l "^X-Parent: {id}" tickets/*.ticket`. No reverse header — avoids a second source of truth. Same principle as `Blocked-by` (no `Blocks:` counterpart).

Projects add `X-` headers freely. If an extension proves universally useful, promote it to standard (drop the `X-` prefix).

**Structure** — three sections separated by marker lines:

1. **Header** (RFC 822 key-value pairs) — mutable, greppable current state. Ends at first blank line.
2. **Log** (after `--- log ---`) — append-only events. Format: `{ISO-timestamp} {agent-id} {event}`. Source of truth if header conflicts.
3. **Body** (after `--- body ---`) — free-form markdown description.

**Separator collision:** the parser uses only the *first* occurrence of each separator, scanning top-down. Body is always last, so duplicates inside it are harmless.

### Naming convention

Files: `{id}-{slug}.ticket` (e.g., `afg-auth-flow-gates.ticket`). The slug is freely chosen — it relates to the ticket's purpose but is not derived mechanically from the title. The ID is the initials of the slug words. Collisions get a numeric suffix (`afg2`). The `.ticket` extension avoids triggering Markdown linters. Branches: `t/{id}-{slug}`.

**Uniqueness enforcement** — two layers:

1. **At creation time** (`new-ticket` skill): check `ls tickets/{id}-*.ticket` before writing. If the ID exists, append next available suffix. Best-effort — concurrent agents can race past this.
2. **At commit time** (pre-commit validator): extract `Id:` from all ticket files, reject duplicates. Error reports next available suffix (e.g., `"duplicate Id 'wf' -- next available: wf3"`). No auto-fix — renaming an ID requires updating cross-references across files.

### Design decisions

- **Semantic slug IDs** — the ID is the initials of a freely chosen slug. No counter file, no hash, no ceremony. Collisions are rare at project scale; the numeric suffix handles them.
- **Mutable header + append-only log** — the header is a greppable index. The log is append-only history, merge-friendly at low concurrency (< 5 agents). If the header conflicts, replay the log to reconstruct it.
- **RFC 822 over YAML** — `Key: value` lines work with `grep` and `cut`. YAML needs a library.
- **Python first, Rust someday** — Python scripts (already in the project). Skills are shell commands, so the implementation swaps transparently. At < 200 tickets, Python is fast enough.
- **Rebuild, don't cache** — `ready` and `validate` scan all files on every call. No index, no cache. Git operations change files under you across worktrees. At < 200 tickets, full scan is milliseconds.
- **Two-tier contention:**
  - **`Coordination: local`** (default) — no protocol. Any agent can start. Duplicated work is cheap.
  - **`Coordination: forge#N`** — forge assignee is the single owner. Reserved for big tickets. Offline agents skip `forge#N` tickets entirely.

### Examples

**Development ticket:**

```
Id: afg
Title: Add authentication flow
Author: minh
Status: open
Created: 2026-03-21
Coordination: local
Assigned-to: agent-x
Blocked-by: cm
Blocked-by: fds
X-Discovered-from: prt
X-Phase: dreaming

--- log ---
2026-03-21T10:00Z agent-x created
2026-03-21T11:30Z agent-x status open
2026-03-21T14:00Z agent-x phase dreaming
2026-03-22T09:00Z agent-y blocked-by + cm
2026-03-22T09:00Z agent-y blocked-by + fds

--- body ---
Free-form description goes here.
Markdown OK.
```

**Peer review comment (future extension):**

```
Id: cmcd
Title: R1.3 -- Clarify methodology for COP funding data
Author: reviewer-1
Status: pending
Created: 2026-03-21
X-Review-round: R1
X-Comment-number: 3
X-Section: 3.2
X-Page: 12

--- log ---
2026-03-21T10:00Z reviewer-1 created
2026-03-25T14:00Z minh status pending -> addressed

--- body ---
The methodology for aggregating COP funding commitments is unclear.
How are pledges vs disbursements distinguished? Table 3 seems to
mix both without explanation.

--- response ---
Added paragraph in 3.2 distinguishing pledges from disbursements.
Table 3 now has separate columns. See commit abc1234.
```

### One-liner queries

```bash
# All open tickets
grep -l "^Status: open" tickets/*.ticket

# Tickets in doing phase
grep -l "^X-Phase: doing" tickets/*.ticket

# What blocks ticket afg?
grep "^Blocked-by:" tickets/afg-*.ticket | cut -d' ' -f2

# Tickets with no blockers
grep -rL "^Blocked-by:" tickets/*.ticket

# Count tickets by status
grep "^Status:" tickets/*.ticket | cut -d' ' -f2 | sort | uniq -c | sort -rn

# History of a ticket
sed -n '/^--- log ---$/,/^--- body ---$/p' tickets/afg-*.ticket
```

The only query needing Python is `ready` (open tickets where all `Blocked-by` refs point to closed tickets) — a graph traversal, not a text filter.

### Forge compatibility

The system is forge-optional, not forge-hostile:

- **Big tickets** use the forge for coordination (`Coordination: gh#N`). The forge issue is real — assignee, comments, external visibility.
- **Small tickets** are local-only. No forge noise.
- **PRs still go through the forge.** Code review is unchanged.
- **Forge CLI available but not required.** Agents without `gh` work on `local` tickets. Offline-first by default.
- **Prefix convention:** `gh#N` (GitHub), `gl#N` (GitLab), `gt#N` (Gitea/Forgejo).

### Transition

No migration. Existing forge issues close naturally. New small tickets are born local. The mix shifts organically. If local tickets don't work out, stop creating them — nothing to undo.

The harness already has runbooks for `new-ticket`, `start-ticket`, `review-pr`, `celebrate`. These become the workflow engine. The ticket files become the data layer.
