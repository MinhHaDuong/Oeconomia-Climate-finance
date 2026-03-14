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
| `.env` | Machine-specific paths: `CLIMATE_FINANCE_DATA`, `CLAUDE_MEMORY_DIR` | Script execution |
| `content/technical-report.qmd` | Full data pipeline documentation | Understanding methodology |

Claude Code auto-loads `$CLAUDE_MEMORY_DIR/MEMORY.md` into every conversation (persistent cross-session memory).

## Dragon Dreaming workflow

Every task passes through four phases. Name the phase you're in.

### Dreaming
Interactive discussion with the user. Imagine specs, gather information, brainstorm freely. No code, no commits. Ask questions, surface motivations, explore what success looks like.

### Planning
Explore alternatives, design strategies, prototype approaches. Read code, research, draft plans. Use GitHub Issues as the planning artifact — write tickets with full context (see below). **Write tests first** (see TDD below). No production commits yet.

### Doing
Autonomous execution. Red → green → refactor. Commit at each step. Stay on the branch, protect main.

## Test-driven development

Write the test before the code. The cycle is:

1. **Red**: write a failing test that defines the expected behavior.
2. **Green**: write the minimum code to make it pass.
3. **Refactor**: clean up, then confirm tests still pass.

Each step gets its own commit (the git log tells the story: intent → solution → polish).

### For scripts (pipeline, analysis, figures)
- Tests live in `tests/`. Run with `uv run pytest`.
- A new script or changed behavior starts with a test in `tests/test_<module>.py`.
- Acceptance tests (e.g., `make corpus-validate`) are the top-level contract — never weaken them without discussion.

### For manuscript (prose, figures, tables)
- Verification commands are the "tests": blacklisted words, em-dash density, word count, `make manuscript` build clean.
- Before editing prose, run the relevant checks. After editing, confirm they still pass.
- `make clean && make all` is the integration test.

### Celebrating
Reflect on lessons learned. Generalize new skills. Update MEMORY.md with durable insights. Clean up: close issues, archive branches, update STATE.md and ROADMAP.md.

## Housekeeping triggers

### Before every commit
- **Stale check**: re-read any project file you modified or relied on. If it contains outdated numbers, stale status, or dead references, fix them in the same commit. The commit is the quality gate — nothing stale gets versioned.

### After completing a ticket (Celebrating phase)
- Update `STATE.md`: refresh stats, remove resolved blockers, adjust priorities.
- Update `ROADMAP.md`: check off completed items, note new ones that emerged.
- Update `content/technical-report.qmd` if the pipeline, data contract, or methodology changed.
- Update MEMORY.md: save durable lessons, prune stale entries.

### At conversation start (time-based)
- Read `STATE.md` and `ROADMAP.md` — if not from today, refresh from current data.

### When to update `content/technical-report.qmd`
- Pipeline phase contract changed (new inputs/outputs)
- New script added or existing script's interface changed
- Data schema changed (columns added/removed in CSV files)
- Methodology changed (embedding model, clustering params, break detection)
- NOT for manuscript prose edits, figure styling, or build tweaks

## Git discipline

- **Always work on a branch.** Branch naming: `t{N}-short-description`.
- **Enforced by pre-commit hook**: no commits on `main`, `CLAUDE.md` locked, no secrets, no large files (>500KB), no conflict markers.
- **Post-checkout hook**: symlinks `.env` from main worktree into new worktrees (scripts need it for data paths).
- **Hooks** live in `hooks/`. After cloning: `git config core.hooksPath hooks`.
- **One change per commit.** Message explains *why this change and not another*: alternatives considered, local design choices made.
- **Merge commits** (`git merge --no-ff -m`): tactical-level detail — architecture decisions, cross-file impacts, residual debt. Readable via `git log --merges`.
- **Git is the project's long-term memory.** Top-level files reflect *now* — history lives in `git log`. In doubt, check older versions.
- **Use worktrees** for feature branches — work in isolated copies via `git worktree`, not `git stash`/`git checkout`.
- **Create PRs** for each ticket so the author can review changes before merging.

### Autonomous workflow
When working on multiple tickets:
1. Launch each ticket in its own worktree (Agent tool with `isolation: "worktree"`)
2. Independent tickets run in parallel
3. Push each branch and create a PR with summary + test plan
4. Launch a fresh-context agent in a new worktree to review the PR: read the diff (`gh pr diff`), check against the issue's exit criteria, run local and general tests, and post review comments on the PR (`gh pr review`)
5. Clean up worktree branches after pushing named branches

## GitHub Issues as plans

Issues are handoff documents. A new agent will only have the context provided. Each issue must include:
- **Relevant files** and their roles
- **Actions** to take (concrete steps)
- **Verification steps** (how to confirm it's done)
- **Invariants** (what must not break)
- **Exit criteria** (definition of done)

Before doing anything on a ticket, clarify the definition of done.

## Memory policy

### What to remember (let Claude auto-manage MEMORY.md)
- User preferences and workflow corrections
- Machine-specific configuration (paths, API keys, remote machines)
- Naming conventions and project quirks not obvious from code

### What NOT to remember
- Anything derivable from code, git history, or other docs
- Ephemeral task state (use STATE.md or git commits instead)
- Content already in README, ROADMAP, STATE, or guidelines docs

### When to update
- **Celebrating phase**: always review and update memories
- **After user correction**: save feedback immediately
- **After discovering a quirk**: save so future sessions don't rediscover it

## Communication with author

### When to ask
- Argument direction is genuinely ambiguous
- Multiple good sources conflict
- Author's position on controversial topic is unclear

### When not to ask
- Standard academic practices apply
- You can research the answer
- It's a matter of stylistic preference you can reasonably infer

## Self-check questions

Before producing any substantial text:
1. Does this advance the core argument? (Climate finance as constructed economic object)
2. Is the economist's role visible? (Not just "institutions" or "policymakers")
3. Is this historically grounded? (Specific dates, documents, actors)
4. Does this fit Œconomia's interdisciplinary scope? (HET + STS + policy studies)
5. Will this interest both historians of economics AND climate policy scholars?

---

**Remember:** This is not a policy paper or a technical report. It's intellectual history that uses climate finance as a case study for understanding how economists create governable objects through quantification.
