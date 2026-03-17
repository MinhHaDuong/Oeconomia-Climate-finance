# Start ticket — begin work on an issue

When this trigger runs, the agent is about to start implementing a ticket.

## Steps

1. `gh issue view N --json title,body` — read the ticket.
2. Check the **Exit criteria** section. If unclear, ask the author before writing code.
3. Create a worktree and branch:
   ```bash
   git worktree add ../t{N}-short-description -b t{N}-short-description
   ```
4. Read the files listed in **Relevant files**.
5. Write the first test from the **Test** section of the ticket.
6. Run `make check-fast` — confirm the test fails (Red).
7. `[Planning → Doing]` — announce the transition, then begin: Red → Green → Refactor.
