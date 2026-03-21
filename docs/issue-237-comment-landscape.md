Gh-issue: #237
Title: Distributed issue tracking for agent workflows
Author: minh, claude
Status: draft
Type: design
Created: 2026-03-21
Post-History: 2026-03-21 (landscape survey, design discussion)

# Distributed issue tracking for agent workflows

## Abstract

This document surveys existing distributed issue trackers and proposes a lightweight local ticket format to complement forge-hosted issue trackers (GitHub Issues, GitLab Issues, etc.). Local tickets handle small, fast, agent-scoped work. The forge handles coordination-heavy, externally-visible work. Neither subsumes the other — cohabitation is the permanent state.

## Motivation

### The concrete problem

This project — a climate finance history written with Claude Code agents — hit the limits of forge-hosted issue trackers early. A typical session: the agent plans a chapter revision, discovers that the data pipeline needs a fix, the fix reveals a test gap, and the test gap spawns a documentation update. That's four tickets from one planning step. Over a week of overnight autonomous sessions, the GitHub issue tracker accumulated dozens of agent-internal tickets that only agents read — drowning the few human-facing issues that matter for coordination.

The problem is not GitHub-specific. GitLab, Gitea, Forgejo — any forge-hosted tracker has the same friction for this pattern. The mismatch is between *forge trackers* (designed for human coordination across repositories) and *agent workflows* (high-volume, short-lived, branch-scoped, offline-capable).

### Why forge trackers don't fit agent work

Forge-hosted issue trackers (GitHub Issues, GitLab Issues, Gitea, etc.) work well for coordination — cross-repo visibility, external contributors, assignee-based ownership. But agent workflows create tickets that forges were not designed for:

- **Volume.** Agents discover sub-tasks during execution. A single planning session can spawn 5–10 tickets. At that rate, the forge issue tracker fills with noise that only agents read.
- **Locality.** Small tickets ("fix typo in §3.2", "rename variable in pipeline.py") live and die within one branch. They never need external visibility. Creating a forge issue, assigning it, closing it — all overhead for a five-minute edit.
- **Offline.** Agents working in worktrees may not have network access. Forge APIs require it. A local ticket file works regardless.
- **Workflow mismatch.** Our Dragon Dreaming phases (dreaming → planning → doing → celebrating) and TDD inner loop (red → green → refactor) have no forge equivalent. We encode them in conventions that no forge can enforce.
- **Speed.** Creating a file is instant. Creating a forge issue requires an API call, a network round-trip, and error handling for rate limits and auth failures.

None of these problems justify *replacing* the forge tracker. They justify *complementing* it with a lightweight local layer for the small/fast/agent-scoped work that forge trackers handle poorly.

## Design philosophy

1. **Two independent systems, not one with two backends.** Local tickets and forge issues are separate systems that can optionally link via `Coordination: forge#N`. No shared ID space, no sync layer.
2. **Natural attrition, not migration.** Forge issues close when their work gets done. New small tickets are born local. The mix shifts organically.
3. **Promote is rare, not routine.** A local ticket can be upgraded to a forge issue if it turns out bigger than expected. This is the exception. There is no routine promotion workflow.
4. **Rollback is trivial.** Stop creating local tickets. The forge never stopped working. Nothing to undo.
5. **Cohabitation is permanent.** Some tickets will always be forge-hosted (cross-repo, external contributors). Both are first-class indefinitely.
6. **Forge-agnostic.** The local ticket system works with any git forge — GitHub, GitLab, Gitea, Forgejo, or none at all. The `Coordination:` header uses a forge-specific prefix (`gh#N`, `gl#N`, etc.) only when linking to a specific forge issue. The rest of the system is pure git.

## Rationale

We surveyed the landscape of distributed issue trackers, evaluated them against our constraints, and concluded that custom skills wrapping plain text files are the best fit. This section documents what we considered and why we rejected it.

### Landscape survey

#### A. File-in-repo approaches (git-native sync for free)

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **[Centy](https://centy.io)** | Markdown files in `.centy/` | Node.js 20+, daemon | ~new | MIT | Yes (Claude Code integration advertised) |
| **[ticket (tk)](https://github.com/wedow/ticket)** | Markdown + YAML frontmatter in `.tickets/` | Bash, coreutils (jq, rg optional) | ~new | MIT | Yes (designed for Claude Opus) |
| **[git-issue](https://github.com/dspinellis/git-issue)** | Files in `.issues/` git branch | jq, curl, GNU date | 864 | Apache-2.0 | Partial (scriptable, no JSON mode) |
| **[Bugs Everywhere](https://bugseverywhere.readthedocs.io)** | Files in `.be/` | Python | ~old | GPLv2 | No (designed pre-AI era) |
| **[TrackDown](https://github.com/mgoellnitz/trackdown)** | Markdown files in repo | Java/Gradle | small | Apache-2.0 | No |

#### B. Git-object approaches (not files, stored in git refs)

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **[git-bug](https://github.com/git-bug/git-bug)** | Git objects in `refs/bugs/` | Go binary | 9.7k | GPLv3 | Partial (JSON output, TUI, bridges) |
| **[git-appraise](https://github.com/google/git-appraise)** | Git notes in `refs/notes/` | Go binary | 6.2k | Apache-2.0 | No (code review, not issues) |

#### C. External database approaches

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **[Beads (bd)](https://github.com/steveyegge/beads)** | Dolt DB in `.beads/` | Go binary + Dolt | 19.4k | MIT | Yes (designed for agents) |
| **[Fossil](https://fossil-scm.org)** | SQLite DB (entire SCM) | C binary | N/A | BSD-2 | No (replaces git entirely) |

#### D. The "just use custom skills" approach

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **Custom Claude Code skills** | RFC 822 text files in `tickets/` | Claude Code | N/A | yours | Yes (by definition) |

### Analysis by architecture class

#### File-in-repo (Centy, tk, git-issue): natural fit, but...

**Pros:**
- Git worktrees get ticket sync for free — no second sync layer
- Readable with any text editor, greppable, diffable
- PRs can include ticket state changes alongside code
- Zero extra infrastructure

**Cons:**
- Merge conflicts on concurrent ticket edits (two agents update same file)
- No structured dependency graph (you build it yourself or go without)
- No `ready` command computing transitive closure of blockers
- Schema-free means schema-drift over time

**Centy** specifically: very new, requires Node.js daemon (extra process to manage), minimal documentation available. Too immature to evaluate properly.

**ticket (tk)** specifically: single bash script, dependency graph built-in, `tk ready` command, YAML frontmatter gives structure. Includes `migrate-beads` command (positioned as Beads replacement). Most aligned with our needs among file-based tools. But brand new — no track record.

**git-issue** specifically: mature (864 stars, tested on multiple platforms), but designed for humans not agents. No JSON output, no dependency graph, no `ready` queue. Would need wrapping.

#### Git-object (git-bug): elegant but friction with worktrees

**Pros:**
- Clean working directory (issues don't clutter file tree)
- Excellent merge semantics (operation-based, not text-based)
- GitHub/GitLab bridges for bidirectional sync
- JSON output, 9.7k stars, GPLv3, mature

**Cons:**
- **Worktree problem:** git objects are shared across worktrees (they live in `.git/objects/`), but refs may not be. `git-bug` stores in `refs/bugs/` — behavior with `git worktree` is undertested. Risk of corruption or stale reads.
- No agent-specific features (no `claim`, no `ready`, no dependency graph)
- GPLv3 license may matter if harness becomes a distributable tool

#### External DB (Beads): powerful but adds a sync layer

**Pros:**
- Best dependency graph (`blocks`, `relates_to`, `discovered_from`, `supersedes`)
- `bd ready` computes transitive closure in ~10ms
- Atomic `--claim` prevents double-work in multi-agent setups
- Memory compaction preserves context window budget
- 19.4k stars, active development

**Cons:**
- **Second sync layer.** Each worktree has its own `.beads/` Dolt DB. Syncing requires `bd dolt push/pull` on top of `git push/pull`. Two version-control systems to keep coordinated.
- **Philosophy clash.** Beads prescribes "push to main, never create PRs." Our workflow requires PRs for review gates. Beads' `--claim` assumes a single-main workflow.
- **Dolt dependency.** MySQL-compatible but still an extra binary to install and maintain. Agents need it available in every environment.
- **Alpha status** (pre-1.0). CLI API may change.

#### Fossil: non-starter

Replaces git entirely. Not compatible with our git-based workflow. Mentioned for completeness only.

### The real cost of extra tooling

Each external tool introduces:

1. **Installation burden** — every new machine, container, CI runner needs the tool
2. **Sync overhead** — DB-based tools need their own push/pull cycle on top of git
3. **Learning curve** — agents need instructions for the tool; humans need docs
4. **Failure modes** — more moving parts = more ways to break
5. **Philosophy mismatch** — tools encode their creator's workflow assumptions

For a research project with one author and intermittent agent sessions, the overhead of Beads (Dolt install + dual sync + push-to-main philosophy) or even Centy (Node.js daemon) is disproportionate to the benefit.

### The "DB in git" antipattern

Storing a database file (SQLite, Dolt) inside git has fundamental problems:

1. **Binary blobs don't merge.** Git can merge text files line-by-line. A SQLite `.db` file is opaque binary — concurrent changes in different worktrees produce a merge conflict that git cannot resolve. You must pick one side entirely.
2. **Dolt solves this differently.** Dolt is *not* a DB-in-git — it's a git-for-DBs. It has its own merge algorithm, its own remotes, its own push/pull. This means two parallel version-control systems.
3. **Repository bloat.** Every DB state change creates a new binary blob. Git can't delta-compress binaries efficiently. Over months, the repo grows.
4. **Worktree isolation breaks.** Git worktrees share `.git/objects/`. A DB file in the working tree is worktree-local, but syncing it requires commits+merges that pollute the code history.

**Verdict:** "DB in git" is an antipattern for this use case. Either go full file-based (text merges naturally) or full external-DB (Dolt handles its own sync). The hybrid corrupts both.

## Recommendation

**Build custom skills wrapping plain text files with RFC 822 headers** — evolved from the overnight runbook's option B, refined through design discussion.

Rationale:
- **Zero dependencies** beyond Claude Code and Python (already in the project)
- **Free worktree sync** via git (tickets are just files)
- **Mutable header + append-only log** — the header holds current state (greppable with Unix tools). The log section is append-only history (merge-safe). If concurrent edits conflict on the header, replay the log to reconstruct. Inspired by git-bug's operation-based model, but using plain text instead of git objects.
- **PR-compatible** — ticket state changes travel with code changes
- **Dragon Dreaming phases** encoded in frontmatter (no tool supports this natively)
- **Dependency tracking** via RFC 822 headers (`Blocked-by: a3b8f2`, one per line) — parse with `grep | cut` or Python
- **`ready` computation** — a Python skill that parses headers, walks the dependency graph, and returns tickets whose blockers are all closed. Simple, inspectable, no magic.
- **Schema validation** — a pre-commit check validates that ticket headers contain required fields (`Id`, `Title`, `Status`, `Created`) and that `Blocked-by` references exist. Prevents schema drift over time.

### Design decisions

- **Random short IDs, not sequential** — sequential counters require a central authority. A 7-char random hex (`secrets.token_hex(4)[:7]`) is unique enough at <200 tickets and simpler than content-addressable hashing.
- **Mutable header + append-only log** — the header is a greppable index of current state (fast Unix one-liners). The log is append-only history (merge-safe). If concurrent edits conflict on the header, the log is the source of truth to reconstruct it. Trade-off: header can conflict, but at <5 agents and >200 tickets, simultaneous edits to the same ticket are rare.
- **RFC 822 headers, not YAML** — `Key: value` lines are greppable with bare `grep` and `cut`. No parser needed for simple queries. YAML requires a library to handle correctly (quoting, multiline, anchors). Email-style headers are the simplest format that works with Unix pipes.
- **Python first, Rust someday** — start with Python scripts (the project already depends on Python everywhere). Skills are shell commands, so the implementation can be swapped to a compiled Rust binary later if performance matters — the interface stays the same. At <200 tickets, Python is fast enough and faster to iterate on.
- **Rebuild, don't cache** — `ready` and `validate` scan all ticket files on every call. No index, no cache. A cache is a second source of truth that needs invalidation, and git operations (checkout, merge, rebase) change files under you across worktrees. At <200 tickets, a full scan is milliseconds. If it gets slow, profile first — the fix is faster parsing (ripgrep, Rust), not a cache layer.
- **Two-tier contention policy** — the `Coordination:` header field controls how agents claim work:
  - **`Coordination: local`** (default) — no coordination protocol. Any agent can start working on the ticket without asking. If two agents independently produce solutions, the author reviews both PRs and picks the better one. Duplicated work is cheap (agent compute is abundant), and competition can surface better solutions. Best for small, well-scoped tickets where the cost of wasted work is low.
  - **`Coordination: forge#N`** with `Assigned-to: agent-name` — the ticket is registered as a forge issue (e.g., `gh#251` for GitHub, `gl#251` for GitLab). The forge assignee is the single owner. Other agents must check the forge before starting — if already assigned, skip it. This adds a forge dependency but provides real coordination. Reserved for big tickets where duplicate work would be wasteful (multi-day effort, complex cross-cutting changes, tickets that touch many files).
  - **The decision happens at creation time.** The `new-ticket` skill asks: is this big? If the ticket spans multiple subsystems, requires multi-day work, or has high coordination cost if duplicated, it gets a forge issue. Otherwise it stays `local`. When in doubt, default to `local` — you can always upgrade later, but you can't un-waste the coordination overhead.
  - **Example — `forge#N`:** "Refresh corpus from UNFCCC sources" — takes an hour, downloads large files, overwrites data files that other tickets depend on. Running it twice in parallel wastes bandwidth and risks conflicts. Gets `Coordination: gh#251`, one agent owns it.
  - **Example — `local`:** "Fix typo in chapter 3" — five-minute edit, single file. If two agents both fix it, the author picks the better PR in seconds. No coordination needed.

Steal the good ideas from Beads and tk:
- `Blocked-by` as standard header; `X-Discovered-from` / `X-Supersedes` as extension headers when needed
- `ready` command as a skill
- Memory compaction as a periodic sweep skill

Skip what doesn't fit:
- Dolt DB layer
- Daemon processes
- Push-to-main workflow
- Sequential IDs

### Forge compatibility

The system is forge-optional, not forge-hostile. It works with GitHub, GitLab, Gitea, Forgejo — or no forge at all:

- **Big tickets** use the forge for coordination (`Coordination: gh#N`, `gl#N`, etc.). The forge issue is real — it has an assignee, comments, and visibility to external collaborators.
- **Small tickets** are local-only. The forge never sees them. No noise in the issue tracker.
- **PRs/MRs still go through the forge.** The code review workflow is unchanged. Ticket state changes travel with the branch.
- **Forge CLI is available but not required.** Agents that can't reach the forge still work on `local` tickets. Offline-first by default, online when it matters.
- **Forge-specific prefix convention:** `gh#N` (GitHub), `gl#N` (GitLab), `gt#N` (Gitea/Forgejo). The prefix tells agents which API to query. Projects using a single forge just pick one prefix and stick with it.

### Transition: natural attrition

No migration. Existing forge issues close naturally as their work completes. New small/short-lived tickets are born local. The mix shifts organically. If local tickets don't work out, stop creating them — the forge never stopped working, nothing to undo.

The harness already has runbooks for `new-ticket`, `start-ticket`, `review-pr`, `celebrate`. These become the workflow engine. The ticket files become the data layer. No new tools needed.

---

## Specification

### File format

**Why RFC 822?** A ticket is a conversation — someone raises an issue, others respond, status evolves over time. Email solved this format problem decades ago: structured headers for metadata, free-form body for content, append-only threading for history. RFC 822 headers (`Key: Value` lines) are the natural format for this, and the same format Python chose for PEPs (PEP 1 specifies RFC 822 headers for the same reasons: greppable, human-readable, tool-friendly).

Not YAML — YAML requires a parser, has quoting gotchas, and doesn't compose with Unix pipes. RFC 822 headers work with bare `grep` and `cut`.

**The header set is open**, following RFC 822 conventions: a set of standard headers that core tools understand, and `X-` extension headers for domain-specific metadata. The validator type-checks standard headers and passes `X-` headers through untouched. This means the same format works for development tickets, peer review comments, and use cases we haven't imagined yet — without schema changes.

**Standard headers** (core tools know these):

| Header | Required | Description |
|--------|----------|-------------|
| `Id` | yes | Content-addressable hash |
| `Title` | yes | Short description |
| `Author` | yes | Creator |
| `Status` | yes | Current state (open, doing, closed, …) |
| `Created` | yes | ISO date |
| `Coordination` | no | `local` (default) or `forge#N` (e.g., `gh#42`, `gl#42`) |
| `Assigned-to` | no | Agent or person owning the work |
| `Blocked-by` | no | ID of blocking ticket (repeatable) |

When `Coordination:` references a forge issue, add a `Forge-issue:` header with the full reference (e.g., `Forge-issue: gh#42`). This header only appears on coordinated tickets — it is not a standard field for local tickets.

**X- extension headers** (domain-specific, ignored by core tools):

| Header | Domain | Description |
|--------|--------|-------------|
| `X-Phase` | Dragon Dreaming | dreaming, planning, doing, celebrating |
| `X-Discovered-from` | provenance | ID of parent ticket |
| `X-Supersedes` | provenance | ID of replaced ticket |
| `X-Review-round` | peer review (future) | R1, R2, R3 |
| `X-Comment-number` | peer review (future) | Reviewer's comment number |
| `X-Section` | peer review (future) | Manuscript section reference |
| `X-Page` | peer review (future) | Page number |

Projects add `X-` headers freely. If an extension proves universally useful, promote it to standard (drop the `X-` prefix).

**Structure:** three sections separated by marker lines:

1. **Header** (RFC 822 key-value pairs) — mutable, greppable current state. Ends at first blank line.
2. **Log** (after `--- log ---`) — append-only timestamped events. Merge-safe history. Source of truth if header conflicts.
3. **Body** (after `--- body ---`) — free-form markdown description.

**Separator collision:** the parser uses only the *first* occurrence of each separator, scanning top-down. Body is always last, so duplicates inside it are harmless.

### Naming convention

Ticket files are named `{id}-{slug}.md` (e.g., `a3b8f2c-add-auth-flow.md`). The ID is a random 7-char hex for uniqueness. The slug is human-readable context. Branches follow the same pattern: `t/a3b8f2c-add-auth-flow`.

### Examples

**Development ticket:**

```
Id: a3b8f2c
Title: Add authentication flow
Author: minh
Status: open
Created: 2026-03-21
Coordination: local
Assigned-to: agent-x
Blocked-by: c7d9e1
Blocked-by: f4a2b8
X-Discovered-from: 9e1c3d
X-Phase: dreaming

--- log ---
2026-03-21T10:00Z created
2026-03-21T11:30Z status open
2026-03-21T14:00Z phase dreaming
2026-03-22T09:00Z blocked-by + c7d9e1
2026-03-22T09:00Z blocked-by + f4a2b8

--- body ---
Free-form description goes here.
Markdown OK.
```

**Peer review comment (future extension):**

```
Id: r1c03a7
Title: R1.3 — Clarify methodology for COP funding data
Author: reviewer-1
Status: pending
Created: 2026-03-21
X-Review-round: R1
X-Comment-number: 3
X-Section: 3.2
X-Page: 12

--- log ---
2026-03-21T10:00Z created
2026-03-25T14:00Z status pending → addressed

--- body ---
The methodology for aggregating COP funding commitments is unclear.
How are pledges vs disbursements distinguished? Table 3 seems to
mix both without explanation.

--- response ---
Added paragraph in §3.2 distinguishing pledges from disbursements.
Table 3 now has separate columns. See commit a3b8f2c.
```

Peer review tickets add `X-` extension headers (`X-Review-round`, `X-Comment-number`, `X-Section`, `X-Page`) and a `--- response ---` section. The reviewer's words stay untouched in the body; the author's point-by-point reply goes in response.

### One-liner queries

Unix philosophy — each query is a pipeline:

```bash
# All open tickets
grep -l "^Status: open" tickets/*.md

# Tickets in doing phase
grep -l "^X-Phase: doing" tickets/*.md

# What blocks ticket a3b8f2c?
grep "^Blocked-by:" tickets/a3b8f2c-*.md | cut -d' ' -f2

# Tickets with no blockers
grep -rL "^Blocked-by:" tickets/*.md

# All ticket IDs
ls tickets/ | cut -d- -f1

# Count tickets by status
grep "^Status:" tickets/*.md | cut -d' ' -f2 | sort | uniq -c | sort -rn

# History of a ticket
sed -n '/^--- log ---$/,/^--- body ---$/p' tickets/a3b8f2c-*.md
```

The only query that needs Python is `ready` (open tickets where all `Blocked-by` refs point to closed tickets) — that's a graph traversal, not a text filter.

**Peer review one-liners:**

```bash
# Unaddressed comments from R1
grep -l "^Status: pending" tickets/r1c*.md

# All comments about section 3
grep -l "^X-Section: 3" tickets/r1c*.md

# Generate response document (all R1 comments + responses, in order)
for f in $(grep -l "^X-Review-round: R1" tickets/*.md | sort); do
  grep "^X-Comment-number:" "$f"
  sed -n '/^--- body ---$/,/^--- response ---$/p' "$f"
  sed -n '/^--- response ---$/,$p' "$f"
  echo
done
```
