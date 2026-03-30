# Start ticket — begin work on an issue

When this trigger runs, the agent is about to start implementing a ticket.

## Steps

1. `gh issue view N --json title,body` — read the ticket.
2. Check the **Exit criteria** section. If unclear, ask the author before writing code.
3. If not already in a worktree, enter one: call `EnterWorktree` with name `t{N}`.
4. Create or checkout the ticket branch:
   ```bash
   git switch -c t{N}-short-description
   ```
5. Read the files listed in **Relevant files**.
6. Write the first test from the **Test** section of the ticket.
7. Run `make check-fast` — confirm the test fails (Red).
8. `[Planning → Doing]` — announce the transition, then begin: Red → Green → Refactor.
9. Create the PR.
10. Review according to the runbook.
11. Fix, addressing all comments regardless of their apparent severity.
12. Repeat 10–11 up to 3 times. If still not clean, escalate (see AGENTS.md).
