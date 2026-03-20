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

## Balance rule

**Deliverable work gets at least 60% of the session's effort.** Tooling
(red tests, hygiene, refactoring) is capped at 40%. If you've spent two
consecutive tickets on tooling, the next ticket must advance a deliverable.
Track this in the overnight log (step 5).

**What counts as a deliverable:** items listed in `ROADMAP.md` under the
current milestone — papers, slides, reading notes, figures, responses to
reviewers. Braindumps about tooling, harness improvements, and repo hygiene
are explicitly NOT deliverables. They are tooling.

**Escape hatch:** if `make check-fast` fails and the failure blocks all
deliverable work (build broken, render broken, data pipeline broken), tooling
may exceed 40%. Document the blocker in the overnight log with: (a) what
broke, (b) why it blocks deliverables, (c) what deliverable-forward work
you attempted anyway.

## Procedure

### 0. Bootstrap

Run `on-start.md` trigger. Then read all territory files listed in the prompt.

### 1. Forward on the next deliverable

Do this first, while context is fresh.

The overnight session must push forward on what matters most — the next
paper, slides, or reading notes. For a paper deliverable, the full cycle:

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

Run up to 3 journal targets in parallel (competing PRs per step 3 below).

### 2. Tooling tickets (capped)

Fix red tests, hygiene issues, and technical debt — but only within the
40% budget. Work them through the full lifecycle:

1. **Dream**: understand the problem, explore alternatives.
2. **Plan**: write ticket with test spec.
3. **Do**: TDD in a worktree (red → green → refactor → PR).
4. **Self-review**: launch a review agent in a fresh worktree (`runbooks/review-pr.md`).
5. **Fix**: address review findings, push fixes.
6. **PR**: open for morning review.

Parallelize independent tickets across worktrees.

### 3. Competing explorations (up to 3)

For each braindump idea or strategic choice, brainstorm alternative
implementations, assess them, then try up to 3 promising candidates
in parallel worktrees. The exploration is within one idea, not across
different ideas.

Example: braindump says "offline ticket system." You brainstorm:
(A) flat markdown files in `tickets/`, (B) YAML frontmatter with
status tracking, (C) SQLite-backed with markdown export. Assess
trade-offs, then implement the 2-3 most promising in parallel PRs.

- Branch naming: `t{N}-explore-A-desc`, `t{N}-explore-B-desc`, `t{N}-explore-C-desc`
- Each gets its own PR with a clear thesis statement in the description.
- Morning review picks the winner; losers become reference material.

This applies to code (competing implementations) and prose
(competing paper framings, journal targets, outlines).

### 4. Recursive braindump

When you finish working the current ideas:

1. Write a new braindump (`docs/braindump-YYYY-MM-DD-topic.md`) reflecting what you
   learned, what new ideas emerged, and what surprised you.
2. Commit it on a branch.
3. Work the new braindump's actionable ideas — but only if they advance
   a deliverable (not more tooling, unless within the 40% budget).
4. Loop until ideas dry up or all ideas are post-submission/blocked.

Each braindump is dated and committed — they form a trail of the exploration.

### 5. Keep reflection notes

Write `docs/overnight-log-YYYY-MM-DD.md` on a branch throughout the session.

Include a balance summary table:

```
| Category | Tickets | Approx % |
|----------|---------|----------|
| Deliverable (paper/slides/reading) | #N, #M | 65% |
| Tooling (tests/hygiene/refactor) | #P, #Q | 30% |
| Meta (braindumps/planning) | #R | 5% |
```

If Tooling exceeds 40%, explain why in the "Decisions made" section.

Also include:
- Decisions made and alternatives considered
- What worked, what didn't, what surprised you
- Feedback memories saved during the session
- Open questions for the author

### Mid-session checkpoint

After roughly half of available effort, pause and check:

- [ ] Have I opened at least one deliverable-forward PR?
- [ ] Is my tooling/deliverable ratio within bounds?
- [ ] Have I self-reviewed at least one PR?
- [ ] Have I written or updated the overnight log?

If any box is unchecked, pause tooling and address it.

### 6. Wrap up

Before the session ends:

1. Ensure all worktrees are cleaned up.
2. All work is pushed and PRs are open.
3. Run `runbooks/celebrate-day.md` with the overnight log as input.
4. Final PR list in the last message — the author's morning briefing.

## Invariants

- **Never merge to main.** All changes as PRs.
- **Archive bit-identical.** Verify: `make archive-analysis && make -C /tmp/climate-finance-analysis verify`
- **One ticket per worktree.** Independent work stays independent.
- **Commit messages explain why.** Overnight work must be reviewable.
- **No long-running tasks.** Don't launch `make` or API calls that run for hours.

## Anti-patterns from first session (2026-03-19)

- Spent entire session on code tooling (red tests), zero forward progress on deliverables.
- Did not self-review PRs in fresh worktrees.
- Did not recurse into new braindumps after completing existing ones.
- Did not explore competing approaches.
- STATE.md refresh blocked by pre-commit hook on main — use a branch.
