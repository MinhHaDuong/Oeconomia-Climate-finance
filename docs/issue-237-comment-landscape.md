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
- **Zero dependencies** beyond Claude Code itself
- **Free worktree sync** via git (tickets are just files)
- **Text merges** work naturally for concurrent edits
- **PR-compatible** — ticket state changes travel with code changes
- **Dragon Dreaming phases** encoded in frontmatter (no tool supports this natively)
- **Dependency tracking** via frontmatter fields (`blocked_by: [t42, t43]`) — parse with a 20-line script or let the agent read YAML directly
- **`ready` computation** — a skill that greps frontmatter for `status: open` where all `blocked_by` entries are `status: closed`. Simple, inspectable, no magic.

Steal the good ideas from Beads and tk:
- Hash-based IDs (not sequential — sequential counters require a central authority, which breaks under distributed/parallel creation)
- `blocked_by` / `discovered_from` / `supersedes` link types in frontmatter
- `ready` command as a skill
- Memory compaction as a periodic sweep skill

Skip what doesn't fit:
- Dolt DB layer
- Daemon processes
- Push-to-main workflow
- External binary dependencies

The harness already has runbooks for `new-ticket`, `start-ticket`, `review-pr`, `celebrate`. These become the workflow engine. The ticket files become the data layer. No new tools needed.
