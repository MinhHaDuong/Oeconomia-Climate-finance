---
name: start-ticket
description: Begin work on a GitHub issue. Creates worktree, writes first test, transitions to Doing phase.
disable-model-invocation: true
user-invocable: true
argument-hint: <issue-number>
---

# Start ticket — begin work on issue $ARGUMENTS

`[Planning → Doing]`

## Steps

1. Read the ticket: `gh issue view $ARGUMENTS --json title,body`
2. Check the **Exit criteria** section. If unclear, ask the author before writing code.
3. Create a worktree and branch:
   ```bash
   git worktree add ../t$ARGUMENTS-short-description -b t$ARGUMENTS-short-description
   ```
4. Read the files listed in **Relevant files**.
5. Write the first test from the **Test** section of the ticket.
6. Run `make check-fast` — confirm the test fails.
7. Announce `[Planning → Doing]`, then implement until tests pass.
8. Create the PR when `make check` passes.
9. Review according to `/review-pr`.
10. Fix all comments regardless of severity.
11. Repeat 9–10 up to 3 times. If still not clean, escalate (see workflow rules).
