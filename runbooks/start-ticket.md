# Start ticket — begin work on an issue

When this trigger runs, the agent is about to start implementing a ticket.

## Steps

1. **Read the ticket.**
   - Local ticket: read `tickets/{id}-{slug}.ticket`.
   - Forge ticket (`Coordination: gh#N`): `gh issue view N --json title,body`.
2. Check the **Exit criteria** section (or body). If unclear, ask the author before writing code.
3. Create a worktree and branch:
   ```bash
   git worktree add ../t/{id}-{slug} -b t/{id}-{slug}
   ```
4. Read the files listed in **Relevant files** (if any).
5. Write the first test from the **Test** section of the ticket.
6. Run `make check-fast` — confirm the test fails (Red).
7. `[Planning → Doing]` — announce the transition, then begin: Red → Green → Refactor.
8. Run one up to three Review/Fix cycle(s), addressing all comments regardless of their apparent severity.
