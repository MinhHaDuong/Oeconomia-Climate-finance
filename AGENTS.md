# AI Agent Guidelines for Climate Finance History Project

> `CLAUDE.md` contains only `@AGENTS.md` — do not modify it (enforced by pre-commit hook).

## Information sources

| File | Purpose | When to consult |
|------|---------|-----------------|
| `README.md` | Project vision, repo structure, build commands | Onboarding, orientation |
| `ROADMAP.md` | Milestones, deliverables, what's done | Starting work, picking tasks |
| `STATE.md` | Current decisions, blockers, stats | Before any task (snapshot of now) |
| `docs/writing-guidelines.md` | Prose style, language polish, citations | Editing manuscript text |
| `docs/coding-guidelines.md` | Pipeline, scripts, conventions | Writing or running code |
| `docs/oeconomia-style.md` | Journal house style | Final formatting |
| `.env` | Project secrets + machine paths (gitignored) | Script execution, agent identity |
| `content/technical-report.qmd` | Full data pipeline documentation | Understanding methodology |
| `runbooks/` | Procedures fired by workflow triggers (see Triggers below) | Automated steps |

## Dragon Dreaming workflow

Every task passes through four phases. Announce transitions inline: `[Phase → Phase] reason`.

### Dreaming
Interactive discussion with the user. No code, no commits. Deliverable: a shared vision.
Imagine specs, gather information, brainstorm freely. Ask questions, surface motivations, explore what success looks like.
Generate portfolio of options with their probabilities. Go beyond conventional habits to explore new approaches. Take the high road.
Act as my high-level advisor. Challenge my thinking, question my assumptions, and expose blind spots. Stop defaulting to agreement. If my reasoning is weak, break it down and show me why.
 
### Planning
Explore alternatives, design strategies, prototype approaches. Read code, research, draft plans. Use GitHub Issues as the planning artifact — write tickets with full context (see below). **Specify the first test in the ticket** — the Doing phase enforces TDD. No production commits yet. Deliverable: a ticket with test spec.

### Doing
Runs in a fresh context — the ticket is the only input. This prevents context window pollution from Dreaming/Planning conversations. Launch via `start-ticket` trigger.

Autonomous execution using test-driven development. See `docs/coding-guidelines.md` and `docs/writing-guidelines.md` for domain-specific test conventions. The inner cycle is:

1. **Red**: write a failing test that defines the expected behavior.
2. **Green**: write the minimum code to make it pass.
3. **Refactor**: clean up, then confirm tests still pass.
4. **PR**: push branch, open PR (include context, it is a handoff point).
5. **Review**: See `runbooks/review-pr.md`.
6. **Iterate**: if review finds issues, fix them all then re-review. Also fix nits, create no debt. Spin an agent to explore seemingly unrelated issues and decide between fix now or open ticket.

Each Red/Green/Refactor step gets its own commit. Stay on the branch, protect main. Use `make check-fast` during development, `make check` before opening a PR.

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
| on-start | Beginning of every conversation | `runbooks/on-start.md` |
| start-ticket | Starting work on a GitHub issue | `runbooks/start-ticket.md` |
| pre-commit | Before every commit | `runbooks/pre-commit.md` |
| post-task | After completing a ticket | `runbooks/celebrate.md` |
| end-session | User ends a work session | `runbooks/celebrate-day.md` |
| new-ticket | Creating a GitHub issue (issues are handoff documents) | `runbooks/new-ticket.md` |
| review-pr | Reviewing a pull request (code) | `runbooks/review-pr.md` |
| review-pr-prose | Reviewing a pull request (prose/manuscript) | `runbooks/review-pr-prose.md` |
| memory-write | Writing or sweeping persistent memory | `runbooks/memory.md` |
| overnight | Unsupervised overnight session (via end-session) | `runbooks/overnight-exploration.md` |

## Git discipline

- **Always work on a branch.** Branch naming: `t/{id}-{slug}` (e.g., `t/afg-auth-flow-gates`). The ID and slug come from the ticket's semantic slug naming (see spec).
- **Enforced by pre-commit hook**: no commits on `main`, `CLAUDE.md` locked, no secrets, no large files (>500KB), no conflict markers.
- **Post-checkout hook**: symlinks `.env` from main worktree into new worktrees (scripts need it for data paths).
- **Git hooks** live in `hooks/`. After cloning: `make setup`. Agents: set automatically by `on-start` trigger.
- **Agent identity**: set at conversation start by the `on-start` trigger. The machine user is `HDMX-coding-agent` (GitHub account). Credentials (`AGENT_GH_TOKEN`, `AGENT_GIT_NAME`, `AGENT_GIT_EMAIL`) are project-specific secrets, deployed per-machine in `.env` (gitignored).
- **One change per commit.** Message explains *why this change and not another*: alternatives considered, local design choices made.
- **Merge commits** (`git merge --no-ff -m`): tactical-level detail — architecture decisions, cross-file impacts, residual debt. Readable via `git log --merges`.
- **Git is the project's long-term memory.** Top-level files reflect *now* — history lives in `git log`. In doubt, check older versions.
- **Use worktrees** for feature branches — work in isolated copies via `git worktree`, not `git stash`/`git checkout`.
- **Create PRs** for each ticket so the author can review changes before merging.

## Autonomous workflow

When issue exploration leads to multiple action items, open one ticket for each. Then work in waves, learning from each.

### Wave cycle

1. **Select** — pick ripe tickets (dependencies met, blockers cleared).
2. **Launch** — each ticket in its own worktree, independent tickets in parallel.
3. **Verify** — review each PR in a fresh-context worktree (`runbooks/review-pr.md`).
4. **Learn** — for each result:
   - **Success**: celebrate (`runbooks/celebrate.md`), save what worked as feedback memory.
   - **Failure**: diagnose root cause, save lesson as feedback memory, re-ticket with the diagnosis.
5. **Adapt** — read feedback memories before planning the next wave. Adjust approach based on what failed and what worked.
6. **Clean up** — worktrees, branches, stale PRs. Then start the next wave.

The wave ends with a global verification pass across all changes merged in this wave. If integration breaks, that's a new ticket for the next wave — not a reason to revert silently.

## When to ask the author
- You're stuck after three different approaches (including expert fan-out).
- The task requires a judgment call outside your domain docs.
- See `docs/writing-guidelines.md` for manuscript-specific guidance.

## Conversation scope
One ticket per conversation. The agent stops when the ticket's exit criteria are met. If investigation reveals sub-issues, open them as new tickets for future conversations — don't scope-creep the current one.
