Gh-issue: #237
Title: Local ticket system for agent workflows
Author: minh, claude
Status: draft
Type: design
Created: 2026-03-21
Post-History: 2026-03-21 (landscape survey, design discussion, motivation correction),
              2026-03-22 (PEP restructure, tooling implementation, review round)

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

## Rationale

### Design constraints

The ticket system is agnostic to:

- **Operating system.** Plain text + Python stdlib. No platform-specific APIs or paths.
- **Programming language.** Tickets describe work — the project's language is irrelevant. The reference tools are Python; reimplementation in any language is straightforward.
- **Forge.** Works with GitHub, GitLab, Gitea, Forgejo, or no forge at all. Forge CLIs are optional, never required.
- **Project size and kind.** Research papers, web apps, monorepos, single-file scripts. The format imposes no project structure beyond a `tickets/` directory.
- **Build system.** The spec defines CLI commands (`python tickets/tools/validate_tickets.py`). Whether a project wraps these in Make, Just, Taskfile, npm scripts, or bare shell aliases is a local implementation detail — not part of the spec.

### Design philosophy

1. **Two independent systems.** Local tickets and forge issues are separate. They can link via `Coordination: forge#N` but share no ID space and no sync layer.
2. **Natural attrition.** Existing forge issues close as their work completes. New small tickets are born local. The mix shifts organically.
3. **Promote is rare.** A local ticket can be upgraded to a forge issue if it turns out bigger than expected. This is the exception.
4. **Rollback is trivial.** Stop creating local tickets. The forge never stopped working. Nothing to undo.
5. **Cohabitation is permanent.** Some tickets will always be forge-hosted (cross-repo, external contributors). Both are first-class indefinitely.
6. **Forge-agnostic.** (See Design constraints above.)

### Design decisions

- **Semantic slug IDs** — the ID is the initials of a freely chosen slug. No counter file, no hash, no ceremony. At < 200 tickets, collisions are rare; the numeric suffix handles them.
- **Mutable header + append-only log** — the header is a greppable index. The log is append-only by convention; concurrent appends to the same ticket are rare at low agent counts and auto-merge correctly in most cases. If the header conflicts during merge, resolve manually — the log helps you understand what happened. At < 5 agents, header conflicts are rare and fast to resolve.
- **RFC 822 over YAML** — see [File format](#file-format) for the full rationale.
- **Reference implementation in Python** — Python stdlib only, no external deps. Skills are shell commands wrapping the scripts, so the implementation language swaps transparently. At < 200 tickets, Python is fast enough. A Rust/Go rewrite changes nothing about the format or protocol.
- **Rebuild, don't cache** — `ready` and `validate` scan all files on every call. No index, no cache. Git operations change files under you across worktrees. At < 200 tickets, full scan is milliseconds. If the ticket count outgrows this, the first lever is archival (see [Cleanup](#cleanup)); the second is indexing or switching to a database-backed tool.
- **Two-tier contention:**
  - **`Coordination: local`** (default) — no protocol. Any agent can start. Duplicated work is cheap.
  - **`Coordination: forge#N`** — forge assignee is the single owner. Reserved for big tickets. Offline agents skip `forge#N` tickets entirely.
- **No atomic claim primitive.** Two agents can both see a ticket as ready and start work concurrently. An atomic `claim` operation (e.g., compare-and-swap on `Status: doing` + `Assigned-to`) would prevent this, but at < 5 agents the duplication is rare and the cost of duplicated work is low. If contention grows, the mitigation is promotion to `Coordination: forge#N`, not a distributed lock.
- **No formal log grammar.** Log entries are free-form human-readable text (`{ISO-timestamp} {agent-id} {event}`). The `{event}` field is not parsed by tools — the log is audit history, not a machine-executable operation log. Formalizing event types (as a CRDT operation set) was considered and rejected: the complexity is disproportionate at this scale (see ticket `con`).
- **Direct Blocked-by, not transitive closure.** The `ready` command checks only direct `Blocked-by` references, not transitive ancestors. If A is blocked by B and B is blocked by C (open), A is already not-ready because B is open (not closed). Transitive closure would only matter if we checked "all ancestors closed" — we don't, so direct checking is correct and sufficient.

### Conclusion

**Build custom skills wrapping plain text files with RFC 822 headers.**

From the landscape survey (see [Rejected Ideas](#rejected-ideas)):
- Adopted from Beads: `Blocked-by` header, `ready` command
- Adopted from tk: dependency graph, `X-Discovered-from` / `X-Supersedes` headers
- Skipped: Dolt DB layer, daemon processes, push-to-main workflow, sequential IDs

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
| `Status` | yes | Current state: `open`, `doing`, `closed`, `pending` |
| `Created` | yes | ISO date |
| `Coordination` | no | `local` (default) or forge-prefix + issue number (e.g., `gh#42`, `gl#42`, `gt#7`) |
| `Assigned-to` | no | Agent or person owning the work |
| `Blocked-by` | no | ID of blocking ticket (repeatable) |
| `Forge-issue` | no | Full forge reference when `Coordination` uses a forge prefix (e.g., `gh#42`) |

`Coordination` controls workflow behavior (local vs. forge-assigned). `Forge-issue` is the greppable cross-reference for humans. They overlap on simple cases like `gh#42`; they diverge if the coordination protocol evolves (e.g., `Coordination: forge-assigned` vs. `Forge-issue: gh#42`).

Status values: `open` (available for work), `doing` (claimed, in progress), `closed` (completed or cancelled), `pending` (awaiting external input, e.g., peer review — excluded from `ready` output).

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

1. **Header** (RFC 822 key-value pairs) — current state. Ends at the first blank line; lines between the header block and the `--- log ---` separator are ignored.
2. **Log** (after `--- log ---`) — append-only events, in chronological order. Format: `{ISO-timestamp} {agent-id} {event}`. Aids manual resolution if headers conflict during merge.
3. **Body** (after `--- body ---`) — free-form markdown description. Domain-specific workflows may add further named separators inside the body (e.g., `--- response ---` in peer review tickets). These are not parsed by core tools — only `--- log ---` and `--- body ---` are structural.

**Separator collision:** the parser uses only the *first* occurrence of each separator, scanning top-down. Body is always last, so duplicates inside it are harmless.

### Naming convention

Files: `{id}-{slug}.ticket` (e.g., `afg-auth-flow-gates.ticket`). The slug is freely chosen — it relates to the ticket's purpose but is not derived mechanically from the title. Branches: `t/{id}-{slug}`.

**ID derivation** — split the slug on hyphens, take the first character of each part: `auth-flow-gates` → `afg`, `validate-tickets` → `vt`, `cycle-detection` → `cd`. The ID is set once at creation and treated as immutable; tools read it from the filename prefix, not by re-deriving it. Avoid single-word slugs (single-character IDs are collision-prone); prefer two or three words. Numeric slug parts contribute their first digit: `r2-fix` → `rf`.

Collisions get a numeric suffix starting at 2: `afg`, `afg2`, `afg3`, …. The `.ticket` extension avoids triggering Markdown linters.

**Slugs are ASCII.** IDs and filenames use `[a-z0-9]` only. Non-ASCII project names or titles should use romanized slugs (e.g., `données-climat` → `dc`).

**Uniqueness enforcement** — two layers:

1. **At creation time** (`new-ticket` skill): check `ls tickets/{id}-*.ticket` before writing. If the ID exists, append next available suffix. Best-effort — concurrent agents can race past this.
2. **At commit time** (pre-commit validator): extract `Id:` from all ticket files, reject duplicates. Error reports next available suffix (e.g., `"duplicate Id 'wf' -- next available: wf3"`). No auto-fix — renaming an ID requires updating cross-references across files.

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
Status: closed
Created: 2026-03-21
X-Review-round: R1
X-Comment-number: 3
X-Section: 3.2
X-Page: 12

--- log ---
2026-03-21T10:00Z reviewer-1 created
2026-03-25T14:00Z minh status pending -> closed

--- body ---
The methodology for aggregating COP funding commitments is unclear.
How are pledges vs disbursements distinguished? Table 3 seems to
mix both without explanation.

--- response ---
Added paragraph in 3.2 distinguishing pledges from disbursements.
Table 3 now has separate columns. See commit abc1234.
```

**Closed ticket:**

```
Id: cm
Title: Configure CI matrix
Author: agent-x
Status: closed
Created: 2026-03-20
Coordination: local

--- log ---
2026-03-20T09:00Z agent-x created
2026-03-20T09:00Z agent-x status open
2026-03-20T14:00Z agent-x status doing
2026-03-21T11:00Z agent-x status closed — merged PR #15

--- body ---
Set up GitHub Actions matrix for Python 3.11 and 3.12.
```

**Forge-coordinated ticket:**

```
Id: bap
Title: Build authentication pipeline
Author: minh
Status: doing
Created: 2026-03-19
Coordination: gh#42
Forge-issue: gh#42
Assigned-to: agent-y
X-Phase: doing

--- log ---
2026-03-19T10:00Z minh created
2026-03-19T10:00Z minh status open
2026-03-20T08:00Z agent-y assigned-to agent-y
2026-03-20T08:00Z agent-y status doing

--- body ---
Big cross-cutting feature requiring human coordination.
See gh#42 for discussion and scope.
```

**Conflict resolution scenario:**

Two agents edit the same ticket header concurrently — agent-x sets `Status: doing`, agent-y sets `Status: closed`. Git reports a merge conflict on the `Status:` line. The merge operator reads the log:

    2026-03-22T10:00Z agent-x status doing
    2026-03-22T10:05Z agent-y status closed — merged PR #18

The log shows agent-y's close happened after agent-x's claim. Resolution: accept `Status: closed`. The log is append-only, so both entries survive the merge — no history is lost.

### One-liner queries

These use GNU/BSD grep extensions (`-l`, `-L`, `-r`) — available on Linux and macOS out of the box. Strictly POSIX environments would need `xargs`-based equivalents.

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

Queries needing Python: `ready` (open tickets where all `Blocked-by` refs point to closed tickets — a graph traversal), `validate` (header checks, duplicate IDs, cycle detection), and `archive` (DAG-safe archival). Everything else is a one-liner.

### Forge compatibility

The system is forge-optional, not forge-hostile:

- **Big tickets** use the forge for coordination (`Coordination: gh#N`). The forge issue is real — assignee, comments, external visibility.
- **Small tickets** are local-only. No forge noise.
- **PRs still go through the forge.** Code review is unchanged.
- **Forge CLI available but not required.** Agents without `gh` work on `local` tickets. Offline-first by default.
- **Prefix convention:** `gh#N` (GitHub), `gl#N` (GitLab), `gt#N` (Gitea/Forgejo).

### Cleanup

Closed tickets stay in `tickets/` by default — they're small, greppable, and occasionally referenced by `Blocked-by`. But if the directory grows noisy, run an on-demand archive:

```bash
# Archive closed tickets older than 90 days (dry run)
python tickets/tools/archive_tickets.py tickets/ --days 90

# Execute the archive
python tickets/tools/archive_tickets.py tickets/ --days 90 --execute

# Custom threshold
python tickets/tools/archive_tickets.py tickets/ --days 180 --execute
```

Projects typically wrap these in their build system (Make, Just, npm, etc.) for convenience.

The procedure:
1. Collect candidates: tickets where `Status: closed` and last log entry is older than the threshold.
2. Preserve the DAG: remove from candidates any ticket whose ID appears in a `Blocked-by`, `X-Discovered-from`, or `X-Supersedes` header of a non-archived ticket. These are still part of the live dependency graph.
3. Move survivors to `tickets/archive/`. Git records the move — `git log --follow` still works.
4. Commit the move in a single commit: `archive N closed tickets (>{DAYS} days, DAG-safe)`.

**Recovery:** `git mv tickets/archive/foo.ticket tickets/` to restore any ticket.

This is never automatic. The author runs it when `ls tickets/*.ticket | wc -l` feels too long.

### CI/CD integration

**Ticket validation in CI:** wire `python tickets/tools/validate_tickets.py tickets/` into whatever check target your build system provides. It verifies required headers, unique IDs, valid `Blocked-by` references, and filename/ID consistency. Non-zero exit blocks the build.

**Pre-commit guard:** the pre-commit hook calls `validate_tickets.py` on staged `.ticket` files. Duplicate IDs and malformed headers are caught before they enter history.

**Build system exclusion:** `.ticket` files are not source code or manuscript content. Exclude `tickets/` from doc generators, bundlers, or linters that scan by extension. (Projects using Quarto's explicit render list need no exclusion.)

**Shallow clones:** ticket files are regular tracked files. They survive `--depth 1` clones, which means CI runners and ephemeral containers see the full backlog without special configuration.

## Backwards Compatibility

No migration required. The two systems coexist permanently (see [Design philosophy](#design-philosophy)). Rollback is equally trivial: `tickets/` can be deleted or gitignored with no side effects on the rest of the repository.

The agent workflow harness (described in `AGENTS.md`) defines runbooks for ticket lifecycle events: `new-ticket`, `start-ticket`, `review-pr`, `celebrate`. These become the workflow engine. The ticket files become the data layer.

## Security Considerations

Local ticket files contain no secrets — they are plain text metadata committed to the repository. The pre-commit hook already rejects files matching secret patterns (`.env`, `credentials`, `*.pem`, `*.key`).

Forge-coordinated tickets (`Coordination: gh#N`) use the existing forge authentication. No new credentials, tokens, or attack surface are introduced.

The `Assigned-to` header is informational — it does not grant permissions. Authorization remains with the forge (for forge tickets) or with git branch protection (for local tickets).

**Identity is advisory, not authenticated.** The `Author` header and log-line attribution (e.g., `agent-x status doing`) are free-form strings. Nothing prevents one agent from writing `Author: agent-y`. For accountability, rely on `git log` attribution (signed commits, SSH keys) rather than in-file identity fields. At the current trust level (single author, trusted agents), this is a non-issue.

**Archive on the right branch is the operator's responsibility.** `archive_tickets.py --execute` commits on whatever branch is checked out. The spec says "the author runs it" — this is a human-facing operation, not an automated one. Running it from a feature worktree would place the archive commit on the wrong branch. The tool does not enforce a branch guard; the operator must be on `main`.

## Reference Implementation

The implementation lives in the project's harness layer:

- **Runbooks** (`runbooks/new-ticket.md`, `runbooks/start-ticket.md`): agent instructions for creating and working tickets.
- **Validation** (`tickets/tools/validate_tickets.py`): header checks, ID uniqueness, `Blocked-by` reference integrity. Wire into your CI check target and the pre-commit hook.
- **Ready query** (`tickets/tools/ready_tickets.py`): graph traversal to find unblocked open tickets.
- **Archive** (`tickets/tools/archive_tickets.py`): DAG-safe archival of old closed tickets.

Tools live in `tickets/tools/` so the core ticket system (`tickets/` + `tickets/tools/`) is portable to other repos. Scripts are Python stdlib only — no external libraries, no `pip install`. The total is ~525 lines across four files (`ticket_parser.py`, `validate_tickets.py`, `ready_tickets.py`, `archive_tickets.py`) using only `pathlib`, `re`, `json`, `datetime`, and `subprocess`. Any language with file I/O and regex can reimplement the full set. Skills are shell commands, so the implementation language swaps transparently.

**Adopting in another repo:** copy `tickets/tools/` and add three integration points: (1) task runner targets wrapping each script (Make, Just, npm, etc. — your choice), (2) pre-commit hook calling `validate_tickets.py` on staged `.ticket` files, (3) agent instructions referencing the ticket lifecycle. The Python tools are self-contained; the integration layer is project-specific.

## Rejected Ideas

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

**Bugs Everywhere** — GPLv2, unmaintained since ~2012, Python 2 heritage. No agent features, no active development. Excluded at the table-scan stage.

**TrackDown** — Java/Gradle dependency, no JSON output, no agent features. Wrong ecosystem entirely.

**Why not tk?** tk is the closest match — single bash script, dependency graph, `tk ready`. We adopt its approach (adapt, not adopt): custom skills let us implement exactly the subset we need without inheriting tk's unknown future direction or bash portability concerns. The ideas travel; the dependency doesn't.

#### Git-object (git-bug, git-appraise)

**Pros:** clean working directory, excellent merge semantics (operation-based), forge bridges, JSON output, mature.

**Cons:** worktree problem (`refs/bugs/` behavior with `git worktree` is undertested — risk of corruption), no agent features (`claim`, `ready`, dependency graph), GPLv3.

**git-appraise** — shares the same worktree uncertainty and adds no agent features. Rejected on the same grounds.

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

### Rejected alternatives

**Subdirectory for closed tickets (`tickets/closed/`).** Moves break `Blocked-by` references — every grep would need two paths. Status is metadata (in the header), not location (in the filesystem). Git treats moves as delete+create, cluttering history. Filtering closed tickets is already a one-liner: `grep -L "^Status: closed" tickets/*.ticket`.
