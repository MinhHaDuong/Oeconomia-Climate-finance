# Landscape analysis: distributed issue trackers for agent workflows

**Context:** #237 asks for an offline, file-based, gh-optional ticket system. This comment surveys the existing ecosystem and evaluates fit with our multi-worktree, PR-based, Dragon Dreaming workflow.

## The contenders

### A. File-in-repo approaches (git-native sync for free)

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **[Centy](https://centy.io)** | Markdown files in `.centy/` | Node.js 20+, daemon | ~new | MIT | Yes (Claude Code integration advertised) |
| **[ticket (tk)](https://github.com/wedow/ticket)** | Markdown + YAML frontmatter in `.tickets/` | Bash, coreutils (jq, rg optional) | ~new | MIT | Yes (designed for Claude Opus) |
| **[git-issue](https://github.com/dspinellis/git-issue)** | Files in `.issues/` git branch | jq, curl, GNU date | 864 | Apache-2.0 | Partial (scriptable, no JSON mode) |
| **[Bugs Everywhere](https://bugseverywhere.readthedocs.io)** | Files in `.be/` | Python | ~old | GPLv2 | No (designed pre-AI era) |
| **[TrackDown](https://github.com/mgoellnitz/trackdown)** | Markdown files in repo | Java/Gradle | small | Apache-2.0 | No |

### B. Git-object approaches (not files, stored in git refs)

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **[git-bug](https://github.com/git-bug/git-bug)** | Git objects in `refs/bugs/` | Go binary | 9.7k | GPLv3 | Partial (JSON output, TUI, bridges) |
| **[git-appraise](https://github.com/google/git-appraise)** | Git notes in `refs/notes/` | Go binary | 6.2k | Apache-2.0 | No (code review, not issues) |

### C. External database approaches

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **[Beads (bd)](https://github.com/steveyegge/beads)** | Dolt DB in `.beads/` | Go binary + Dolt | 19.4k | MIT | Yes (designed for agents) |
| **[Fossil](https://fossil-scm.org)** | SQLite DB (entire SCM) | C binary | N/A | BSD-2 | No (replaces git entirely) |

### D. The "just use custom skills" approach

| Tool | Storage | Deps | Stars | License | Agent-ready |
|------|---------|------|-------|---------|-------------|
| **Custom Claude Code skills** | Markdown/YAML files in `tickets/` | Claude Code | N/A | yours | Yes (by definition) |

## Analysis by architecture class

### File-in-repo (Centy, tk, git-issue): natural fit, but...

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

### Git-object (git-bug): elegant but friction with worktrees

**Pros:**
- Clean working directory (issues don't clutter file tree)
- Excellent merge semantics (operation-based, not text-based)
- GitHub/GitLab bridges for bidirectional sync
- JSON output, 9.7k stars, GPLv3, mature

**Cons:**
- **Worktree problem:** git objects are shared across worktrees (they live in `.git/objects/`), but refs may not be. `git-bug` stores in `refs/bugs/` — behavior with `git worktree` is undertested. Risk of corruption or stale reads.
- No agent-specific features (no `claim`, no `ready`, no dependency graph)
- GPLv3 license may matter if harness becomes a distributable tool

### External DB (Beads): powerful but adds a sync layer

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

### Fossil: non-starter

Replaces git entirely. Not compatible with our git-based workflow. Mentioned for completeness only.

## Unfit with extra tooling: the real cost

Each external tool introduces:

1. **Installation burden** — every new machine, container, CI runner needs the tool
2. **Sync overhead** — DB-based tools need their own push/pull cycle on top of git
3. **Learning curve** — agents need instructions for the tool; humans need docs
4. **Failure modes** — more moving parts = more ways to break
5. **Philosophy mismatch** — tools encode their creator's workflow assumptions

For a research project with one author and intermittent agent sessions, the overhead of Beads (Dolt install + dual sync + push-to-main philosophy) or even Centy (Node.js daemon) is disproportionate to the benefit.

## The "DB in git" approach: analysis

Storing a database file (SQLite, Dolt) inside git has fundamental problems:

1. **Binary blobs don't merge.** Git can merge text files line-by-line. A SQLite `.db` file is opaque binary — concurrent changes in different worktrees produce a merge conflict that git cannot resolve. You must pick one side entirely.
2. **Dolt solves this differently.** Dolt is *not* a DB-in-git — it's a git-for-DBs. It has its own merge algorithm, its own remotes, its own push/pull. This means two parallel version-control systems.
3. **Repository bloat.** Every DB state change creates a new binary blob. Git can't delta-compress binaries efficiently. Over months, the repo grows.
4. **Worktree isolation breaks.** Git worktrees share `.git/objects/`. A DB file in the working tree is worktree-local, but syncing it requires commits+merges that pollute the code history.

**Verdict:** "DB in git" is an antipattern for this use case. Either go full file-based (text merges naturally) or full external-DB (Dolt handles its own sync). The hybrid corrupts both.

## Recommendation for #237

**Build custom skills wrapping plain markdown files** — the approach sketched in the overnight runbook (option B: YAML frontmatter with status tracking).

Rationale:
- **Zero dependencies** beyond Claude Code and Python (already in the project)
- **Free worktree sync** via git (tickets are just files)
- **Append-only logs** for conflict resolution — ticket files are append-only event streams (like git-bug's operation-based model). No in-place mutation of fields. Status changes, reassignments, and comments are appended as timestamped entries. Git merges appended lines cleanly; concurrent edits to the same ticket don't conflict.
- **PR-compatible** — ticket state changes travel with code changes
- **Dragon Dreaming phases** encoded in frontmatter (no tool supports this natively)
- **Dependency tracking** via frontmatter fields (`blocked_by: [a3b8f2, c7d9e1]`) — parse with Python or let the agent read YAML directly
- **`ready` computation** — a Python skill that parses frontmatter, walks the dependency graph, and returns tickets whose blockers are all closed. Simple, inspectable, no magic.
- **Schema validation** — a pre-commit check validates that ticket frontmatter contains required fields (`id`, `title`, `status`, `created`) and that `blocked_by` references exist. Prevents schema drift over time.

### File format

RFC 822 style headers (like email), not YAML — designed so most queries are bash one-liners with standard Unix tools.

```
Id: a3b8f2c
Title: Add authentication flow
Status: open
Phase: dreaming
Created: 2026-03-21
Author: minh
Coordination: local
Blocked-by: c7d9e1
Blocked-by: f4a2b8
Discovered-from: 9e1c3d

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

**Structure:** mutable header (greppable current state) + append-only log (merge-safe history) + free-form body. If the header conflicts on merge, replay the log to reconstruct. The log only appends lines, so git merges it cleanly.

**One-liner examples** (Unix philosophy — each query is a pipeline):

```bash
# All open tickets
grep -l "^Status: open" tickets/*.md

# Tickets in doing phase
grep -l "^Phase: doing" tickets/*.md

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

### Naming convention

Ticket files are named `{hash}-{slug}.md` (e.g., `a3b8f2c-add-auth-flow.md`). The hash is the canonical ID (content-addressable, distributed-safe). The slug is human-readable context. Branches follow the same pattern: `t/a3b8f2c-add-auth-flow`.

### Design decisions

- **Hash-based IDs, not sequential** — sequential counters require a central authority, which breaks under distributed/parallel creation. Short hash prefixes (like git) for usability.
- **Mutable header + append-only log** — the header is a greppable index of current state (fast Unix one-liners). The log is append-only history (merge-safe). If concurrent edits conflict on the header, the log is the source of truth to reconstruct it. Trade-off: header can conflict, but at <5 agents and >200 tickets, simultaneous edits to the same ticket are rare.
- **RFC 822 headers, not YAML** — `Key: value` lines are greppable with bare `grep` and `cut`. No parser needed for simple queries. YAML requires a library to handle correctly (quoting, multiline, anchors). Email-style headers are the simplest format that works with Unix pipes.
- **Python first, Rust someday** — start with Python scripts (the project already depends on Python everywhere). Skills are shell commands, so the implementation can be swapped to a compiled Rust binary later if performance matters — the interface stays the same. At <200 tickets, Python is fast enough and faster to iterate on.
- **Rebuild, don't cache** — `ready` and `validate` scan all ticket files on every call. No index, no cache. A cache is a second source of truth that needs invalidation, and git operations (checkout, merge, rebase) change files under you across worktrees. At <200 tickets, a full scan is milliseconds. If it gets slow, profile first — the fix is faster parsing (ripgrep, Rust), not a cache layer.
- **Two-tier contention policy** — the `Coordination:` header field controls how agents claim work:
  - **`Coordination: local`** (default) — no coordination protocol. Any agent can start working on the ticket without asking. If two agents independently produce solutions, the author reviews both PRs and picks the better one. Duplicated work is cheap (agent compute is abundant), and competition can surface better solutions. Best for small, well-scoped tickets where the cost of wasted work is low.
  - **`Coordination: gh#N`** with `Assigned-to: agent-name` — the ticket is registered as GitHub issue #N. The GitHub assignee is the single owner. Other agents must check `gh issue view N` before starting — if already assigned, skip it. This adds a GitHub dependency but provides real coordination. Reserved for big tickets where duplicate work would be wasteful (multi-day effort, complex cross-cutting changes, tickets that touch many files).
  - **The decision happens at creation time.** The `new-ticket` skill asks: is this big? If the ticket spans multiple subsystems, requires multi-day work, or has high coordination cost if duplicated, it gets `gh#N`. Otherwise it stays `local`. When in doubt, default to `local` — you can always upgrade a ticket to `gh#N` later, but you can't un-waste the coordination overhead.

Steal the good ideas from Beads and tk:
- `blocked_by` / `discovered_from` / `supersedes` link types in frontmatter
- `ready` command as a skill
- Memory compaction as a periodic sweep skill

Skip what doesn't fit:
- Dolt DB layer
- Daemon processes
- Push-to-main workflow
- Sequential IDs

The harness already has runbooks for `new-ticket`, `start-ticket`, `review-pr`, `celebrate`. These become the workflow engine. The ticket files become the data layer. No new tools needed.
