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
4. **Claim the ticket** — set `Status: doing` in the header, append a log entry (`{ISO-timestamp} {agent-id} status doing`), and commit immediately. This makes the claim visible to other agents across worktrees.
5. Read the files listed in **Relevant files** (if any).
6. Write the first test from the **Test** section of the ticket.
7. Run `make check-fast` — confirm the test fails (Red).
8. `[Planning → Doing]` — announce the transition, then begin: Red → Green → Refactor.
9. Create the PR.
10. Review according to the runbook.
11. Fix, addressing all comments regardless of their apparent severity.
12. Repeat 10–11 up to 3 times. If still not clean, escalate (see AGENTS.md).
