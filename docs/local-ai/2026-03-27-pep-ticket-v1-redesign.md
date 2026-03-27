Gh-issue: #435
Title: %ticket v1 — agent-friendly redesign of the local ticket system
Author: minh, claude
Status: draft
Type: design
Created: 2026-03-27
Supersedes: docs/issue-237-comment-landscape.md (PR #385)
Post-History: 2026-03-27 (dreaming session — plugin architecture, format redesign)

# %ticket v1 — agent-friendly redesign

## Abstract

PR #385 built a local ticket system with three parallel implementations
(Python, bash, Go) and a flexible format (open `X-` headers, mnemonic IDs).
This PEP redesigns the system around a single principle: **the agent reads
the spec and operates on files directly — CLI tools are guardrails, not the
interface.** The result is a smaller, stricter format that ships as a Claude
Code plugin (rules + skills + validator).

## Motivation

PR #385's design was tool-centric: the agent calls Python scripts to create,
query, and archive tickets. This worked but inverted the natural relationship.
LLMs don't need CLI tools to read and write plain text — they do it natively.
The tools were doing work the agent already knows how to do, while the format
was too flexible for agents to handle reliably without the tools.

The forcing function for redesign: packaging the ticket system as a reusable
plugin for other repos (#391, harness extraction). A plugin must be
self-contained, zero-dependency, and adoptable by any AI agent — not just
Claude Code with Python installed.

## Design changes from PR #385

### 1. Magic first line (`%ticket v1`)

**PR #385:** no version marker. Format defined implicitly by tool behavior.

**v1:** every file starts with `%ticket v1`. Enables file-type detection
without relying on the `.ticket` extension, and provides a schema migration
path. A v2 validator rejects v1 files rather than silently misparsing them.

**Rationale:** agents need to know what they're looking at. A version marker
is the simplest possible self-description. Inspired by shebangs, PEP markers,
and YAML document separators.

**Alternatives considered:**
- YAML frontmatter (`---`). Rejected: introduces YAML parsing ambiguity.
- Comment-based (`# ticket v1`). Rejected: RFC 822 has no comment syntax.
- No marker (status quo). Rejected: makes version migration impossible.

### 2. Closed header set, no `X-` extensions

**PR #385:** open header set. Standard headers (`Id`, `Title`, `Status`, etc.)
plus arbitrary `X-` extensions (`X-Phase`, `X-Discovered-from`, `X-Supersedes`,
`X-Parent`, `X-Review-round`, `X-Comment-number`, `X-Section`, `X-Page`).

**v1:** exactly 5 headers. `Title`, `Status`, `Created`, `Author`, `Blocked-by`.
No `X-` extensions. New headers require a version bump (`%ticket v2`).

**Rationale:** agents work best with rigid schemas where there is exactly one
right way to do something. An open header set invites creative variations that
break cross-agent interop. The `X-` convention worked for email (millions of
implementors, decades of evolution) but is wrong for a format consumed by LLMs
that hallucinate plausible-but-invalid headers.

**What was lost:**
- `X-Phase` (Dragon Dreaming). Moved to the body or log. Phase is workflow
  metadata, not ticket metadata — it belongs in the agent's instructions,
  not the file format.
- `X-Discovered-from`, `X-Supersedes`, `X-Parent`. Provenance edges.
  These were useful for DAG-safe archival (archive script checked them).
  In v1, archival only respects `Blocked-by` edges. If provenance tracking
  proves necessary, promote these to first-class headers in v2.
- `X-Review-round`, `X-Comment-number`, `X-Section`, `X-Page`. Peer review
  metadata. These belonged to a specific workflow (manuscript review) and
  were over-fitted to one project. Not general enough for a plugin.
- `Coordination`, `Assigned-to`, `Forge-issue`. Forge integration headers.
  Dropped because the ticket system no longer caches GitHub Issues (see
  decision #6 below). `Blocked-by: gh#N` is the only forge reference.

**Alternatives considered:**
- Keep `X-` but make the validator warn on unknown ones. Rejected: warnings
  that agents ignore are useless. Either enforce or don't have the rule.
- Allow a project-specific extension file listing valid extra headers.
  Rejected: adds a configuration layer. Version bumps are simpler.

### 3. Sequential numeric IDs instead of mnemonics

**PR #385:** mnemonic IDs derived from slug initials. `auth-flow-gates` -> `afg`,
`validate-tickets` -> `vt`. Collisions handled with numeric suffixes: `afg2`.

**v1:** sequential 4-digit zero-padded numbers. `0001`, `0002`, `0003`.
ID is the filename prefix, not a header field.

**Rationale:** mnemonic IDs require creativity — the agent must invent a
unique, meaningful abbreviation. This is exactly the kind of task where
agents make mistakes (collision, poor mnemonics, inconsistent derivation
rules). Sequential numbers are mechanical: read the highest existing number,
add 1. Zero creative effort, zero ambiguity.

**Tradeoff:** mnemonics are human-memorable (`vt` = validate tickets).
Numbers are not (`0017` = ???). But the `Title` header and filename slug
provide readability: `0017-validate-tickets.ticket` is just as scannable
as `vt-validate-tickets.ticket`.

**On collision:** sequential IDs collide the same way mnemonics do — two
worktrees creating tickets simultaneously pick the same number. The
collision rate is identical. The fix is also identical: the pre-commit
validator catches duplicates, the losing agent renames. We chose not to
solve this differently because (a) the collision rate is low at
single-machine scale, and (b) any atomic solution (lock files, CAS)
adds complexity disproportionate to the problem.

**No `Id:` header:** the ID is the filename prefix. This eliminates the
redundancy between `Id: vt` and filename `vt-validate-tickets.ticket`
that PR #385 had to validate (rule: "Id must match filename prefix").
One source of truth, not two.

**Alternatives considered:**
- UUIDs. Rejected: unreadable, impossible to type or reference in conversation.
- Worktree-scoped prefixes (`A-001`, `B-001`). Rejected: ugly, requires
  lane assignment, adds configuration.
- Random short codes (like git's abbreviated hashes). Rejected: still
  collision-prone, not human-meaningful.

### 4. Closed verb set in log section

**PR #385:** free-form log entries. No formal grammar.

**v1:** 5 verbs: `created`, `status`, `claimed`, `released`, `note`.
Each log line is `{timestamp} {actor} {verb} [{detail}]`.

**Rationale:** the log is the ticket's audit trail. If the format is
free-form, agents write inconsistent entries that tools can't parse.
A closed verb set means the validator can check log entries, and
querying the log programmatically is reliable. The `note` verb provides
an escape hatch for anything that doesn't fit the other four.

**Alternatives considered:**
- CRDT operation set (as discussed in PR #385's `con` ticket). Rejected:
  disproportionate complexity for the scale. CRDTs solve concurrent
  distributed writes — local tickets don't have that problem.
- No validation of log lines. Rejected: if we don't validate, agents
  will produce inconsistent formats that break cross-agent interop.

### 5. `pending` status restored

**PR #385:** 4 statuses: `open`, `doing`, `closed`, `pending`.

**v1 draft (initial):** 3 statuses, `pending` dropped.

**v1 (revised):** 4 statuses, `pending` restored.

**Rationale for restoration:** a ticket awaiting external input (reviewer
feedback, human decision) is neither open nor doing. Without `pending`,
agents would either (a) leave it `open` and risk picking it up, or (b)
mark it `doing` which blocks the agent from other work. `pending` is
excluded from the ready query, which is the correct behavior.

### 6. No GitHub Issue cache

**PR #385:** `Coordination: gh#42` and `Forge-issue: gh#42` headers linked
local tickets to forge issues. The relationship was a loose cross-reference.

**Explored and rejected:** making local tickets a read cache of GitHub Issues.
Sync at session start, work offline, push changes back.

**v1:** local tickets and GitHub Issues are fully independent systems.
The only bridge is `Blocked-by: gh#N`, a one-way reference that the
ready query resolves on demand (API call when online, treat as satisfied
when offline).

**Rationale explored in dreaming session (pros/cons):**

Cache pros:
- One query surface for all work (`/ticket-ready` covers both local and upstream).
- Offline reads of upstream state after initial sync.
- Cross-system dependency graph visible locally.

Cache cons:
- **Staleness is the exact failure mode being prevented.** The system exists
  to stop friendly fire. A stale cache causes friendly fire.
- Sync complexity grows with every GitHub field someone wants locally.
- Two sources of truth with a "GitHub wins" rule means the agent must
  distrust its own files.
- Committed cache pollutes git history. Gitignored cache is invisible to
  other worktrees (defeats the purpose).

**Resolution:** `Blocked-by: gh#N` gives the one useful thing from caching
(cross-system dependencies) without the sync machinery. The forge prefix
(`gh#`) disambiguates from local 4-digit IDs.

### 7. Plugin architecture: rules + skills + validator

**PR #385:** 3 implementations (Python ~525 LOC, bash ~766 LOC, Go ~785 LOC).
The tools were the interface — agents called `python tickets/tools/validate_tickets.py`.

**v1:** the rules file is the interface. The agent reads `.claude/rules/tickets.md`
and operates on `.ticket` files directly using Read/Edit tools. The Go binary
is a pre-commit validator (safety net). Python and bash implementations dropped.

**Plugin ships as:**
```
.claude/rules/tickets.md        # format spec (agent reads this)
.claude/skills/ticket-new/      # create a ticket
.claude/skills/ticket-claim/    # claim for work
.claude/skills/ticket-close/    # mark done
.claude/skills/ticket-ready/    # list unblocked tickets
.claude/skills/ticket-archive/  # move old closed tickets
hooks/ticket-validate           # Go binary, pre-commit
tickets/                        # the pool
tickets/archive/                # old closed tickets
```

**Rationale:** agents don't need CLI tools to read and write plain text.
The 1,500+ lines of Python/bash/Go in PR #385 existed to do what the agent
already does natively. The rules file (~150 lines of markdown) replaces all
of it as the agent's primary reference. The Go binary catches the rare
mistake — it's a linter, not the interface.

**Why Go for the validator:** zero dependencies, fast, ships as a single
binary. No Python runtime, no Node.js, no installation step. Projects
without Go can skip the binary and rely on agent discipline alone.

**Agent portability:** any LLM that reads markdown can work tickets.
The skills are Claude Code-specific (`.claude/skills/`), but the format
and rules file work with Cursor, Aider, Copilot, or a human with `$EDITOR`.
Other agent frameworks map skills to their own invocation mechanism.

### 8. Cross-worktree coordination via `.git/ticket-wip/`

**Unchanged from PR #385.** The `.git/ticket-wip/` mechanism exploits
`git-common-dir` — all worktrees share the same `.git/` directory.

**Explored and rejected:** claims as log lines in the ticket file.
This would require a commit-push-pull cycle for every claim — too heavy
for a coordination primitive. `.wip` files are instant, local-only,
and visible across worktrees without any git operation.

**Explored and rejected:** branch-as-claim (creating a `tNNNN-*` branch
is the claim). This works but requires `git ls-remote` or `git branch -a`
to check — heavier than reading a local file. Also conflates "I'm working
on this" with "I have code for this."

**Multi-machine coordination is a non-goal.** The `.wip` mechanism is
local-only. Across machines, use GitHub Issues (assignees, labels).
The plugin serves single-machine, multi-worktree coordination.

## Backwards compatibility

PR #385 was never merged. No backwards compatibility concerns.

Projects adopting v1 create a `tickets/` directory and drop in the plugin
files. Removal is equally trivial: delete `tickets/` and the plugin files.

## Security considerations

Unchanged from PR #385. Local tickets contain no secrets. Forge references
(`gh#N`) use existing authentication. Identity in ticket files is advisory —
rely on `git log` attribution for accountability.

## Open questions

1. **Should `Labels` be a v1 header?** Dropped in this revision because its
   purpose was underspecified. If projects need categorization, it could
   return in v2, or projects use the body for ad-hoc tagging.

2. **Provenance headers.** PR #385's `X-Discovered-from` and `X-Supersedes`
   were useful for DAG-safe archival. Worth promoting to v1, or wait for v2?

3. **Validator distribution.** Ship as source (Go file in `tickets/tools/`),
   pre-built binary, or `go install` URL? Source is most portable but
   requires a Go toolchain to build.
