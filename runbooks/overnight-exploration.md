# Overnight autonomous exploration

Unsupervised session — the agent works autonomously overnight, reviews its own PRs,
and pushes forward on deliverables. Author reviews results in the morning.

## Trigger

Entry point is `runbooks/celebrate-day.md` step 8 — the end-of-day celebration
hands off to overnight exploration when the user requests it.

User prompt structured as:

```
Overnight session — unsupervised exploration.

Territory: [braindumps, red tests, next deliverable docs]
Next deliverable: [e.g. Data paper for Scientometrics/QSS/Scientific Data]
Existing branches on origin: [list] — prior work to build on, rebase, or discard.

You may dream, plan, and do. Open branches, PRs, issues freely.
Do NOT merge to main — leave everything as PRs for morning review.
Archive outputs must remain bit-identical on any code-change PR.
Verify: make archive-analysis && make -C /tmp/climate-finance-analysis verify
```

## Procedure

### 0. Bootstrap

Run `on-start.md` trigger. Then read all territory files listed in the prompt.

### 1. Full ticket lifecycle

Don't just open tickets — work them through the complete cycle:

1. **Dream**: understand the problem, explore alternatives.
2. **Plan**: write ticket with test spec.
3. **Do**: TDD in a worktree (red → green → refactor → PR).
4. **Self-review**: launch a review agent in a fresh worktree (`runbooks/review-pr.md`).
5. **Fix**: address review findings, push fixes.
6. **PR**: open for morning review.

Parallelize independent tickets across worktrees.

### 2. Recursive braindump

When you finish working the ideas in existing braindumps:

1. Write a new braindump (`docs/braindump-YYYY-MM-DD-topic.md`) reflecting what you
   learned, what new ideas emerged, and what surprised you.
2. Commit it on a branch.
3. Work the new braindump's actionable ideas.
4. Loop until ideas dry up or all ideas are post-submission/blocked.

Each braindump is dated and committed — they form a trail of the exploration.

### 3. Competing explorations (up to 3)

For strategic choices (which journal? which framing? which structure?),
explore up to 3 approaches in parallel worktrees:

- Branch naming: `explore/A-short-desc`, `explore/B-short-desc`, `explore/C-short-desc`
- Each gets its own PR with a clear thesis statement in the description.
- Morning review picks the winner; losers become reference material.

This applies to code (competing refactoring approaches) and prose
(competing paper framings, journal targets, outlines).

### 4. Forward on the next deliverable

The overnight session must push forward on what matters most — the next
paper, not just code tooling. Tooling work (red tests, hygiene) is valid
but should not consume the entire session.

For a paper deliverable, the full cycle:

1. **Analyze findings**: what research outputs are available?
   Read scripts, figures, tables, stats. What story do they tell?

2. **Survey target journals**: scope, audience, ambitions, recent articles.
   Download author guidelines and sample articles (use WebFetch).
   Check word limits, figure policies, reference style, open data requirements.

3. **Match findings to journals**: which findings fit which audience?
   Which journal's scope aligns with the contribution?

4. **Formalize constraints**: format template, word count, figure count,
   section structure, reference style, submission requirements.

5. **Outline**: structure the argument for each target journal.
   Use `docs/writing-guidelines.md` for prose style.

6. **Draft**: write sections, adjusting framing per journal.
   Look for writing skills on disk (`skills/`, `docs/`, other repos under `~/`).
   If not found, search the web for method papers and author resources.

7. **Review literature**: fill gaps, strengthen positioning.
   Use available corpus data and bibliography.

8. **Iterate**: cycle through steps 5-7, refining.

Run up to 3 journal targets in parallel (competing PRs per step 3 above).

### 5. Keep reflection notes

Write `docs/overnight-log-YYYY-MM-DD.md` on a branch throughout the session:

- Decisions made and alternatives considered
- What worked, what didn't, what surprised you
- Feedback memories saved during the session
- Open questions for the author
- Time allocation: how much went to tooling vs. deliverables?

### 6. Wrap up

Before the session ends:

1. Ensure all worktrees are cleaned up.
2. All work is pushed and PRs are open.
3. Run `runbooks/celebrate-day.md` with the overnight log as input.
4. Final PR list in the last message — the author's morning briefing.

## Invariants

- **Never merge to main.** All changes as PRs.
- **Archive bit-identical.** Verify on any code-change PR.
- **One ticket per worktree.** Independent work stays independent.
- **Commit messages explain why.** Overnight work must be reviewable.
- **No long-running tasks.** Don't launch `make` or API calls that run for hours.

## Anti-patterns from first session (2026-03-19)

- Spent entire session on code tooling (red tests), zero forward progress on deliverables.
- Did not self-review PRs in fresh worktrees.
- Did not recurse into new braindumps after completing existing ones.
- Did not explore competing approaches.
- STATE.md refresh blocked by pre-commit hook on main — use a branch.
