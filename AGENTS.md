# AI Agent Guidelines for Climate Finance History Project

> `CLAUDE.md` contains only `@AGENTS.md` — do not modify it (enforced by pre-commit hook).

## Information sources

| File | Purpose | When to consult |
|------|---------|-----------------|
| `README.md` | Project vision, repo structure, build commands | Onboarding, orientation |
| `ROADMAP.md` | Milestones, deliverables, what's done | Starting work, picking tasks |
| `STATE.md` | Current decisions, blockers, stats | Before any task (snapshot of now) |
| `.agent/guidelines/writing-guidelines.md` | Prose style, language polish, citations | Editing manuscript text |
| `.agent/guidelines/coding-guidelines.md` | Pipeline, scripts, conventions | Writing or running code |
| `.agent/guidelines/oeconomia-style.md` | Journal house style | Final formatting |
| `.env` | Project secrets + machine paths (gitignored) | Script execution, agent identity |
| `content/technical-report.qmd` | Full data pipeline documentation | Understanding methodology |
| `.agent/runbooks/` | Procedures fired by workflow triggers (see Triggers below) | Automated steps |

## Dragon Dreaming workflow

Every task passes through four phases. Announce transitions inline: `[Phase → Phase] reason`.

### Dreaming
Interactive discussion with the user on an `explore-{topic}` branch. Imagine specs, gather information, brainstorm freely. Ask questions, surface motivations, explore what success looks like.
Generate portfolio of options with their probabilities. Go beyond conventional habits to explore new approaches. Take the high road.
Act as my high-level advisor. Challenge my thinking, question my assumptions, and expose blind spots. Stop defaulting to agreement. If my reasoning is weak, break it down and show me why.

Commits are workspace artifacts (notes, analysis, braindumps) unless the conversation produces a small fix (see below). Deliverable: a shared vision, plus one of:

- **Tickets** — non-trivial work gets one ticket per action item, for future Doing conversations.
- **Small fix** — if the fix fits in one red/green/refactor cycle and doesn't need a fresh context, do it on the explore branch. TDD still applies. Rationale goes in the commit message (why this change) and the PR description (the Dreaming context that led to it). If during the fix you realize it's bigger than expected, stop — open a ticket, start fresh.
- **Nothing actionable** — delete the branch at session end.

### Planning
Explore alternatives, design strategies, prototype approaches. Read code, research, draft plans. Use GitHub Issues as the planning artifact — write tickets with full context (see below). **Specify the first test in the ticket** — the Doing phase enforces TDD. No production commits yet. Deliverable: a ticket with test spec.

### Doing
Runs in a fresh context — the ticket is the only input. This prevents context window pollution from Dreaming/Planning conversations. Launch via `start-ticket` trigger.

Autonomous execution using test-driven development. See `.agent/guidelines/coding-guidelines.md` and `.agent/guidelines/writing-guidelines.md` for domain-specific test conventions. The inner cycle is:

1. **Red**: write a failing test that defines the expected behavior. Commit.
2. **Green**: write the minimum code to make it pass. Commit.
3. **Refactor**: clean up, then confirm tests still pass. Use `make check-fast` during development. Commit.
4. **PR**: Pass `make check` gate, then submit the work by pushing the branch and opening a PR with detailed context.
5. **Review**: See `.agent/runbooks/review-pr.md`.
6. **Fix**: Fix all issues and comments. Nits: fix them. Leave no debt. Seemingly unrelated issues: Spin an agent to explore and decide between fixing now or opening a ticket. Code smells: ultrathink architectural improvements, not code shaving.
6. **Iterate**: As necessary for top quality, up to three review/fix cycle.

 Use `make check-fast` during development, `make check` before opening a PR.

When stuck, escalate progressively:
1. Fix direct — review feedback is straightforward.
2. Alternative approach — rethink the solution.
3. Parallel expert agents — fan-out different directions.
4. Re-ticket with diagnosis — the problem is mis-specified.
5. Stop — ask the author.

Save a feedback memory at each escalation (what failed, why). Stop if repeating yourself. Deliverable: a merged PR.

### Celebrating (autonomous)
The `post-task` trigger runs automatically. Celebrating is not a formality — it closes the energy cycle. The agent reflects on what was accomplished and learned, acknowledges contributions, and releases the context before the next dream begins.

### Phase state

The agent must always know and declare its current DD phase.

- **At conversation start**: `on-start.md` infers the initial phase from context and announces it (e.g., `[→ Dreaming]`).
- **At each transition**: announce explicitly with `[Phase → Phase] reason` before proceeding. Runbooks include these markers at the appropriate steps.
- **No implicit transitions**: if no announcement was made, the phase hasn't changed. When in doubt, state the current phase.

## Triggers

| Event | When | Runbook |
|-------|------|---------|
| on-start | Beginning of every conversation | `.agent/runbooks/on-start.md` |
| start-ticket | Starting work on a GitHub issue | `.agent/runbooks/start-ticket.md` |
| pre-commit | Before every commit | `.agent/runbooks/pre-commit.md` |
| post-task | After completing a ticket | `.agent/runbooks/celebrate.md` |
| end-session | User ends a work session | `.agent/runbooks/celebrate-day.md` |
| new-ticket | Creating a GitHub issue (issues are handoff documents) | `.agent/runbooks/new-ticket.md` |
| review-pr | Reviewing a pull request (code) | `.agent/runbooks/review-pr.md` |
| review-pr-prose | Reviewing a pull request (prose/manuscript) | `.agent/runbooks/review-pr-prose.md` |
| memory-write | Writing or sweeping persistent memory | `.agent/runbooks/memory.md` |
| autonomous | Unsupervised autonomous session (via end-session) | `.agent/runbooks/autonomous-session.md` |
| hotfix | Quick fix via `/hotfix` skill | `.claude/skills/hotfix.md` |

## Git discipline

- **Always work on a branch.** Branch naming: `t{N}-short-description` (Doing), `explore-{topic}` (Dreaming), `hotfix-{slug}` (quick fixes via `/hotfix` skill), or `submission/{journal}-{document}` (long-lived submission tracking, see `.agent/runbooks/submission-branch.md`). Main is read-only except for STATE housekeeping (see `.agent/runbooks/celebrate-day.md` step 7). Submission branches are protected: no merges (cherry-pick only), no deletion, no force-push.
- **Enforced by pre-commit hook**: no commits on `main`, `CLAUDE.md` locked, no secrets, no large files (>500KB), no conflict markers.
- **Post-checkout hook**: symlinks `.env` from main worktree into new worktrees (scripts need it for data paths).
- **Git hooks** live in `hooks/`. After cloning: `make setup`. Agents: set automatically by `on-start` trigger.
- **Agent identity**: set at conversation start by the `on-start` trigger. The machine user is `HDMX-coding-agent` (GitHub account). Credentials (`AGENT_GH_TOKEN`, `AGENT_GIT_NAME`, `AGENT_GIT_EMAIL`) are project-specific secrets, deployed per-machine in `.env` (gitignored).
- **One change per commit.** Message explains *why this change and not another*: alternatives considered, local design choices made.
- **Merge commits**: strategic-level detail — architecture decisions, cross-file impacts, residual debt. Readable via `git log --merges`. Feature merges go through PRs; chores (dvc.lock, housekeeping) merge locally via short-lived branch + fast-forward.
- **Git is the project's long-term memory.** Top-level files reflect *now* — history lives in `git log`. In doubt, check older versions.
- **Use worktrees** for feature branches — work in isolated copies via `git worktree`, not `git stash`/`git checkout`.
- **Create PR** for each ticket to review changes before merging.

## Autonomous workflow

When issue exploration leads to multiple action items, open one ticket for each under a tracking ticket. Then work in waves, learning from each.

### Wave cycle

1. **Select** — pick ripe tickets (dependencies met, blockers cleared).
2. **Launch** — each ticket in its own worktree, independent tickets in parallel.
3. **Verify** — review each PR in a fresh-context worktree (`.agent/runbooks/review-pr.md`).
4. **Learn** — for each result:
   - **Success**: celebrate (`.agent/runbooks/celebrate.md`), save what worked as feedback memory.
   - **Failure**: diagnose root cause, save lesson as feedback memory, re-ticket with the diagnosis.
5. **Adapt** — read feedback memories before planning the next wave. Adjust approach based on what failed and what worked.
6. **Clean up** — worktrees, branches, stale PRs. Then start the next wave.

The wave ends with a global verification pass across all changes merged in this wave. If integration breaks, that's a new ticket for the next wave — not a reason to revert silently.

## When to ask the author
- You're stuck after three different approaches (including expert fan-out).
- The task requires a judgment call outside your domain docs.
- See `.agent/guidelines/writing-guidelines.md` for manuscript-specific guidance.

## Conversation scope

**Dreaming conversations**: may produce zero or many tickets, or inline small fixes. The explore branch is the workspace; the tickets (or PR) are the deliverables.

**Doing conversations**: one ticket per conversation. The agent transition to Celebration when the PR is merged with the ticket closed, exit criteria met. If investigation reveals sub-issues, open them as new tickets for future conversations — don't scope-creep the current one.
