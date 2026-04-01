# AI Agent Guidelines for Climate Finance History Project

> `CLAUDE.md` contains only `@AGENTS.md` — do not modify it (enforced by pre-commit hook).

## Configuration

| Location | Purpose |
|----------|---------|
| `~/.claude/rules/` | Generic rules (git, workflow, coding, state-roadmap) |
| `~/.claude/skills/` | Generic skills (celebrate, review-pr, memory, etc.) |
| `~/.claude/hooks/` | Generic hooks (on-start identity setup) |
| `.claude/rules/` | Project-specific rules (writing, architecture, oeconomia-style, etc.) |
| `.claude/skills/` | Project-specific skills (submission-branch, submission-readiness, update-publist) |
| `.claude/hooks/` | Project-specific hooks (merge gate review check) |
| `.claude/settings.json` | Project permissions and hooks |
| `hooks/` | Git hooks (pre-commit, pre-push, post-checkout) |

## Imperial Dragon workflow

Every task passes through five phases (five claws). Announce transitions inline: `[Phase → Phase] reason`.

### Imagine
Interactive discussion with the user on an `explore-{topic}` branch. Imagine specs, gather information, brainstorm freely. Ask questions, surface motivations, explore what success looks like.
Generate portfolio of options with their probabilities. Go beyond conventional habits to explore new approaches. Take the high road.
Act as my high-level advisor. Challenge my thinking, question my assumptions, and expose blind spots. Stop defaulting to agreement. If my reasoning is weak, break it down and show me why.

Commits are workspace artifacts unless the conversation produces a small fix. Deliverable: a shared vision, plus one of:

- **Tickets** — non-trivial work gets one ticket per action item (`/new-ticket`).
- **Small fix** — if it fits in one red/green/refactor cycle, do it on the explore branch. TDD still applies.
- **Nothing actionable** — delete the branch at session end.

### Plan
Explore alternatives, design strategies, prototype approaches. Use GitHub Issues as the planning artifact — write tickets with full context (`/new-ticket`). **Specify the first test in the ticket** — the Execute phase enforces TDD. Review tickets for intent over metrics. No production commits yet. Deliverable: a ticket with test spec.

### Execute
Runs in a fresh context — the ticket is the only input. Launch via `/start-ticket`.

Autonomous execution using test-driven development. The inner cycle is:

1. **Red**: write a failing test that defines the expected behavior. Commit.
2. **Green**: write the minimum code to make it pass. Commit.
3. **Refactor**: clean up, then confirm tests still pass. Use `make check-fast` during development. Commit.
4. **PR**: Pass `make check` gate, then push and open a PR.

Use `make check-fast` during development, `make check` before opening a PR.

### Verify
Review each PR before merging:

1. **Review**: `/review-pr` or `/review-pr-prose`.
2. **Fix**: Fix all issues. Nits: fix them. Code smells: ultrathink architectural improvements.
3. **Iterate**: Up to three review/fix cycles.

### Celebrate (autonomous)
Runs via `/celebrate`. Celebrating is not a formality — it closes the energy cycle. Reflect on what was accomplished and learned, consolidate memory, dream forward.

### Phase state

The agent must always know and declare its current phase.

- **At conversation start**: workflow rule infers the initial phase and announces it (e.g., `[→ Imagine]`).
- **At each transition**: announce explicitly with `[Phase → Phase] reason`.
- **No implicit transitions**: if no announcement was made, the phase hasn't changed.

## Skills (slash commands)

| Skill | When | Purpose |
|-------|------|---------|
| `/start-ticket N` | Starting work on a GitHub issue | Create worktree, write first test, transition to Execute |
| `/celebrate` | After completing a ticket | Reflect, update STATE/ROADMAP, clean up |
| `/end-session` | User ends a work session | Push branches, run tests, refresh STATE |
| `/new-ticket` | Creating a GitHub issue | Write handoff document with test spec |
| `/review-pr N` | Reviewing a pull request (code) | Multi-perspective agent review |
| `/review-pr-prose N` | Reviewing a pull request (prose) | Simulated peer review panel |
| `/memory` | Writing or sweeping persistent memory | Enforce caps, TTLs, staleness |
| `/autonomous` | Unsupervised autonomous session | Imperial Dragon cycles with 60/40 balance |
| `/submission-branch` | Creating a submission branch | Sprout, freeze, revision lifecycle |
| `/submission-readiness` | Pre-submission gate | Checklist before sprouting |
| `/update-publist` | Adding/updating a publication | Edit Ha-Duong.bib, deposit on HAL via SWORD |

## Autonomous workflow

When issue exploration leads to multiple action items, open one ticket for each under a tracking ticket. Then work in waves, learning from each.

### Wave cycle

1. **Select** — pick ripe tickets (dependencies met, blockers cleared).
2. **Launch** — each ticket in its own worktree, independent tickets in parallel.
3. **Verify** — review each PR in a fresh-context worktree (`/review-pr`).
4. **Learn** — for each result:
   - **Success**: `/celebrate`, save what worked as feedback memory.
   - **Failure**: diagnose root cause, save lesson, re-ticket with diagnosis.
5. **Adapt** — read feedback memories before planning the next wave.
6. **Clean up** — worktrees, branches, stale PRs. Then start the next wave.

## Conversation scope

**Imagine conversations**: may produce zero or many tickets, or inline small fixes. The explore branch is the workspace; the tickets (or PR) are the deliverables.

**Execute conversations**: one ticket per conversation. Transition to Celebrate when the PR is merged and ticket closed. If investigation reveals sub-issues, open them as new tickets — don't scope-creep.
