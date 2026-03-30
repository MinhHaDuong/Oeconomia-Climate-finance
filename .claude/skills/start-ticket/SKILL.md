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
3. If not already in a worktree, enter one: call `EnterWorktree` with name `t$ARGUMENTS`.
4. Create or checkout the ticket branch:
   ```bash
   git switch -c t$ARGUMENTS-short-description
   ```
5. Read the files listed in **Relevant files**.
6. Write the first test from the **Test** section of the ticket.
7. Run `make check-fast` — confirm the test fails.
8. Announce `[Planning → Doing]`, then implement until `make check` passes.
9. Create the PR.
10. Review according to `/review-pr`.
11. Fix all comments regardless of severity.
12. Repeat 10–11 up to 3 times. If still not clean, escalate (see workflow rules).
