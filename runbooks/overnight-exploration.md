# Overnight autonomous exploration

Unsupervised session — the agent works autonomously overnight, reviews its own PRs,
and pushes forward on deliverables. Author reviews results in the morning.

## Trigger

Entry point is `runbooks/celebrate-day.md` step 10 — the end-of-day celebration
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

The session is a loop of Dragon Dreaming cycles, not a single pass.
Each cycle: Dream (explore) → Plan (outline/ticket) → Do (draft/code/PR)
→ Celebrate (braindump what you learned). Then start the next cycle,
informed by what the previous one revealed. Keep cycling until wrap-up
time (06:00) — there is no fixed cycle count. The mid-session checkpoint
(step 5b) runs between cycles, not at the end.

### Picking a target for each cycle

At the Dreaming phase of each cycle, choose a target with high benefit / risk ratio. Benefits priorities are:

1. **The scientific deliverable is paramount**
2. **Resolve gaps with the north star** (`README.md` § North star) —
   red tests, non-idempotent pipelines, PR defects, under-specified issues.
3. **Fix tickets** — pick the ripest open issue (dependencies met, blockers
   cleared) and work it through Plan → Do.
4. **Sweep for inline markers** — scan code and prose for `FIXME`, `TODO`,
   `HACK`, `IMPROVEMENT`, `XXX` comments. Turn each into a ticket if none
   exists yet.


### 0. Bootstrap

Run `on-start.md` trigger. Record start time (`date`). Then read all
territory files listed in the prompt. Note the start time in the overnight
log immediately — don't wait until wrap-up to start the log.

**Baseline test run:** run `make check` and record results in the overnight
log. This is the baseline — the session must leave things no worse.

**Usage tracking:** every Agent tool task notification includes
`<usage>` with `total_tokens`, `tool_uses`, and `duration_ms`.
Record these per-agent metrics in the overnight log as they arrive.
At wrap-up, sum them into a per-cycle and session-total table.

For CLI subagents (`claude -p`), enable OTEL to capture the same data:

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=console
```

Prefer internal Agent-tool subagents over CLI — they share the parent's
cached context (4x cheaper in measured tests: 29K vs 126K tokens for
the same review task).

### Reference procedures

The target picker (above) selects what to work on each cycle. These
procedures describe *how* to execute each type of work.

#### Deliverable work

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

Run up to 3 journal targets in parallel (competing PRs per § Competing
explorations below).

#### Tooling tickets

Fix red tests, hygiene issues, and technical debt — but only within the
40% budget. Work them through the full lifecycle:

1. **Dream**: understand the problem, explore alternatives.
2. **Plan**: write ticket with test spec.
3. **Do**: TDD in a worktree (red → green → refactor → PR).
4. **Self-review**: single review agent in a fresh worktree (lightweight —
   focus on correctness and behavioral preservation, not full multi-reviewer).
5. **Fix**: address review findings, push fixes.
6. **PR & celebrate**: open PR for morning review. Run `runbooks/celebrate.md`
   to close the cycle before starting the next one.
7. **Verify**: run `make check-fast` after opening the PR to confirm no
   regressions. If tests fail, fix before moving on.

Parallelize independent tickets across worktrees (max 4 active at once —
more causes git/disk contention and token waste).

#### Competing explorations (up to 3 at a time)

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

### 1. Memos (per cycle)

After completing each cycle's work, write a memo
(`docs/local-ai/YYYY-MM-DD-memo-topic.md`) reflecting what you learned,
what new ideas emerged, and what surprised you. Commit it on the cycle's
branch. Work the memo's actionable ideas in subsequent cycles — but only
if they advance a deliverable (not more tooling, unless within the 40%
budget). Each memo is dated and committed — they form a trail of the
exploration.

### 2. Mid-session checkpoint

After roughly half of available effort, pause and check:

- [ ] Have I opened at least one deliverable-forward PR?
- [ ] Is my tooling/deliverable ratio within bounds?
- [ ] Have I self-reviewed at least one PR?
- [ ] Have I written or updated the overnight log?
- [ ] Does `make check` pass on main? (full suite, not just check-fast)

If any box is unchecked, pause tooling and address it.

### 3. Overnight log (one per session)

Write `docs/local-ai/YYYY-MM-DD-log.md` on a dedicated branch
(`overnight-log-YYYY-MM-DD`). This branch carries only the log —
never mixed into a feature branch. Start writing at bootstrap, update
throughout.

Include a balance and time summary:

```
Session: started HH:MM, ended HH:MM (Xh total)
Clock phases: deep work until HH:MM, lighter work until HH:MM, wrap-up at HH:MM

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
- Token usage if available (total tokens, number of tool calls)

### 4. Wrap up

Before the session ends:

1. Run `make check` on main — compare against baseline from bootstrap.
   New failures get ticketed (tag `bug`).
2. Ensure all worktrees are cleaned up.
3. All work is pushed and PRs are open.
4. Write the morning briefing (overnight log + PR list, including test delta).
   Do NOT run `celebrate-day.md` — that would re-trigger overnight
   exploration (step 10). The overnight log IS the celebration artifact.
5. Final PR list in the last message — the author's morning briefing.

## Time and budget management

### Clock awareness

Check the wall clock (`date`) at bootstrap and periodically. Plan work
backwards from the morning review:

- **Before 06:00** — deep work: deliverable drafting, competing explorations.
- **06:00–07:00** — lighter work: braindumps, literature notes, self-reviews.
- **07:00–07:30** — wrap-up: push all branches, write overnight log, clean worktrees.
- **By 08:00** — session must be complete. Final message is the morning briefing.

Don't start a new multi-file refactoring or paper section after 06:00.
Finish in-progress work, commit what you have, note what's incomplete.

### Token budget

The subscription plan uses rolling usage windows. Usage data comes from
two sources: task notification `<usage>` tags (Agent tool) and OTEL
console output (CLI `claude -p`).

**Rules:**
- **Prefer Agent-tool subagents over CLI.** They inherit cached context
  and cost ~4x less (measured: 29K vs 126K tokens for same review).
  Use CLI only when OTEL cost measurement is specifically needed.
- **Default to sequential.** Parallel agents multiply token consumption.
- **Max 3 subagents at a time**.
- **Cap subagent scope** — give focused prompts with pre-summarized
  context. Don't let subagents re-read files you've already read.
- **Memos are cheap** — writing reflection notes costs few tokens
  and produces high value. Prefer writing memos over launching agents.
- **Monitor throttling** — if responses get slower, tool calls are
  declined, or you see rate-limit errors, enter wrap-up immediately.
- **Log usage** — record each task notification's `total_tokens`,
  `tool_uses`, `duration_ms` in the overnight log as they arrive.
  At wrap-up, sum into a per-cycle and session-total table.

## Invariants

- **Never merge to main.** All changes as PRs for morning review.
- **Archive bit-identical.** Verify: `make archive-analysis && make -C /tmp/climate-finance-analysis verify`
- **One ticket per worktree.** Independent work stays independent.
- **Commit messages explain why.** Overnight work must be reviewable.
- **Manage long-running tasks.** Overnight autonomous mode is ideal to launch long running processes (full `make`, API harvesting, model training). Babysit them with TLC. Learn from failures, fix and retry.

## Anti-patterns from first session (2026-03-19)

- Spent entire session on code tooling (red tests), zero forward progress on deliverables.
- Did not self-review PRs in fresh worktrees.
- Did not recurse into new dreams after completing existing ones.
- Did not explore competing approaches.
- STATE.md refresh blocked by pre-commit hook on main — use a branch.
