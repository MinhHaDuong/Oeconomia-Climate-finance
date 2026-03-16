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

Every task passes through four phases. Identify and report the phase you're in on startup.

### Dreaming
Interactive discussion with the user. Imagine specs, gather information, brainstorm freely. No code, no commits. Ask questions, surface motivations, explore what success looks like.

### Planning
Explore alternatives, design strategies, prototype approaches. Read code, research, draft plans. Use GitHub Issues as the planning artifact — write tickets with full context (see below). **Specify the first test in the ticket** — the Doing phase enforces TDD. No production commits yet.

### Doing
Autonomous execution using test-driven development. The cycle is:

1. **Red**: write a failing test that defines the expected behavior.
2. **Green**: write the minimum code to make it pass.
3. **Refactor**: clean up, then confirm tests still pass.

Each step gets its own commit (the git log tells the story: intent → solution → polish). Stay on the branch, protect main. Use `make check-fast` during development, `make check` before opening a PR. See `docs/coding-guidelines.md` and `docs/writing-guidelines.md` for test details per domain.

If a test stays red after three approaches:
1. Launch parallel expert agents exploring different directions.
2. If all experts fail: is the test correct? (Maybe the spec is wrong — re-ticket with diagnosis.)
3. If the spec is sound but no approach works: ask the author.

### Celebrating (autonomous)
The `post-task` trigger runs automatically. Celebrating is not a formality — it closes the energy cycle. The agent reflects on what was accomplished and learned, acknowledges contributions, and releases the context before the next dream begins.

## Triggers

| Event | When | Runbook |
|-------|------|---------|
| on-start | Beginning of every conversation | `runbooks/on-start.md` |
| start-ticket | Starting work on a GitHub issue | `runbooks/start-ticket.md` |
| pre-commit | Before every commit | `runbooks/pre-commit.md` |
| post-task | After completing a ticket | `runbooks/celebrate.md` |
| new-ticket | Creating a GitHub issue (issues are handoff documents) | `runbooks/new-ticket.md` |
| review-pr | Reviewing a pull request | `runbooks/review-pr.md` |
| memory-write | Writing or sweeping persistent memory | `runbooks/memory.md` |

## Git discipline

- **Always work on a branch.** Branch naming: `t{N}-short-description`.
- **Enforced by pre-commit hook**: no commits on `main`, `CLAUDE.md` locked, no secrets, no large files (>500KB), no conflict markers.
- **Post-checkout hook**: symlinks `.env` from main worktree into new worktrees (scripts need it for data paths).
- **Git hooks** live in `hooks/`. After cloning: `git config core.hooksPath hooks`.
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
