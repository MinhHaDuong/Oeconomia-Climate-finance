# PEP: %ticket v1 — Agent-native local ticket system

**Status:** Draft
**Created:** 2026-03-27
**Author:** claude (with MHD)
**Context:** PR #385 (t237-local-ticket-system), issue #435

## Abstract

A file-based ticket system designed for AI agent coordination across
git worktrees on a single machine. Tickets are plain-text files with a
versioned format (`%ticket v1`), committed to git, and validated by a
pre-commit hook. The system complements (not replaces) GitHub Issues.

## Motivation

When an AI agent works across multiple git worktrees on the same machine,
two failure modes emerge:

1. **Friendly fire**: Agent A in worktree `../t003-auth/` and agent B in
   `../t005-cache/` both pick the same task because neither can see the
   other's uncommitted state.

2. **Network dependency**: Listing open issues requires a GitHub API call.
   In offline, rate-limited, or latency-sensitive contexts, this blocks
   the agent's ability to pick work.

The ticket system solves both: local files for offline reads, a shared
`.git/ticket-wip/` directory for cross-worktree coordination.

## Design choices and rationale

### 1. Magic first line: `%ticket v1`

**Choice:** Every ticket file starts with `%ticket v1`.

**Rationale:** Enables file-type detection without relying on the `.ticket`
extension. Provides a schema version for forward compatibility — a `v2`
that adds headers won't break v1 validators (they reject unknown versions
rather than silently misparsing).

**Alternatives considered:**
- YAML front matter (`---`/`---`): ambiguous, could be confused with log
  separators. YAML parsing is heavy for agents.
- JSON: not human-readable, poor diffability in git.
- No version marker: makes format evolution impossible without breaking
  existing files.

### 2. Closed header set (no X- extensions)

**Choice:** v1 defines exactly 5 headers: Title, Status, Created, Author,
Blocked-by. No `X-` extensions are allowed.

**Rationale:** Agents work best with rigid schemas where there's exactly
one right way to write a file. Open extension headers invite creative
variations that break tooling. If v2 needs new headers (Priority, Labels,
Assignee), it declares `%ticket v2` and extends the closed set.

**Alternatives considered:**
- Open `X-` headers (as in PR #385): caused proliferation of
  `X-Phase`, `X-Discovered-from`, `X-Supersedes`, `X-Parent` — each
  requiring ad-hoc validation rules. The "closed set + version bump"
  approach is cleaner.
- RFC 822 with free extensions: too flexible for agent consumption.

### 3. Sequential numeric IDs (not mnemonics)

**Choice:** 4-digit zero-padded sequential IDs derived from filenames:
`0001-add-auth.ticket`, `0002-fix-cache.ticket`.

**Rationale:** Mechanical assignment — no creativity needed. The agent
runs `ls | sort | tail -1`, increments, and pads. Mnemonics (e.g., `afg`,
`ta`, `vt` from PR #385) require the agent to invent unique abbreviations,
which becomes fragile at scale.

**Collision handling:** Optimistic concurrency. Two worktrees may pick the
same number simultaneously. The pre-commit validator catches duplicates.
The agent that loses renames its ticket (increment again). This matches
git's own optimistic concurrency model.

**Alternatives considered:**
- Mnemonic IDs (PR #385): creative, readable, but collision-prone and
  not mechanically assignable.
- UUIDs: unique but unreadable, poor for human consumption.
- Hash-based IDs: explored in early PR #385 commits, abandoned because
  hashes are opaque and don't sort chronologically.

### 4. ID in filename, not header

**Choice:** The ticket ID is derived from the filename prefix, not from
an `Id:` header.

**Rationale:** Eliminates the consistency check between `Id:` header and
filename (a source of errors in PR #385). Single source of truth. The
filename is the canonical identifier.

**Alternatives considered:**
- `Id:` header (PR #385): required a validation rule to ensure
  header/filename consistency. Redundant information invites divergence.

### 5. Four status values: open, doing, closed, pending

**Choice:** `open` (available), `doing` (claimed), `closed` (done),
`pending` (awaiting external input).

**Rationale:** `pending` was added to exclude tickets awaiting review or
human input from the ready query. Without it, agents would pick up
tickets that can't be worked on. `doing` is explicit claim (vs. the
`.wip` file being the only claim signal).

**Alternatives considered:**
- Three statuses (open/doing/closed): no way to express "waiting for
  review" without a separate mechanism.
- Labels for sub-states: would require validating label values, adding
  complexity to the closed header set.

### 6. Cross-worktree coordination via `.git/ticket-wip/`

**Choice:** Claims use `.wip` files inside `.git/ticket-wip/`, shared
across worktrees via `git-common-dir`.

**Rationale:** Git worktrees on the same machine share the `.git/`
directory. Writing a `.wip` file is instant (no commit, no push, no
merge conflict). The alternative — putting claims in the ticket file
itself — would require a commit-push-pull cycle just to say "I'm working
on this."

**Tradeoffs:**
- `.wip` files are invisible to `git status` (feature: no noise).
- `.wip` files don't survive across clones (acceptable: coordination
  scope is one machine).
- Stale `.wip` files from crashed sessions need manual cleanup or
  session-end hooks.

### 7. GitHub Issues as separate coordination layer

**Choice:** The ticket system does NOT cache GitHub Issues locally. A
ticket may reference a GitHub issue (`Blocked-by: gh#435`) but never
mirrors its state.

**Rationale explored in conversation:**

*Pro cache:*
- Listing open work without network call.
- Local-first development workflow.
- Single query interface for both local and remote tickets.

*Con cache:*
- Sync protocol complexity (pull/push, conflict resolution, staleness).
- GitHub is source of truth — cache introduces eventual consistency bugs.
- Push/pull discipline overhead for every state change.
- Two representations of the same data invites divergence.

**Decision:** No cache. Local tickets are local-only; they never need to
exist on the forge. GitHub Issues remain the inter-agent coordination
layer. The `gh#N` reference in `Blocked-by` is resolved on demand (API
call when online, treated as satisfied when offline).

### 8. Agent-friendly by design

**Choice:** The agent reads `.ticket` files directly using `Read`/`Edit`
tools. The Go binary is a validator in the pre-commit hook, not the
primary interface.

**Rationale:** Agents are better at parsing structured text than at
running CLIs. The rules file (`.claude/rules/tickets.md`) is the complete
specification — an agent that reads only that file can create, query, and
close tickets correctly. The CLI tools exist as guardrails, not interfaces.

**Architecture:**

| Component | Role |
|-----------|------|
| `.claude/rules/tickets.md` | Format spec (agent reads this) |
| `.claude/skills/ticket-*` | Agent verbs (slash commands) |
| `tickets/tools/go/ticket-tools` | Validator binary (pre-commit) |
| `tickets/tools/*.py` | Python fallback + test harness |

### 9. Go binary as single validator

**Choice:** Single Go binary (`ticket-tools`) implements validate, ready,
and archive. No Python/bash/Perl alternatives.

**Rationale:** PR #385 explored Python, bash, Perl, and Go implementations
simultaneously. The Go binary won: zero dependencies, fast, single file,
cross-compilable. The Python tools are kept as a test harness and fallback
but are not the primary path.

**Alternatives explored (PR #385 history):**
- Python first (PR #385 initial): worked but required `PYTHONPATH` setup.
- Bash+awk (commit `5b7dd3a`): 34x slower than pure bash variant.
- Perl (commit `e41f4d3`): 2.5x faster than Python, dropped as niche.
- Rust (commit `32dff03`): overkill for the problem size.

## What changed from PR #385

| PR #385 | v1 plugin |
|---------|-----------|
| 3 implementations (Python, bash, Go) | 1 validator (Go), Python as test fallback |
| Mnemonic IDs (`ta`, `vt`, `rt`) | Sequential numeric IDs (`0001`, `0002`) |
| `Id:` header + filename consistency check | ID from filename only |
| `X-` extension headers | Closed header set, versioned |
| Open header schema | Closed set: 5 headers in v1 |
| Tools as primary interface | Agent reads/writes files; tools are guardrails |
| No magic line | `%ticket v1` |
| 3 statuses | 4 statuses (`pending` added) |

## What was imported from PR #385

- **Go binary structure** (parser, validator, ready, archive) — adapted
  for v1 format rules.
- **Test suite** (validate, ready, archive) — rewritten for v1 fixtures.
- **`.wip` coordination protocol** — unchanged.
- **DAG-safe archive logic** — unchanged (Blocked-by reference protection).

## Specification

See `.claude/rules/tickets.md` for the complete format specification.
That file is authoritative; this PEP documents the rationale.

### 10. Postel's Law: tolerant on read, strict on write

**Choice:** The validator enforces `%ticket v1` strictly on commit. But the
agent — not the tooling — is the parser for arbitrary input.

**Rationale:** An agent may receive ticket-like information in any form:
raw `gh issue view --json` output, a sentence in conversation, a markdown
sketch, a paste from a PR comment. Requiring the agent to first convert
this into `%ticket v1` before it can reason about it would be a barrier.

Instead: the agent reads whatever it finds, understands the intent, and
writes clean `%ticket v1`. The pre-commit hook catches any formatting
mistakes. The tolerance is in the LLM, not the tooling.

This keeps the tooling simple (one format to parse, one format to
validate) while making the system maximally agent-friendly. The strict
format is a *write contract*, not a *read requirement*.

**Implication for skills:** Skill prompts accept any input shape and
normalize to `%ticket v1` on output. The `/ticket-new` skill can take
a JSON blob, a sentence, or a structured template — it produces the
same canonical format.

## Open questions

1. **v2 header candidates**: Labels, Priority, Assignee — add when needed.
2. **Archive retention**: 90 days is arbitrary. Should it be configurable
   per-project?
3. **Cross-machine coordination**: Currently out of scope. If needed,
   the `.wip` protocol could be extended with a network-aware lock.
4. **Log verb enforcement**: The spec lists a closed verb set but the
   validator only checks structural format (rule 10). Enforce in v2?
